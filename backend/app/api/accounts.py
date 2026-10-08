"""Workspace accounts: email/password sign-in with durable, hashed session cookies.

Each account sees only the invoices it submitted. It never grants wallet or owner authority.
"""

import asyncio
import hashlib
import hmac
import re
import secrets
import time
import unicodedata

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.api.security import (
    SESSION_COOKIE,
    hash_private,
    problem,
    session_digest,
    session_user,
    team_member,
)
from app.models import RateBucket, UserAccount, UserSession

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32, "maxmem": 64 * 1024 * 1024}
LOGIN_WINDOW = 900

router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=60)


class AccountView(BaseModel):
    id: str
    name: str
    email: str
    team: bool = True  # may submit invoices that spend the shared vault


class AccountResponse(BaseModel):
    user: AccountView


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(stored: str, password: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        params = {
            "n": int(n),
            "r": int(r),
            "p": int(p),
            "dklen": len(digest) // 2,
            "maxmem": SCRYPT["maxmem"],
        }
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **params)
    except ValueError:
        return False
    return hmac.compare_digest(actual.hex(), digest)


# Unknown emails still pay for one scrypt, so response time does not reveal which accounts exist.
UNKNOWN_ACCOUNT = hash_password(secrets.token_urlsafe(16))


def normalize_email(value: str) -> str:
    email = unicodedata.normalize("NFKC", value).strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise problem(422, "Enter a valid email address.", "请输入有效的邮箱地址。")
    return email


def clean_name(value: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", value).split())
    if not 2 <= len(name) <= 60 or any(unicodedata.category(c).startswith("C") for c in name):
        raise problem(422, "Use 2–60 characters for your name.", "姓名需为 2–60 个字符。")
    return name


def throttle(request: Request, limits):
    """Durable fixed-window counters, the same scheme as submission limits. Identities are stored hashed."""
    runtime = request.app.state.runtime
    salt = runtime.settings.ip_hash_salt.get_secret_value()
    if not salt:
        raise problem(503, "Account service is not configured.", "账户服务尚未配置。")
    now = int(time.time())
    with runtime.store.engine.connect() as conn:
        conn.execute(text("BEGIN IMMEDIATE"))
        try:
            conn.execute(delete(RateBucket).where(RateBucket.expires_at <= now))
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
                        429, "Too many attempts. Wait and try again.", "尝试过于频繁，请稍后再试。"
                    )
                conn.execute(
                    insert(RateBucket)
                    .values(key=key, count=count + 1, expires_at=(now // seconds + 1) * seconds)
                    .on_conflict_do_update(index_elements=["key"], set_={"count": count + 1})
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def device_limits(request: Request, scope: str, seconds: int, limit: int):
    device = request.headers.get("x-device-id", "")
    return [(scope, device, seconds, limit)] if 0 < len(device) <= 64 else []


def end_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        with Session(request.app.state.runtime.store.engine) as session:
            session.execute(
                delete(UserSession).where(UserSession.token_hash == session_digest(token))
            )
            session.commit()


def start_session(request: Request, response: Response, user_id: str):
    settings = request.app.state.runtime.settings
    end_session(request)  # never keep a session identifier chosen before sign-in
    token = secrets.token_urlsafe(32)
    ttl = settings.session_ttl_hours * 3600
    now = int(time.time())
    with Session(request.app.state.runtime.store.engine) as session:
        session.execute(delete(UserSession).where(UserSession.expires_at <= now))
        session.add(
            UserSession(token_hash=session_digest(token), user_id=user_id, expires_at=now + ttl)
        )
        session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl,
        path="/",
        httponly=True,
        samesite="strict",
        secure=settings.public_base_url.startswith("https://"),
    )


@router.post("/register", status_code=201, response_model=AccountResponse)
async def register(request: Request, response: Response, body: Registration):
    throttle(
        request,
        [
            ("register-global", "global", 60, 20),
            *device_limits(request, "register-device", 3600, 10),
        ],
    )
    email, name = normalize_email(body.email), clean_name(body.name)
    password_hash = await asyncio.to_thread(hash_password, body.password)
    account = UserAccount(email=email, name=name, password_hash=password_hash)
    with Session(request.app.state.runtime.store.engine) as session:
        session.add(account)
        try:
            session.commit()
        except IntegrityError:
            raise problem(
                409,
                "This email already has an account. Sign in instead.",
                "该邮箱已注册，请直接登录。",
            ) from None
        view = AccountView(
            id=account.id,
            name=account.name,
            email=account.email,
            team=team_member(request, {"email": account.email}),
        )
    start_session(request, response, view.id)
    return {"user": view}


@router.post("/login", response_model=AccountResponse)
async def login(request: Request, response: Response, body: Credentials):
    email = normalize_email(body.email)
    throttle(
        request,
        [
            ("login-global", "global", 60, 120),
            ("login-email", email, LOGIN_WINDOW, 10),
            *device_limits(request, "login-device", LOGIN_WINDOW, 30),
        ],
    )
    with Session(request.app.state.runtime.store.engine) as session:
        account = session.execute(
            select(UserAccount).where(UserAccount.email == email)
        ).scalar_one_or_none()
        stored = account.password_hash if account else UNKNOWN_ACCOUNT
        view = (
            AccountView(
                id=account.id,
                name=account.name,
                email=account.email,
                team=team_member(request, {"email": account.email}),
            )
            if account
            else None
        )
    if not await asyncio.to_thread(verify_password, stored, body.password) or view is None:
        raise problem(401, "Email or password is incorrect.", "邮箱或密码不正确。")
    start_session(request, response, view.id)
    return {"user": view}


@router.post("/logout")
async def logout(request: Request, response: Response):
    end_session(request)
    settings = request.app.state.runtime.settings
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=settings.public_base_url.startswith("https://"),
    )
    return {"ok": True}


@router.get("/me", response_model=AccountResponse)
async def me(request: Request):
    user = session_user(request)
    if user is None:
        raise problem(401, "Not signed in.", "尚未登录。")
    return {"user": {**user, "team": team_member(request, user)}}
