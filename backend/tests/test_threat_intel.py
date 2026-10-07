import asyncio
import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import ApiChain, public_state
from test_runner import ATTACKER, PAYOUT, Chain, Models

from app.api.runtime import Runtime
from app.config import Settings
from app.db import AttemptStore
from app.main import create_app
from app.pipeline.ingest import ingest_text
from app.pipeline.runner import PipelineRunner, new_attempt
from app.threat_intel import COMMITS, RAW, ScreeningUnavailable, WalletScreening, parse_snapshot

NOW = 1791360000
SHA = "a" * 40
LICENSE = "GNU GENERAL PUBLIC LICENSE Version 3\n" + "test license fixture\n" * 100


def payload(addresses=(ATTACKER,), **updates):
    raw = json.dumps(list(addresses))
    return (
        dict(
            version=1,
            revision=SHA,
            checked_at=NOW,
            source_updated_at="2026-10-07T00:00:00Z",
            address_json=raw,
            source_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            license_text=LICENSE,
        )
        | updates
    )


def feed(tmp_path, addresses=(ATTACKER,)):
    value = WalletScreening(tmp_path, clock=lambda: NOW)
    value.snapshot = parse_snapshot(payload(addresses), NOW)
    return value


def test_exact_case_insensitive_matching_never_claims_safety(tmp_path):
    value = feed(tmp_path, ("0x" + "Ab" * 20,))
    view = value.view(["0x" + "aB" * 20, PAYOUT])
    assert [c.verdict for c in view.checks] == ["listed", "not_listed"]
    assert view.publication_delay_days == 7 and view.revision == SHA
    assert view.chain_scope == "address_match_without_chain_attribution"
    with pytest.raises(ValueError):
        value.view(["https://attacker.invalid"])


def test_missing_stale_and_clock_rollback_fail_closed(tmp_path):
    value = WalletScreening(tmp_path, clock=lambda: NOW)
    with pytest.raises(ScreeningUnavailable):
        value.require_ready()
    value.snapshot = parse_snapshot(payload(checked_at=NOW - 172801), NOW)
    assert value.view([PAYOUT]).checks[0].verdict == "unavailable"
    assert value.view([ATTACKER]).checks[0].verdict == "listed"
    with pytest.raises(ScreeningUnavailable):
        value.require_ready()
    value.clock = lambda: NOW - 200000
    assert not value.view().ready


@pytest.mark.parametrize(
    "updates",
    [
        {"revision": "../malicious"},
        {"version": 2},
        {"checked_at": NOW + 1000},
        {"source_sha256": "wrong"},
        {"license_text": "wrong"},
        {"address_json": "[]"},
        {"source_updated_at": "not a date"},
    ],
)
def test_corrupt_snapshots_rejected(updates):
    with pytest.raises((ValueError, KeyError)):
        parse_snapshot(payload(**updates), NOW)


@pytest.mark.parametrize("addresses", [[], ["bad"], [123], ["0x" + "a" * 39]])
def test_bad_address_lists_rejected(addresses):
    with pytest.raises(ValueError):
        parse_snapshot(payload(addresses), NOW)


def transport(requests, *, bad=None):
    def respond(request):
        url = str(request.url)
        requests.append(url)
        assert request.method == "GET"
        if url == COMMITS:
            if bad == "redirect":
                return httpx.Response(302, headers={"location": "https://evil.invalid"})
            return httpx.Response(
                200, json={"sha": SHA, "commit": {"committer": {"date": "2026-10-07T00:00:00Z"}}}
            )
        if url == RAW + SHA + "/blacklist/address.json":
            if bad == "oversize":
                return httpx.Response(200, content=b"x" * (4 * 1024 * 1024 + 1))
            return httpx.Response(200, json=["bad"] if bad == "invalid" else [ATTACKER])
        assert url == RAW + SHA + "/LICENSE"
        return httpx.Response(200, text=LICENSE)

    return httpx.MockTransport(respond)


def test_refresh_pins_revision_keeps_license_and_reloads_atomic_cache(tmp_path):
    requests = []
    value = WalletScreening(tmp_path, clock=lambda: NOW)
    asyncio.run(value.refresh(transport=transport(requests)))
    assert len(requests) == 3 and all(ATTACKER not in url for url in requests)
    assert value.path.stat().st_mode & 0o777 == 0o600
    saved = json.loads(value.path.read_text())
    assert (
        saved["license_text"] == LICENSE
        and saved["source_sha256"] == hashlib.sha256(saved["address_json"].encode()).hexdigest()
    )
    reloaded = WalletScreening(tmp_path, clock=lambda: NOW)
    assert reloaded.view([ATTACKER]).checks[0].verdict == "listed"
    assert not list(value.path.parent.glob("*.tmp"))


@pytest.mark.parametrize("bad", ["redirect", "invalid", "oversize"])
def test_bad_refresh_preserves_last_good_snapshot_without_extending_freshness(tmp_path, bad):
    value = feed(tmp_path)
    original = value.snapshot
    requests = []
    with pytest.raises(ScreeningUnavailable):
        asyncio.run(value.refresh(transport=transport(requests, bad=bad)))
    assert value.snapshot is original and value.last_refresh_failed
    assert not any("evil.invalid" in u for u in requests)


@pytest.mark.parametrize("agent", ["guarded", "naive"])
@pytest.mark.parametrize("target", ["invoice", "registry"])
def test_listed_invoice_or_registry_refuses_both_agents_before_proposal(tmp_path, agent, target):
    chain, models = Chain(), Models()
    if target == "invoice":
        models.invoice.payee_address = ATTACKER
    else:
        chain.registry = replace(
            chain.registry, vendors=[replace(chain.registry.vendors[0], payout=ATTACKER)]
        )
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=feed(tmp_path))
    item = new_attempt(chain.registry, network="testnet", source="team", agent=agent)
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("test invoice")))
    assert result.outcome == "refused" and not chain.sent and result.proposal is None
    assert (
        result.flags[-1]["code"] == "SCAM_SNIFFER_LISTED" and SHA in result.flags[-1]["detail_en"]
    )
    assert models.guard_calls == 0 and "naive" not in result.model_versions


def test_naive_changed_proposal_checked_before_signing(tmp_path):
    chain, models = Chain(), Models()
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=feed(tmp_path))
    item = new_attempt(chain.registry, network="testnet", source="bounty", agent="naive")
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("test invoice")))
    assert result.proposal["pay_to"] == ATTACKER
    assert result.outcome == "refused" and result.tx_hash is None and not chain.sent
    assert result.match["wallet_screening"]["revision"] == SHA
    assert result.ai_fooled and len(result.match["wallet_screening_history"]) == 2


def test_unavailable_feed_stops_before_model_call_and_not_a_fraud_flag(tmp_path):
    chain, models = Chain(), Models()
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=WalletScreening(tmp_path))
    item = new_attempt(chain.registry, network="testnet", source="team", agent="guarded")
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("test invoice")))
    assert result.outcome == "error" and result.error == "WALLET_SCREENING_UNAVAILABLE"
    assert not result.flags and not result.model_versions and not chain.sent


def test_not_listed_still_goes_through_existing_vault_rules(tmp_path):
    chain, models = Chain(), Models()
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=feed(tmp_path, ["0x" + "99" * 20]))
    item = new_attempt(chain.registry, network="testnet", source="team", agent="naive")
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("test invoice")))
    assert result.outcome == "blocked" and result.block_reason == "PayoutMismatch"


def test_public_lookup_health_and_private_admission(tmp_path):
    settings = Settings(
        _env_file=None,
        scam_screening_enabled=True,
        data_dir=tmp_path,
        indexer_enabled=False,
        llm_enabled=True,
        transactions_enabled=True,
        bounty_enabled=True,
    )
    chain = ApiChain()
    runtime = Runtime(settings, chain=chain, models=Models(), state_reader=public_state)
    chain.engine = runtime.store.engine
    runtime.screening = feed(tmp_path)
    runtime.runner.screening = runtime.screening

    async def offline_refresh():
        await asyncio.Event().wait()

    runtime.screening.refresh_loop = offline_refresh
    with TestClient(create_app(runtime=runtime)) as client:
        response = client.get("/api/security/wallets", params={"address": ATTACKER})
        assert response.status_code == 200 and response.json()["checks"][0]["verdict"] == "listed"
        assert "address_json" not in response.text and "license_text" not in response.text
        assert client.get("/api/security/wallets", params={"address": "bad"}).status_code == 422
        runtime.screening.snapshot = None
        assert (
            "WALLET_SCREENING_UNAVAILABLE" in client.get("/api/health").json()["degraded_reasons"]
        )
        assert client.post("/api/bounty/attempts").status_code == 503


def test_snapshot_expiring_during_model_call_stops_before_signing(tmp_path):
    chain, models = Chain(), Models()
    screening = feed(tmp_path)
    original = models.naive

    async def expire(payload, versions):
        decision = await original(payload, versions)
        screening.clock = lambda: NOW + 172801
        return decision

    models.naive = expire
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=screening)
    item = new_attempt(chain.registry, network="testnet", source="team", agent="naive")
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("invoice")))
    assert result.error == "WALLET_SCREENING_UNAVAILABLE" and result.proposal
    assert not chain.sent and result.tx_hash is None


def test_source_rollback_preserves_snapshot(tmp_path):
    value = feed(tmp_path)
    value.snapshot = parse_snapshot(payload(source_updated_at="2026-10-07T01:00:00Z"), NOW)
    original = value.snapshot
    with pytest.raises(ScreeningUnavailable):
        asyncio.run(value.refresh(transport=transport([])))
    assert value.snapshot is original


@pytest.mark.parametrize("proposed", [True, False])
def test_reputation_only_attributes_listed_proposal_to_agent(tmp_path, proposed):
    from app.api.reputation import observation

    chain, models = Chain(), Models()
    if not proposed:
        models.invoice.payee_address = ATTACKER
    store = AttemptStore(tmp_path / "case.db")
    runner = PipelineRunner(store, models, chain, screening=feed(tmp_path))
    item = new_attempt(chain.registry, network="testnet", source="team", agent="naive")
    store.save(item)
    result = asyncio.run(runner.run(item.id, ingest_text("invoice")))
    record, counts = observation(result, None, "https://scan.bohr.life")
    assert record.suspicious == proposed and counts.suspicious_proposals == int(proposed)
    assert ("SCAM_SNIFFER_LISTED" in record.reason_codes) == proposed
    assert record.evidence == ["application_record"] and record.transaction_url is None
    # A model-supplied flag without our screening evidence must not accuse an agent.
    result.match = {}
    assert not observation(result, None, "https://scan.bohr.life")[0].suspicious
