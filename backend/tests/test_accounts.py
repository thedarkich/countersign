"""Invite-only accounts: registration, sign-in, durable sessions, same-origin writes and limits."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_api import ApiChain, public_state
from test_runner import Models

from app.api.accounts import hash_password, verify_password
from app.api.runtime import Runtime
from app.api.security import SESSION_COOKIE, session_digest
from app.config import Settings
from app.main import create_app
from app.models import UserAccount, UserSession

INVITE = "team-invite-for-tests"
ORIGIN = {"Origin": "http://testserver"}
ADMIN = {"Authorization": "Bearer local-api-test-token"}
MEMBER = {
    "name": "Test Member",
    "email": "Member@Example.com",
    "password": "correct horse battery",
    "invite_code": INVITE,
}


def system(tmp_path, invite=INVITE):
    settings = Settings(
        _env_file=None,
        scam_screening_enabled=False,
        data_dir=tmp_path,
        static_dir=tmp_path / "static",
        admin_token="local-api-test-token",
        ip_hash_salt="synthetic-privacy-salt",
        team_invite_code=invite,
        llm_enabled=True,
        transactions_enabled=True,
        public_base_url="http://testserver",
    )
    chain = ApiChain()
    runtime = Runtime(
        settings, chain=chain, models=Models(), state_reader=public_state, receipt_reader=lambda n, t: []
    )
    chain.engine = runtime.store.engine
    return TestClient(create_app(runtime=runtime), raise_server_exceptions=False), runtime


@pytest.fixture
def accounts(tmp_path):
    client, runtime = system(tmp_path)
    with client:
        yield client, runtime


def register(client, **overrides):
    return client.post("/api/register", json={**MEMBER, **overrides})


def test_passwords_are_salted_scrypt_hashes():
    first, second = hash_password("correct horse battery"), hash_password("correct horse battery")
    assert first != second and first.startswith("scrypt$")
    assert verify_password(first, "correct horse battery")
    assert not verify_password(first, "wrong horse battery")
    assert not verify_password("not-a-hash", "correct horse battery")


def test_registration_needs_the_invite_code_and_starts_a_session(accounts):
    client, runtime = accounts
    refused = register(client, invite_code="guess")
    assert refused.status_code == 403 and SESSION_COOKIE not in refused.cookies
    created = register(client)
    assert created.status_code == 201
    assert created.json() == {"id": created.json()["id"], "name": "Test Member", "email": "member@example.com"}
    cookie = created.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert client.get("/api/me").json()["email"] == "member@example.com"
    token = client.cookies.get(SESSION_COOKIE)
    with Session(runtime.store.engine) as session:
        account = session.exec(select(UserAccount)).one()
        stored = session.exec(select(UserSession)).one()
    assert "correct horse battery" not in account.password_hash
    assert stored.token_hash == session_digest(token) != token


def test_registration_closed_without_a_configured_invite(tmp_path):
    client, _ = system(tmp_path, invite="")
    with client:
        assert register(client).status_code == 503


def test_one_account_per_email_case_insensitive(accounts):
    client, _ = accounts
    assert register(client).status_code == 201
    client.cookies.clear()
    assert register(client, email="  MEMBER@example.COM ").status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [("email", "not-an-email"), ("password", "short"), ("name", "x"), ("name", "bad\x00name")],
)
def test_registration_validates_fields(accounts, field, value):
    client, runtime = accounts
    assert register(client, **{field: value}).status_code == 422
    with Session(runtime.store.engine) as session:
        assert session.exec(select(UserAccount)).first() is None


def test_login_logout_and_generic_failures(accounts):
    client, _ = accounts
    register(client)
    assert client.post("/api/logout").json() == {"ok": True}
    assert client.get("/api/me").status_code == 401
    wrong = client.post("/api/login", json={"email": MEMBER["email"], "password": "wrong horse battery"})
    unknown = client.post("/api/login", json={"email": "nobody@example.com", "password": "wrong horse battery"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    ok = client.post("/api/login", json={"email": "member@EXAMPLE.com", "password": MEMBER["password"]})
    assert ok.status_code == 200 and client.get("/api/me").status_code == 200


def test_logout_invalidates_the_session_server_side(accounts):
    client, _ = accounts
    register(client)
    token = client.cookies.get(SESSION_COOKIE)
    client.post("/api/logout")
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/team/attempts").status_code == 401


def test_session_grants_team_reads_and_same_origin_writes(accounts):
    client, _ = accounts
    assert client.get("/api/team/attempts").status_code == 401
    register(client)
    assert client.get("/api/team/attempts").status_code == 200
    data = {"nickname": "team", "agent": "guarded", "text": "private invoice"}
    assert client.post("/api/team/attempts", data=data).status_code == 403
    assert client.post("/api/team/attempts", data=data, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/team/attempts", data=data, headers=ORIGIN).status_code == 202
    # the admin token keeps working for scripts without an Origin header
    client.cookies.clear()
    assert client.post("/api/team/attempts", data=data, headers=ADMIN).status_code == 202


def test_expired_sessions_are_rejected(accounts):
    client, runtime = accounts
    register(client)
    with Session(runtime.store.engine) as session:
        stored = session.exec(select(UserSession)).one()
        stored.expires_at = 0
        session.add(stored)
        session.commit()
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/team/attempts").status_code == 401


def test_login_attempts_are_rate_limited_per_email(accounts):
    client, _ = accounts
    register(client)
    client.cookies.clear()
    body = {"email": MEMBER["email"], "password": "wrong horse battery"}
    assert all(client.post("/api/login", json=body).status_code == 401 for _ in range(10))
    assert client.post("/api/login", json=body).status_code == 429
    assert client.post("/api/login", json={**body, "password": MEMBER["password"]}).status_code == 429
