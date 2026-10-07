from sqlmodel import Session
from test_api import (
    ApiChain,
    api_system,  # noqa: F401
    public_state,
)
from test_runner import AGENT, ATTACKER, PAYOUT, VAULT

from app.api.reputation import build_reputation
from app.chain.indexer import save_events
from app.db import AttemptStore
from app.models import Attempt
from app.pipeline.runner import new_attempt


def attempt(
    store,
    *,
    agent="guarded",
    source="team",
    outcome="refused",
    scenario="unlabeled",
    proposal=False,
    tx=None,
):
    a = new_attempt(
        ApiChain().registry,
        network="testnet",
        source=source,
        agent=agent,
        nickname="PRIVATE-NICKNAME",
        device_id="PRIVATE-DEVICE",
        input_text="PRIVATE-INVOICE",
    )
    a.status, a.outcome, a.scenario, a.tx_hash = "done", outcome, scenario, tx
    a.model_versions, a.guard_version = {"extract": "mock-extractor-v1"}, "v1"
    if proposal:
        a.proposal = {
            "vendor_id": 1,
            "po_id": 1,
            "pay_to": PAYOUT,
            "amount_base": "1250000",
            "amount": "1.25",
            "invoice_hash": "0x" + "ab" * 32,
        }
    store.save(a)
    return a


def event(store, a, *, name="Blocked", reason=5, **changes):
    value = {
        "network": "testnet",
        "contract_address": VAULT.lower(),
        "tx_hash": a.tx_hash,
        "log_index": 0,
        "block_number": 10,
        "block_time": a.created_at,
        "name": name,
        "args": {
            "agent": a.agent_address,
            "vendorId": 1,
            "poId": 1,
            "payTo": PAYOUT,
            "amount": 1250000,
            "invoiceHash": "0x" + "ab" * 32,
        },
    }
    if name == "Blocked":
        value["args"]["reason"] = reason
    save_events(store.engine, [value | changes])


def history(store, address=AGENT, state=None):
    result = build_reputation(store.engine, state or public_state())
    return next(agent for agent in result.agents if agent.agent_address == address.lower()), result


def test_known_attack_refusal_is_successful_defense_not_suspicion(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    attempt(store, source="bounty", scenario="known_attack")
    agent, result = history(store)
    assert agent.status == "no_flag_observed" and agent.counts.known_attack_refusals == 1
    assert agent.counts.suspicious_proposals == 0
    assert "PRIVATE" not in result.model_dump_json()
    assert result.coverage.stale and "BACKFILL_NOT_VERIFIED" in result.coverage.gaps


def test_known_attack_paid_to_registered_vendor_remains_flagged(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    a = attempt(
        store,
        source="bounty",
        scenario="known_attack",
        outcome="paid",
        proposal=True,
        tx="0x" + "01" * 32,
    )
    event(store, a, name="Paid")
    agent, _ = history(store)
    assert agent.status == "suspicious_observed"
    assert (
        agent.counts.confirmed_payments
        == agent.counts.suspicious_proposals
        == agent.counts.proposals
        == 1
    )
    assert agent.recent_observations[0].evidence == ["application_record", "verified_transaction"]


def test_budget_pause_duplicate_errors_do_not_imply_fraud(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    for i, reason in enumerate([1, 9, 10]):
        a = attempt(store, outcome="blocked", proposal=True, tx="0x" + f"{i + 1:064x}")
        event(store, a, reason=reason)
    attempt(store, outcome="error", proposal=True)
    agent, _ = history(store)
    assert agent.counts.policy_blocks == 3 and agent.counts.errors == 1
    assert agent.counts.suspicious_proposals == 0 and agent.status == "no_flag_observed"


def test_receipt_merges_without_double_count_and_wrong_chain_is_excluded(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    a = attempt(
        store,
        agent="naive",
        outcome="blocked",
        scenario="known_attack",
        proposal=True,
        tx="0x" + "02" * 32,
    )
    event(store, a)
    event(store, a)
    with Session(store.engine) as session:
        row = session.get(Attempt, a.id)
        session.delete(row)
        session.commit()
    agent, _ = history(store, ATTACKER)
    assert agent.counts.receipt_only == agent.counts.suspicious_proposals == 1
    assert agent.recent_observations[0].source == "unknown"
    store.save(a)
    event(store, a, network="mainnet")
    event(store, a, contract_address=PAYOUT.lower())
    for _ in range(2):
        agent, _ = history(store, ATTACKER)
        assert (
            agent.counts.observations
            == agent.counts.policy_blocks
            == agent.counts.suspicious_proposals
            == 1
        )
        assert agent.counts.receipt_only == 0


def test_wrong_proposal_does_not_gain_verified_transaction_attribution(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    a = attempt(store, outcome="paid", proposal=True, tx="0x" + "03" * 32)
    event(store, a, name="Paid")
    a.proposal["amount_base"] = "999"
    store.save(a)
    agent, _ = history(store)
    application = next(o for o in agent.recent_observations if o.id.startswith("attempt:"))
    assert application.outcome == "unverified" and application.transaction_url is None
    assert agent.counts.receipt_only == 1 and agent.counts.confirmed_payments == 1


def test_revoked_key_keeps_history_new_key_starts_empty_and_versions_stay_separate(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    first = attempt(store, source="team")
    second = attempt(store, source="seed", scenario="known_attack")
    second.guard_version = "v2"
    store.save(second)
    state = public_state()
    state["config"]["agents"]["guarded"] = "0x" + "66" * 20
    state["registry"]["agents"][0]["active"] = False
    old, result = history(store, state=state)
    assert not old.active and len(old.breakdown) == 2
    fresh = next(a for a in result.agents if a.agent_address == "0x" + "66" * 20)
    assert fresh.status == "no_history" and fresh.counts.observations == 0
    assert {b.guard_version for b in old.breakdown} == {first.guard_version, "v2"}


def test_public_endpoint_empty_and_private_projection(request):
    client, runtime, _, _ = request.getfixturevalue("api_system")
    response = client.get("/api/reputation")
    assert response.status_code == 200
    assert all(a["status"] == "no_history" for a in response.json()["agents"])
    attempt(runtime.store, scenario="known_attack", proposal=True, outcome="error")
    response = client.get("/api/reputation?limit=1")
    assert response.status_code == 200 and "PRIVATE" not in response.text
    assert "input_text" not in response.text and "device_id" not in response.text
    assert response.json()["agents"][0]["status"] == "suspicious_observed"
    assert client.get("/api/reputation?limit=101").status_code == 422
