import asyncio
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
