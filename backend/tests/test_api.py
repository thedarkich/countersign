import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from test_runner import AGENT, ATTACKER, PAYOUT, VAULT, Chain, Models

from app.api.runtime import Runtime
from app.api.security import RateLimiter
from app.chain.indexer import save_events
from app.config import Settings
from app.main import create_app
from app.models import SubmissionMeta
from app.pipeline.runner import new_attempt

ADMIN = {"Authorization": "Bearer local-api-test-token"}
DEVICE = {"X-Device-Id": str(uuid4())}


class ApiChain(Chain):
    def __init__(self):
        super().__init__()
        self.engine = None

    async def send(self, network, agent, proposal, on_broadcast, *, on_prepared=None):
        self.sent.append(proposal)
        tx = "0x" + f"{len(self.sent):064x}"
        on_broadcast(tx)
        blocked = proposal.pay_to != PAYOUT
        event = {
            "network": network,
            "contract_address": VAULT.lower(),
            "tx_hash": tx,
            "log_index": 0,
            "block_number": len(self.sent),
            "block_time": "2026-10-07T00:00:00+00:00",
            "name": "Blocked" if blocked else "Paid",
            "args": {
                "agent": self.registry.agent_addresses[agent],
                "vendorId": proposal.vendor_id,
                "poId": proposal.po_id,
                "payTo": proposal.pay_to,
                "amount": proposal.amount_base,
                "invoiceHash": proposal.invoice_hash,
            },
        }
        if blocked:
            event["args"]["reason"] = 5
        save_events(self.engine, [event])
        return {
            "hash": tx,
            "explorer_url": "https://scan.bohr.life/tx/" + tx,
            "event": event["name"],
            "reason": "PayoutMismatch" if blocked else None,
            "reason_label_en": None,
            "reason_label_zh": None,
            "network": network,
        }


def public_state(network="testnet"):
    return {
        "config": {
            "network": network,
            "chain_id": 968 if network == "testnet" else 677,
            "rpc_url": "https://rpc.bohr.life",
            "explorer_url": "https://scan.bohr.life",
            "contract_address": VAULT,
            "owner_address": PAYOUT,
            "agents": {"guarded": AGENT, "naive": ATTACKER},
            "token": {"address": PAYOUT, "symbol": "USDT", "decimals": 6},
            "public_base_url": "http://testserver",
            "timelock_seconds": 120,
            "bounty_network": "testnet",
        },
        "registry": {
            "vendors": [
                {"id": 1, "name_en": "Acme", "name_zh": "艾克米", "payout": PAYOUT, "active": True}
            ],
            "pos": [
                {
                    "po_id": 1,
                    "ref": "PO-1",
                    "vendor_id": 1,
                    "cap": "10",
                    "remaining": "10",
                    "expiry": "2026-10-31",
                    "period_days": 0,
                    "closed": False,
                }
            ],
            "pending_changes": [],
            "daily_cap": "15",
            "remaining_today": "15",
            "paused": False,
            "vault_balance": "20",
            "agents": [
                {
                    "address": AGENT,
                    "label": "guarded",
                    "active": True,
                    "balance": "1",
                    "gas": "self",
                }
            ],
        },
        "block_number": 1,
        "block_time": "2026-10-07T00:00:00+00:00",
    }


@pytest.fixture
def api_system(tmp_path):
    settings = Settings(
        _env_file=None, scam_screening_enabled=False,
        data_dir=tmp_path,
        static_dir=tmp_path / "static",
        admin_token="local-api-test-token",
        ip_hash_salt="synthetic-privacy-salt",
        llm_enabled=True,
        transactions_enabled=True,
        bounty_enabled=True,
        batch_enabled=True,
        public_base_url="http://testserver",
    )
    chain, models = ApiChain(), Models()
    runtime = Runtime(
        settings,
        chain=chain,
        models=models,
        state_reader=public_state,
        receipt_reader=lambda network, tx: [],
    )
    chain.engine = runtime.store.engine
    with TestClient(create_app(runtime=runtime), raise_server_exceptions=False) as client:
        yield client, runtime, chain, models


def submit(
    client, *, agent="guarded", headers=None, text="private invoice", route="bounty", **data
):
    return client.post(
        f"/api/{route}/attempts",
        headers=headers or DEVICE,
        data={"nickname": "Tester", "agent": agent, "text": text, **data},
    )


def done(client, attempt_id, headers=DEVICE):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get("/api/attempts/" + attempt_id, headers=headers)
        assert response.status_code == 200, response.text
        if response.json()["status"] in {"done", "error"}:
            return response.json()
        time.sleep(0.01)
    raise AssertionError("Attempt did not finish")


def make_pdf():
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 80), "Acme invoice A-1")
        return pdf.tobytes()


def add_fixture(runtime, name="clean/example.pdf", kind="clean", stage=True):
    root = runtime.settings.data_dir / "invoices"
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_pdf())
    manifest = root / "manifest.json"
    entries = json.loads(manifest.read_text()) if manifest.exists() else []
    entries.append(
        {"name": name, "kind": kind, "stage": stage, "title_en": "Example", "title_zh": "样本"}
    )
    manifest.write_text(json.dumps(entries))
    return path


def test_public_read_shapes_and_empty_results(api_system):
    client, _, _, _ = api_system
    assert client.get("/api/config").json()["token"]["decimals"] == 6
    assert client.get("/api/registry").json()["daily_cap"] == "15"
    assert client.get("/api/eval").json() == {}
    assert client.get("/api/ledger").json() == []
    assert client.get("/api/leaderboard").json() == []
    assert client.get("/api/stats").json()["outside"]["attempts"] == 0
    assert client.get("/api/health").json()["ok"]
    assert client.get("/api/ledger?limit=101").status_code == 422
    assert client.get("/api/team/attempts?limit=200", headers=ADMIN).status_code == 200
    assert client.get("/api/team/attempts?limit=201", headers=ADMIN).status_code == 422
    assert client.get("/api/ledger?kind=bogus").status_code == 422
    assert client.get("/api/does-not-exist").status_code == 404


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/team/attempts"),
        ("post", "/api/team/attempts"),
        ("get", "/api/team/demo-invoices"),
        ("post", "/api/team/batch"),
        ("post", "/api/team/owner-tx"),
    ],
)
def test_every_team_route_requires_auth(api_system, method, path):
    client = api_system[0]
    assert getattr(client, method)(path).status_code == 401
    assert (
        getattr(client, method)(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    )


def test_submit_runs_pipeline_and_anonymous_view_redacts(api_system):
    client, runtime, chain, _ = api_system
    response = submit(client)
    assert response.status_code == 202, response.text
    attempt_id = response.json()["attempt_id"]
    result = done(client, attempt_id)
    assert result["outcome"] == "paid" and result["ai_fooled"]
    assert result["proposal"]["amount"] == "1.25"
    assert len(result["steps"]) == 5 and len(chain.sent) == 1
    public = client.get("/api/attempts/" + attempt_id).json()
    assert public["outcome"] == "paid" and public["extraction"] is None
    assert public["steps"] == [] and public["proposal"] is None and public["tx"] is None
    for name in (
        "device_id",
        "input_text",
        "file_path",
        "claimed_address",
        "preview_path",
        "model_versions",
        "error",
    ):
        assert name not in result and name not in public
    assert "private invoice" not in json.dumps(public)
    assert client.get("/api/attempts/" + attempt_id, headers=ADMIN).json()["extraction"]
    assert client.get("/api/team/attempts", headers=ADMIN).json()[0]["id"] == attempt_id
    stats = client.get("/api/stats").json()
    assert stats["outside"]["paid_real_vendor_on_fake_invoice"] == "1.25"
    assert stats["outside"]["money_lost"] == "0"
    assert stats["outside"]["people"] == 1 and stats["seed"]["attempts"] == 0
    assert client.get("/api/ledger?kind=paid").json()[0]["amount"] == "1.25"
    with Session(runtime.store.engine) as session:
        meta = session.get(SubmissionMeta, attempt_id)
        assert meta.ip_hash and "testclient" not in meta.ip_hash


def test_naive_block_refusal_and_error_are_distinct(api_system):
    client, _, chain, models = api_system
    blocked = done(client, submit(client, agent="naive").json()["attempt_id"])
    assert blocked["outcome"] == "blocked" and blocked["tx"]["reason"] == "PayoutMismatch"
    models.invoice.payee_address = ATTACKER
    refused = done(client, submit(client).json()["attempt_id"])
    assert refused["outcome"] == "refused" and refused["steps"][3]["detail"] == "refused"
    models.fail = True
    failed = done(client, submit(client).json()["attempt_id"])
    assert failed["outcome"] == "error" and failed["tx"] is None
    assert "PRIVATE" not in json.dumps(failed)
    stats = client.get("/api/stats").json()["outside"]
    assert stats["chain_blocks"] == 1 and stats["guard_catches"] == 1
    assert stats["ai_fooled"] == {"guarded": 0, "naive": 1}
    assert len(chain.sent) == 1


def test_private_previews_auth_and_path_confinement(api_system):
    client, runtime, _, _ = api_system
    response = client.post(
        "/api/bounty/attempts",
        headers=DEVICE,
        data={"nickname": "Tester", "agent": "guarded"},
        files={"file": ("../../invoice.pdf", make_pdf(), "application/pdf")},
    )
    assert response.status_code == 202, response.text
    result = done(client, response.json()["attempt_id"])
    assert result["file_name"] == "invoice.pdf"
    url = result["preview_url"]
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"X-Device-Id": str(uuid4())}).status_code == 403
    image = client.get(url, headers=DEVICE)
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert "no-store" in image.headers["cache-control"]
    assert client.get(url, headers=ADMIN).status_code == 200
    attempt = runtime.store.get(result["id"])
    attempt.preview_path = str(runtime.settings.data_dir / "countersign.db")
    runtime.store.save(attempt)
    assert client.get(url, headers=ADMIN).status_code == 404


def test_team_device_cannot_bypass_admin(api_system):
    client = api_system[0]
    response = submit(client, route="team", headers={**ADMIN, **DEVICE})
    result = done(client, response.json()["attempt_id"], headers=ADMIN)
    assert result["source"] == "team" and not result["ai_fooled"]
    assert client.get("/api/attempts/" + result["id"], headers=DEVICE).json()["extraction"] is None


@pytest.mark.parametrize(
    "extra",
    [
        {"source": "team"},
        {"scenario": "clean_fixture"},
        {"agent_address": AGENT},
        {"demo": "clean/example.pdf"},
        {"address": "bad"},
        {"agent": "unknown"},
    ],
)
def test_untrusted_fields_cannot_set_identity_or_scenario(api_system, extra):
    client, _, chain, _ = api_system
    data = {"nickname": "Tester", "agent": "guarded", "text": "Invoice", **extra}
    assert client.post("/api/bounty/attempts", headers=DEVICE, data=data).status_code == 400
    assert not chain.sent


def test_missing_device_invalid_text_and_magic_bytes(api_system):
    client = api_system[0]
    assert submit(client, headers={"X-Device-Id": "not-a-uuid"}).status_code == 400
    assert (
        client.post(
            "/api/bounty/attempts", data={"nickname": "Tester", "text": "Invoice"}
        ).status_code
        == 400
    )
    assert submit(client, text="x" * 4001).status_code == 400
    assert (
        client.post(
            "/api/bounty/attempts",
            headers=DEVICE,
            data={"nickname": "Tester"},
            files={"file": ("fake.pdf", b"<script>malicious</script>", "application/pdf")},
        ).status_code
        == 400
    )
    response = client.post(
        "/api/bounty/attempts", headers=DEVICE, content=b"x" * (5 * 1024 * 1024 + 65537)
    )
    assert response.status_code == 413


def test_rate_limits_persist_and_do_not_share_ip(api_system):
    client, runtime, _, _ = api_system
    now = [86401]

    def clock():
        return now[0]

    runtime.limiter.clock = clock
    for _ in range(3):
        assert submit(client).status_code == 202
    response = submit(client)
    assert response.status_code == 429 and set(response.json()) == {"message_en", "message_zh"}
    with pytest.raises(Exception) as exc:
        RateLimiter(runtime.store.engine, runtime.settings, clock=clock).reserve(
            DEVICE["X-Device-Id"], "Tester"
        )
    assert exc.value.status_code == 429
    assert submit(client, headers={"X-Device-Id": str(uuid4())}).status_code == 202
    now[0] += 60
    assert submit(client).status_code == 202


def test_atomic_nickname_and_global_limits(api_system):
    _, runtime, _, _ = api_system
    runtime.settings.rate_device_per_min = 100
    runtime.settings.rate_nickname_per_day = 2
    limiter = RateLimiter(runtime.store.engine, runtime.settings, clock=lambda: 86401)

    def call(_):
        try:
            limiter.reserve(str(uuid4()), "Ｔｅｓｔｅｒ")
            return True
        except Exception as exc:
            assert exc.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        assert sum(pool.map(call, range(5))) == 2
    with pytest.raises(Exception) as exc:
        limiter.reserve(str(uuid4()), "tester")
    assert exc.value.status_code == 429
    runtime.settings.rate_global_per_min = 2
    with pytest.raises(Exception) as exc:
        limiter.reserve(str(uuid4()), "Another")
    assert exc.value.status_code == 429


def test_manifest_whitelist_and_holdout_exclusion(api_system):
    client, runtime, _, _ = api_system
    add_fixture(runtime)
    add_fixture(runtime, "clean_holdout/unseen.pdf", stage=False)
    assert len(client.get("/api/team/demo-invoices", headers=ADMIN).json()) == 1
    for bad in ("../countersign.db", "clean_holdout/unseen.pdf", "/etc/passwd"):
        assert (
            client.post("/api/team/attempts", headers=ADMIN, data={"demo": bad}).status_code == 400
        )
    response = client.post("/api/team/attempts", headers=ADMIN, data={"demo": "clean/example.pdf"})
    assert response.status_code == 202
    assert done(client, response.json()["attempt_id"], ADMIN)["input_kind"] == "pdf"
    response = client.post("/api/team/batch", headers=ADMIN, json={"folder": "clean"})
    assert response.status_code == 202, response.text
    assert (
        client.get("/api/team/batch/" + response.json()["batch_id"], headers=ADMIN).json()["total"]
        == 1
    )
    assert (
        client.post("/api/team/batch", headers=ADMIN, json={"folder": "clean_holdout"}).status_code
        == 422
    )


def test_disabled_spend_bounty_and_batch_gates(api_system):
    client, runtime, chain, _ = api_system
    runtime.settings.bounty_enabled = False
    assert submit(client).status_code == 503
    runtime.settings.batch_enabled = False
    assert (
        client.post("/api/team/batch", headers=ADMIN, json={"folder": "clean"}).status_code == 503
    )
    runtime.settings.llm_enabled = False
    assert submit(client, route="team", headers=ADMIN).status_code == 503
    assert not chain.sent
    assert "AI_DISABLED" in client.get("/api/health").json()["degraded_reasons"]


def test_restart_marks_unfinished_without_rebroadcast(tmp_path):
    settings = Settings(_env_file=None, scam_screening_enabled=False, data_dir=tmp_path, static_dir=tmp_path / "none")
    chain = ApiChain()
    runtime = Runtime(settings, chain=chain, models=Models(), state_reader=public_state)
    attempt = new_attempt(chain.registry, network="testnet", source="team", agent="guarded")
    attempt.status = "sending"
    attempt.tx_hash = "0x" + "99" * 32
    runtime.store.save(attempt)
    with TestClient(create_app(runtime=runtime)):
        result = runtime.store.get(attempt.id)
        assert result.error == "INTERRUPTED_REVIEW_REQUIRED" and result.outcome == "error"
        assert result.tx_hash == attempt.tx_hash and result.tx is None
        assert not chain.sent


def test_state_failure_is_sanitized_and_invalid_host_rejected(api_system):
    client, runtime, _, _ = api_system

    def fail(network):
        raise ValueError("secret-rpc-and-wallet-body")

    runtime.state_reader = fail
    runtime.refreshed.clear()
    response = client.get("/api/config")
    assert response.status_code == 503 and "secret" not in response.text
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_fresh_state_does_not_wait_for_background_refresh(tmp_path):
    async def check():
        runtime = Runtime(
            Settings(_env_file=None, scam_screening_enabled=False, data_dir=tmp_path),
            chain=ApiChain(),
            models=Models(),
            state_reader=public_state,
        )
        snapshot = public_state()
        runtime.states["testnet"] = snapshot
        runtime.refreshed["testnet"] = time.monotonic()
        try:
            async with runtime.state_locks["testnet"]:
                assert await asyncio.wait_for(runtime.state("testnet"), timeout=0.2) is snapshot
        finally:
            runtime.store.engine.dispose()

    asyncio.run(check())
