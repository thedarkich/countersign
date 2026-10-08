import asyncio
import hashlib
import hmac
import time
import unicodedata
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session
from starlette.responses import JSONResponse

from app.models import AttemptOwner, RateBucket, UserAccount, UserSession
from app.pipeline.ingest import MAX_BYTES

SESSION_COOKIE = "countersign_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def problem(status, en, zh):
    return HTTPException(status_code=status, detail={"message_en": en, "message_zh": zh})


def has_admin_token(request: Request):
    expected = request.app.state.runtime.settings.admin_token.get_secret_value()
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    return bool(
        expected
        and scheme.lower() == "bearer"
        and hmac.compare_digest(supplied.encode(), expected.encode())
    )


def session_digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def session_user(request: Request):
    """The signed-in account for this request's session cookie, or None. Looked up once per request."""
    if "session_user" not in request.scope:
        token = request.cookies.get(SESSION_COOKIE, "")
        user = None
        if 20 <= len(token) <= 128:
            with Session(request.app.state.runtime.store.engine) as session:
                row = session.execute(
                    select(UserAccount.id, UserAccount.name, UserAccount.email)
                    .join(UserSession, UserSession.user_id == UserAccount.id)
                    .where(
                        UserSession.token_hash == session_digest(token),
                        UserSession.expires_at > int(time.time()),
                    )
                ).first()
            if row:
                user = {"id": row.id, "name": row.name, "email": row.email}
        request.scope["session_user"] = user
    return request.scope["session_user"]


def same_origin(request: Request):
    """Cookie-authorized writes must come from this site (SameSite=Strict is the first line)."""
    origin = urlparse(request.headers.get("origin", ""))
    allowed = {
        request.url.netloc,
        urlparse(request.app.state.runtime.settings.public_base_url).netloc,
    }
    return origin.scheme in {"http", "https"} and origin.netloc in allowed - {""}


def team_member(request: Request, user) -> bool:
    """With TEAM_EMAILS set, only those accounts may spend the shared demo vault; unset means every account."""
    listed = request.app.state.runtime.settings.team_emails
    allowed = {email.strip().lower() for email in listed.split(",") if email.strip()}
    return not allowed or (user is not None and user["email"].lower() in allowed)


def is_admin(request: Request):
    return has_admin_token(request) or session_user(request) is not None


def owns_attempt(request: Request, attempt_id: str):
    user = session_user(request)
    if user is None:
        return False
    with Session(request.app.state.runtime.store.engine) as session:
        owner = session.get(AttemptOwner, attempt_id)
    return owner is not None and owner.user_id == user["id"]


def require_admin_token(request: Request):
    """Shared-budget operations (batches) stay with the team token, not individual accounts."""
    if not has_admin_token(request):
        raise problem(403, "Only the team token can run this.", "仅团队令牌可执行此操作。")


def require_admin(request: Request):
    if has_admin_token(request):
        return
    if session_user(request) is None:
        raise problem(401, "Sign in or provide the team token.", "请登录或提供团队令牌。")
    if request.method not in SAFE_METHODS and not same_origin(request):
        raise problem(403, "Cross-site request refused.", "已拒绝跨站请求。")


def device_id(request: Request, *, required=False):
    raw = request.headers.get("x-device-id", "")
    try:
        if raw:
            return str(UUID(raw))
        if not required:
            return None
    except ValueError:
        if not required:
            return None
    if required:
        raise problem(400, "A valid device ID is required.", "需要有效的设备标识。")


def can_read_private(request, attempt):
    device = device_id(request)
    return (
        has_admin_token(request)
        or owns_attempt(request, attempt.id)
        or bool(
            attempt.source == "bounty"
            and attempt.device_id
            and device
            and hmac.compare_digest(attempt.device_id, device)
        )
    )


def hash_private(value, salt):
    return hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()


class RateLimiter:
    """Atomic fixed-window counters survive restarts; never throttle by shared IP."""

    def __init__(self, engine, settings, clock=time.time):
        self.engine, self.settings, self.clock = engine, settings, clock

    def reserve(self, device, nickname):
        now = int(self.clock())
        salt = self.settings.ip_hash_salt.get_secret_value()
        if not salt:
            raise problem(503, "Submission privacy is not configured.", "提交隐私配置未完成。")
        nick = unicodedata.normalize("NFKC", nickname).casefold().strip()
        limits = [
            ("device-minute", device, 60, self.settings.rate_device_per_min),
            ("device-day", device, 86400, self.settings.rate_device_per_day),
            ("nickname-day", nick, 86400, self.settings.rate_nickname_per_day),
            ("global-minute", "global", 60, self.settings.rate_global_per_min),
        ]
        with self.engine.connect() as conn:
            conn.execute(text("BEGIN IMMEDIATE"))
            try:
                conn.execute(delete(RateBucket).where(RateBucket.expires_at <= now))
                buckets = []
                for scope, identity, seconds, limit in limits:
                    key = f"{scope}:{now // seconds}:{hash_private(identity, salt)}"
                    count = (
                        conn.execute(
                            select(RateBucket.count).where(RateBucket.key == key)
                        ).scalar_one_or_none()
                        or 0
                    )
                    if count >= limit:
                        raise problem(
                            429,
                            "Too many attempts. Wait and try again.",
                            "提交太频繁，请稍后再试。",
                        )
                    buckets.append((key, count, (now // seconds + 1) * seconds))
                for key, count, expiry in buckets:
                    conn.execute(
                        insert(RateBucket)
                        .values(key=key, count=count + 1, expires_at=expiry)
                        .on_conflict_do_update(index_elements=["key"], set_={"count": count + 1})
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise


class RequestBoundary:
    """Bound upload time, bytes and concurrent requests before multipart parsing."""

    def __init__(self, app, *, body_timeout=15, max_inflight=8):
        self.app = app
        self.body_timeout = body_timeout
        self.max_inflight = max_inflight
        self.inflight = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
                )
                if scope["path"].startswith("/api/"):
                    message["headers"].extend(
                        [(b"cache-control", b"no-store"), (b"vary", b"Authorization, X-Device-Id")]
                    )
            await send(message)

        async def reject(status, en, zh):
            response = JSONResponse({"message_en": en, "message_zh": zh}, status_code=status)
            await response(scope, receive, secured_send)

        if scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, secured_send)
        # No await between checking and reserving. Hold through processing, so
        # accepted buffers waiting for RPC/parser work also remain bounded.
        if self.inflight >= self.max_inflight:
            return await reject(
                503, "Upload service is busy. Try later.", "上传服务繁忙，请稍后再试。"
            )
        self.inflight += 1
        try:
            content = bytearray()
            try:
                # One deadline for the complete body; drip-fed chunks do not reset it.
                async with asyncio.timeout(self.body_timeout):
                    while True:
                        part = await receive()
                        if part["type"] == "http.disconnect":
                            return
                        chunk = part.get("body", b"")
                        if len(content) + len(chunk) > MAX_BYTES + 65536:
                            return await reject(413, "Upload is too large.", "上传文件过大。")
                        content.extend(chunk)
                        if not part.get("more_body", False):
                            break
            except TimeoutError:
                return await reject(408, "Upload timed out. Try again.", "上传超时，请重试。")
            consumed = False
            original = receive

            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(content), "more_body": False}
                return await original()

            receive = replay
            await self.app(scope, receive, secured_send)
        finally:
            self.inflight -= 1
