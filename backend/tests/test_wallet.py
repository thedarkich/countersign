"""Pay from your own wallet: proof of control, whitelist with a waiting period, own maximum, verified receipts."""

from types import SimpleNamespace

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from test_accounts import MEMBER, ORIGIN, register, system

import app.api.wallet as wallet_api

PAYEE = "0x419D0c4F429981b45548724404E5a2CeFcB303d0"
OTHER = "0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b"
HASH = "0x" + "ab" * 32


class FakeChain:
    def __init__(self):
        self.txs, self.receipts = {}, {}

    def transaction(self, tx_hash):
        return self.txs.get(tx_hash)

    def receipt(self, tx_hash):
        return self.receipts.get(tx_hash)


@pytest.fixture
def member(tmp_path, monkeypatch):
    client, runtime = system(tmp_path)
    clock = [1_800_000_000]
    monkeypatch.setattr(wallet_api, "time", SimpleNamespace(time=lambda: clock[0]))
    with client:
        assert register(client).status_code == 201
        client.app.state.wallet_chain = FakeChain()
        yield client, clock


def link(client, key=None):
    key = key or Account.create()
    message = client.post(
        "/api/wallet/challenge", json={"address": key.address}, headers=ORIGIN
    ).json()["message"]
    signature = key.sign_message(encode_defunct(text=message)).signature.to_0x_hex()
    return key, client.post(
        "/api/wallet/link", json={"address": key.address, "signature": signature}, headers=ORIGIN
    )


def ready(client, clock, max_bot="0.5"):
    """A linked wallet, an active payee and a maximum."""
    key, response = link(client)
    assert response.status_code == 200
    payee = client.post(
        "/api/wallet/payees", json={"address": PAYEE, "label": "Printer"}, headers=ORIGIN
    ).json()
    assert client.put("/api/wallet/limit", json={"max": max_bot}, headers=ORIGIN).status_code == 200
    clock[0] += 61
    return key, payee


def approve(client, payee_id, amount):
    return client.post(
        "/api/wallet/payments", json={"payee_id": payee_id, "amount": amount}, headers=ORIGIN
    )


def test_wallet_routes_need_a_signed_in_account_and_same_origin(tmp_path):
    client, _ = system(tmp_path)
    with client:
        assert client.get("/api/wallet").status_code == 401
        assert (
            client.get(
                "/api/wallet", headers={"Authorization": "Bearer local-api-test-token"}
            ).status_code
            == 401
        )
        register(client)
        assert client.get("/api/wallet").status_code == 200
        assert (
            client.post("/api/wallet/payees", json={"address": PAYEE, "label": "x"}).status_code
            == 403
        )


def test_linking_requires_a_fresh_signature_from_that_wallet(member):
    client, clock = member
    key, response = link(client)
    assert response.status_code == 200
    assert client.get("/api/wallet").json()["wallet"]["address"] == key.address
    # someone else's signature, a reused challenge, and an expired challenge are all refused
    victim = Account.create()
    message = client.post(
        "/api/wallet/challenge", json={"address": victim.address}, headers=ORIGIN
    ).json()["message"]
    forged = Account.create().sign_message(encode_defunct(text=message)).signature.to_0x_hex()
    assert (
        client.post(
            "/api/wallet/link",
            json={"address": victim.address, "signature": forged},
            headers=ORIGIN,
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/wallet/link",
            json={"address": victim.address, "signature": forged},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    message = client.post(
        "/api/wallet/challenge", json={"address": victim.address}, headers=ORIGIN
    ).json()["message"]
    clock[0] += 301
    signed = victim.sign_message(encode_defunct(text=message)).signature.to_0x_hex()
    assert (
        client.post(
            "/api/wallet/link",
            json={"address": victim.address, "signature": signed},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert client.get("/api/wallet").json()["wallet"]["address"] == key.address
    assert client.delete("/api/wallet", headers=ORIGIN).status_code == 200
    assert client.get("/api/wallet").json()["wallet"] is None


def test_new_payees_wait_and_only_whitelisted_active_addresses_are_approved(member):
    client, clock = member
    link(client)
    client.put("/api/wallet/limit", json={"max": "1"}, headers=ORIGIN)
    payee = client.post(
        "/api/wallet/payees", json={"address": PAYEE.lower(), "label": "Printer"}, headers=ORIGIN
    )
    assert payee.status_code == 201 and payee.json()["address"] == PAYEE
    assert (
        client.post(
            "/api/wallet/payees", json={"address": PAYEE, "label": "Again"}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/wallet/payees", json={"address": "0x1234", "label": "Bad"}, headers=ORIGIN
        ).status_code
        == 422
    )
    blocked = approve(client, payee.json()["id"], "0.1")
    assert blocked.status_code == 409 and "60 s" in blocked.json()["message_en"]
    clock[0] += 60
    approved = approve(client, payee.json()["id"], "0.1")
    assert approved.status_code == 201
    assert approved.json()["tx"] == {
        "from": approved.json()["tx"]["from"],
        "to": PAYEE,
        "value": str(10**17),
        "chain_id": 677,
    }
    assert approve(client, "not-a-payee", "0.1").status_code == 404
    assert (
        client.delete(f"/api/wallet/payees/{payee.json()['id']}", headers=ORIGIN).status_code == 200
    )
    assert approve(client, payee.json()["id"], "0.1").status_code == 404


def test_own_maximum_lowers_at_once_and_raises_after_the_wait(member):
    client, clock = member
    _, payee = ready(client, clock, max_bot="0.5")
    assert approve(client, payee["id"], "0.6").status_code == 409
    assert approve(client, payee["id"], "0.5").status_code == 201
    raised = client.put("/api/wallet/limit", json={"max": "2"}, headers=ORIGIN).json()
    assert raised["max"] == "0.5" and raised["pending_max"] == "2"
    assert approve(client, payee["id"], "1").status_code == 409
    clock[0] += 61
    assert approve(client, payee["id"], "1").status_code == 201
    assert (
        client.put("/api/wallet/limit", json={"max": "0.1"}, headers=ORIGIN).json()["max"] == "0.1"
    )
    assert approve(client, payee["id"], "0.2").status_code == 409
    for bad in ("0", "-1", "abc", "0.0000000000000000001"):
        assert client.put("/api/wallet/limit", json={"max": bad}, headers=ORIGIN).status_code == 422


def test_sent_transaction_is_checked_against_the_approval(member):
    client, clock = member
    key, payee = ready(client, clock)
    fake = client.app.state.wallet_chain
    payment = approve(client, payee["id"], "0.05").json()["payment"]
    # not mined yet: stays "sent", then settles when the history is read again
    sent = client.post(
        f"/api/wallet/payments/{payment['id']}/sent", json={"tx_hash": HASH}, headers=ORIGIN
    ).json()["payment"]
    assert (
        sent["status"] == "sent" and sent["explorer_url"] == "https://scan.botchain.ai/tx/" + HASH
    )
    fake.txs[HASH] = {"from": key.address, "to": PAYEE, "value": 5 * 10**16}
    fake.receipts[HASH] = {"status": 1, "block_number": 123}
    history = client.get("/api/wallet/payments").json()["payments"]
    assert history[0]["status"] == "confirmed" and history[0]["block_number"] == 123
    # an approval is single use, and a hash can be recorded once
    assert (
        client.post(
            f"/api/wallet/payments/{payment['id']}/sent", json={"tx_hash": HASH}, headers=ORIGIN
        ).status_code
        == 409
    )
    second = approve(client, payee["id"], "0.05").json()["payment"]
    assert (
        client.post(
            f"/api/wallet/payments/{second['id']}/sent", json={"tx_hash": HASH}, headers=ORIGIN
        ).status_code
        == 409
    )


def test_wallet_that_sends_something_else_is_flagged(member):
    client, clock = member
    key, payee = ready(client, clock)
    fake = client.app.state.wallet_chain
    for tx_hash, tx, receipt, status in (
        (
            "0x" + "01" * 32,
            {"from": key.address, "to": OTHER, "value": 5 * 10**16},
            {"status": 1, "block_number": 7},
            "mismatch",
        ),
        (
            "0x" + "02" * 32,
            {"from": key.address, "to": PAYEE, "value": 9 * 10**16},
            {"status": 1, "block_number": 8},
            "mismatch",
        ),
        (
            "0x" + "03" * 32,
            {"from": key.address, "to": PAYEE, "value": 5 * 10**16},
            {"status": 0, "block_number": 9},
            "failed",
        ),
    ):
        fake.txs[tx_hash], fake.receipts[tx_hash] = tx, receipt
        payment = approve(client, payee["id"], "0.05").json()["payment"]
        result = client.post(
            f"/api/wallet/payments/{payment['id']}/sent", json={"tx_hash": tx_hash}, headers=ORIGIN
        )
        assert result.json()["payment"]["status"] == status
    flagged = client.get("/api/wallet/payments").json()["payments"]
    assert {p["detail"] for p in flagged} >= {
        "The wallet changed the recipient.",
        "The wallet changed the amount.",
    }


def test_accounts_never_see_each_other(member, tmp_path):
    client, clock = member
    _, payee = ready(client, clock)
    approve(client, payee["id"], "0.05")
    client.post("/api/logout", headers=ORIGIN)
    register(client, email="other@example.com")
    view = client.get("/api/wallet").json()
    assert view["wallet"] is None and view["payees"] == [] and view["limit"] is None
    assert client.delete(f"/api/wallet/payees/{payee['id']}", headers=ORIGIN).status_code == 404
    assert approve(client, payee["id"], "0.05").status_code in {404, 409}
    assert client.get("/api/wallet/payments").json()["payments"] == []
    assert MEMBER["email"] != "other@example.com"
