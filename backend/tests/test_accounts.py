"""Workspace accounts: open sign-up, sign-in, durable sessions, per-account invoices, same-origin writes and limits."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_api import ApiChain, done, public_state
from test_runner import Models

from app.api.accounts import hash_password, verify_password
from app.api.runtime import Runtime
from app.api.security import SESSION_COOKIE, session_digest
from app.config import Settings
from app.main import create_app
from app.models import UserAccount, UserSession

ORIGIN = {"Origin": "http://testserver"}
ADMIN = {"Authorization": "Bearer local-api-test-token"}
MEMBER = {"name": "Test Member", "email": "Member@Example.com", "password": "correct horse battery"}
INVOICE = {"nickname": "team", "agent": "guarded", "text": "private invoice"}


def system(tmp_path):
    settings = Settings(
        _env_file=None,
        scam_screening_enabled=False,
        data_dir=tmp_path,
        static_dir=tmp_path / "static",
        admin_token="local-api-test-token",
        ip_hash_salt="synthetic-privacy-salt",
        llm_enabled=True,
        transactions_enabled=True,
        batch_enabled=True,
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


def test_open_registration_starts_a_session(accounts):
    client, runtime = accounts
    created = register(client)
    assert created.status_code == 201
    user = created.json()["user"]  # the shape the sign-in page reads
    assert user == {"id": user["id"], "name": "Test Member", "email": "member@example.com", "team": True}
    cookie = created.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert client.get("/api/me").json() == {"user": user}
    token = client.cookies.get(SESSION_COOKIE)
    with Session(runtime.store.engine) as session:
        account = session.exec(select(UserAccount)).one()
        stored = session.exec(select(UserSession)).one()
    assert "correct horse battery" not in account.password_hash
    assert stored.token_hash == session_digest(token) != token


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
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "member@example.com"
    assert client.get("/api/me").json()["user"]["name"] == "Test Member"


def test_logout_invalidates_the_session_server_side(accounts):
    client, _ = accounts
    register(client)
    token = client.cookies.get(SESSION_COOKIE)
    client.post("/api/logout")
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/team/attempts").status_code == 401


def test_session_writes_need_same_origin(accounts):
    client, _ = accounts
    assert client.get("/api/team/attempts").status_code == 401
    register(client)
    assert client.get("/api/team/attempts").status_code == 200
    assert client.post("/api/team/attempts", data=INVOICE).status_code == 403
    assert client.post("/api/team/attempts", data=INVOICE, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN).status_code == 202
    # the admin token keeps working for scripts without an Origin header
    client.cookies.clear()
    assert client.post("/api/team/attempts", data=INVOICE, headers=ADMIN).status_code == 202


def test_each_account_sees_only_its_own_invoices(accounts):
    client, _ = accounts
    register(client)
    mine = client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN).json()["attempt_id"]
    done(client, mine, headers={})
    alice = client.cookies.get(SESSION_COOKIE)
    client.cookies.clear()
    register(client, name="Other Member", email="other@example.com")
    assert client.get("/api/team/attempts").json() == []
    view = client.get("/api/attempts/" + mine).json()
    assert view.get("extraction") is None and view.get("proposal") is None
    assert client.get(f"/api/attempts/{mine}/preview.png").status_code == 403
    client.cookies.set(SESSION_COOKIE, alice)
    assert [a["id"] for a in client.get("/api/team/attempts").json()] == [mine]
    assert client.get("/api/attempts/" + mine).json().get("extraction") is not None
    client.cookies.clear()
    assert [a["id"] for a in client.get("/api/team/attempts", headers=ADMIN).json()] == [mine]


def test_accounts_cannot_run_the_shared_batch(accounts):
    client, _ = accounts
    register(client)
    assert client.post("/api/team/batch", json={"folder": "clean"}, headers=ORIGIN).status_code == 403
    client.cookies.clear()
    assert client.post("/api/team/batch", json={"folder": "clean"}, headers=ADMIN).status_code != 403


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


def test_account_submissions_are_rate_limited_but_the_team_token_is_not(accounts):
    client, _ = accounts
    register(client)
    codes = [client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]
    client.cookies.clear()
    assert all(client.post("/api/team/attempts", data=INVOICE, headers=ADMIN).status_code == 202 for _ in range(4))


def test_only_team_accounts_spend_the_shared_vault_when_a_team_list_is_set(accounts):
    client, runtime = accounts
    runtime.settings.team_emails = " Member@Example.com , lead@example.com "
    assert register(client).json()["user"]["team"] is True
    assert client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN).status_code == 202
    client.post("/api/logout", headers=ORIGIN)
    outsider = register(client, email="visitor@example.com").json()["user"]
    assert outsider["team"] is False and client.get("/api/me").json()["user"]["team"] is False
    refused = client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN)
    assert refused.status_code == 403 and "team accounts" in refused.json()["message_en"]
    assert client.get("/api/wallet").status_code == 200  # the Wallet page stays open to every account
    assert client.post("/api/team/attempts", data=INVOICE, headers=ADMIN).status_code == 202
    runtime.settings.team_emails = ""  # unset: every account may submit, as before
    assert client.post("/api/team/attempts", data=INVOICE, headers=ORIGIN).status_code == 202
