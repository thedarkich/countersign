import hashlib
import hmac
import time
import unicodedata
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.sqlite import insert
from starlette.responses import JSONResponse

from app.models import RateBucket
from app.pipeline.ingest import MAX_BYTES


def problem(status, en, zh):
    return HTTPException(status_code=status, detail={"message_en": en, "message_zh": zh})


def is_admin(request: Request):
    expected = request.app.state.runtime.settings.admin_token.get_secret_value()
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    return bool(
        expected
        and scheme.lower() == "bearer"
        and hmac.compare_digest(supplied.encode(), expected.encode())
    )


def require_admin(request: Request):
    if not is_admin(request):
        raise problem(401, "Admin token required.", "需要管理员令牌。")


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
    return is_admin(request) or bool(
        attempt.source == "bounty"
        and attempt.device_id
        and device
        and hmac.compare_digest(attempt.device_id, device)
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
    """Bound bodies before multipart parsing, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            content = bytearray()
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    return
                content.extend(part.get("body", b""))
                if len(content) > MAX_BYTES + 65536:
                    response = JSONResponse(
                        {"message_en": "Upload is too large.", "message_zh": "上传文件过大。"},
                        status_code=413,
                    )
                    return await response(scope, receive, send)
                if not part.get("more_body", False):
                    break
            consumed = False
            original = receive

            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(content), "more_body": False}
                return await original()

            receive = replay

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

        await self.app(scope, receive, secured_send)
