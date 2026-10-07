import asyncio
from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.config import Settings
from app.db import AttemptStore
from app.llm import ModelUnavailable
from app.models import ChainEvent
from app.pipeline.agents import human_amount, naive_proposal
from app.pipeline.ingest import ingest_text
from app.pipeline.match import PurchaseOrder, Vendor
from app.pipeline.runner import PipelineRunner, RegistrySnapshot, new_attempt
from app.schemas import Extraction, GuardVerdict, NaiveDecision

PAYOUT = "0x" + "11" * 20
ATTACKER = "0x" + "22" * 20
AGENT = "0x" + "33" * 20
VAULT = "0x" + "44" * 20
TX = "0x" + "55" * 32


class Models:
    guard_version = "v1"

    def __init__(self):
        self.invoice = Extraction(
            is_invoice=True,
            vendor_name="Acme",
            invoice_number="A-1",
            currency="USDT",
            amount_total=1.25,
            po_reference="PO-1",
            payee_address=PAYOUT,
            visible_text="Acme invoice A-1",
        )
        self.verdict = GuardVerdict(verdict="ok", risk=0.1)
        self.decision = NaiveDecision(
            vendor_id=1, po_id=1, pay_to=ATTACKER, amount=1.25, invoice_number="A-1"
        )
        self.guard_calls = 0
        self.fail = False
        self.active = 0
        self.max_active = 0
        self.delay = 0

    async def extract(self, document, versions):
        versions["extract"] = "mock-extractor-2026"
        if self.fail:
            raise ModelUnavailable("PRIVATE INVOICE TEXT")
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        await asyncio.sleep(self.delay)
        self.active -= 1
        return self.invoice

    async def guard(self, payload, versions):
        self.guard_calls += 1
        versions["guard"] = "mock-guard-2026"
        return self.verdict

    async def naive(self, payload, versions):
        versions["naive"] = "mock-naive-2026"
        return self.decision


class Chain:
    def __init__(self):
        self.registry = RegistrySnapshot(
            968,
            VAULT,
            {"guarded": AGENT, "naive": ATTACKER},
            [Vendor(1, "Acme", "艾克米", (), PAYOUT)],
            [PurchaseOrder(1, "PO-1", 1, 10_000_000)],
            6,
            "USDT",
        )
        self.sent = []
        self.paid = False
        self.failure = None

    async def snapshot(self, network):
        return self.registry

    async def invoice_paid(self, network, invoice_hash):
        return self.paid

    async def send(self, network, agent, proposal, on_broadcast, *, on_prepared=None):
        self.sent.append(proposal)
        if self.failure == "before":
            raise RuntimeError("PRIVATE RPC BODY")
        on_broadcast(TX)
        if self.failure == "after":
            raise RuntimeError("PRIVATE REVERT REASON")
        blocked = proposal.pay_to != PAYOUT
        return {
            "hash": TX,
            "event": "Blocked" if blocked else "Paid",
            "reason": "PayoutMismatch" if blocked else None,
            "network": network,
            "explorer_url": "https://scan.bohr.life/tx/" + TX,
            "reason_label_en": None,
            "reason_label_zh": None,
        }


@pytest.fixture
def system(tmp_path):
    store, models, chain = AttemptStore(tmp_path / "test.db"), Models(), Chain()
    runner = PipelineRunner(store, models, chain)
    return store, models, chain, runner


def make(system, *, agent="guarded", source="team", **kwargs):
    store, _, chain, _ = system
    attempt = new_attempt(chain.registry, network="testnet", source=source, agent=agent, **kwargs)
    store.save(attempt)
    return attempt


def run(system, attempt):
    return asyncio.run(system[-1].run(attempt.id, ingest_text("Invoice")))


def test_guarded_clean_persists_every_result(system):
    result = run(system, make(system))
    store, models, chain, _ = system
    saved = store.get(result.id)
    assert saved.outcome == "paid" and saved.status == "done"
    assert saved.proposal["pay_to"] == PAYOUT
    assert saved.proposal["amount"] == "1.25"
    assert chain.sent[0].amount_base == 1_250_000
    assert saved.model_versions == {"extract": "mock-extractor-2026", "guard": "mock-guard-2026"}
    assert saved.guard_version == "v1" and not saved.ai_fooled
    assert [step["name"] for step in saved.steps] == [
        "extract",
        "hidden_text",
        "match",
        "guard",
        "chain",
    ]
    assert all(step["status"] in {"done", "skipped"} for step in saved.steps)


def test_deterministic_refusal_uses_no_second_model_or_chain(system):
    system[1].invoice.payee_address = ATTACKER
    result = run(system, make(system, source="bounty"))
    assert result.outcome == "refused" and not result.ai_fooled
    assert not system[2].sent and system[1].guard_calls == 0
    assert result.steps[3]["detail"] == "refused"
    assert "guard" not in result.model_versions
    assert result.scenario == "known_attack"


def test_model_can_refuse_clean_looking_invoice(system):
    system[1].verdict = GuardVerdict(verdict="suspicious", risk=0.6)
    result = run(system, make(system))
    assert result.outcome == "refused" and not system[2].sent


def test_naive_attack_reaches_chain_and_block_is_distinct(system):
    result = run(system, make(system, agent="naive", source="bounty"))
    assert result.outcome == "blocked" and result.ai_fooled
    assert result.proposal["pay_to"] == ATTACKER
    assert result.block_reason == "PayoutMismatch"
    assert result.summary_en == "Got a payment proposed"
    assert result.guard_version is None
    assert result.model_versions["naive"] == "mock-naive-2026"


def test_fake_invoice_paid_real_vendor_remains_known_attack(system):
    result = run(system, make(system, source="bounty"))
    assert result.outcome == "paid" and result.ai_fooled and result.scenario == "known_attack"


def test_no_invoice_stops_before_guard_or_chain(system):
    system[1].invoice.is_invoice = False
    result = run(system, make(system))
    assert result.outcome == "no_invoice" and not system[2].sent
    assert all(step["status"] == "skipped" for step in result.steps[1:])


def test_duplicate_check_refuses_changed_amount(system):
    system[2].paid = True
    system[1].invoice.amount_total = 2
    result = run(system, make(system))
    assert result.outcome == "refused" and not system[2].sent
    assert "DUPLICATE_INVOICE" in [flag["code"] for flag in result.flags]


@pytest.mark.parametrize("when,fooled", [("before", False), ("after", True)])
def test_chain_failure_never_becomes_paid_or_policy_block(system, when, fooled):
    system[2].failure = when
    result = run(system, make(system, source="bounty"))
    assert result.outcome == "error" and result.status == "error"
    assert result.tx is None and result.block_reason is None
    assert result.ai_fooled is fooled
    assert bool(result.tx_hash) is fooled
    assert result.proposal is not None  # Application evidence survives transport failure.
    assert "PRIVATE" not in result.model_dump_json()


def test_model_failure_is_sanitized_and_never_sends(system):
    system[1].fail = True
    result = run(system, make(system))
    assert result.error == "MODEL_UNAVAILABLE" and result.outcome == "error"
    assert result.steps[0]["status"] == "failed" and not system[2].sent
    assert "PRIVATE" not in result.model_dump_json()


def test_identity_change_fails_before_model_or_payment(system):
    attempt = make(system)
    system[2].registry = replace(system[2].registry, chain_id=677)
    result = run(system, attempt)
    assert result.outcome == "error" and not result.model_versions and not system[2].sent


def test_duplicate_job_claim_and_three_worker_limit(system):
    attempts = [make(system) for _ in range(7)]
    system[1].delay = 0.015

    async def jobs():
        runner = system[-1]
        await asyncio.gather(
            *(
                runner.run(item.id, ingest_text("Invoice"))
                for item in [*attempts, attempts[0], attempts[0]]
            )
        )

    asyncio.run(jobs())
    assert len(system[2].sent) == 7
    assert system[1].max_active == 3
    assert all(system[0].get(attempt.id).outcome == "paid" for attempt in attempts)


def test_server_scenario_and_identity_cannot_be_overridden(system):
    assert make(system, fixture_kind="poisoned").scenario == "known_attack"
    assert make(system, fixture_kind="clean").scenario == "clean_fixture"
    with pytest.raises(ValueError):
        make(system, scenario="clean_fixture")
    with pytest.raises(ValueError):
        make(system, agent_address=ATTACKER)


def test_naive_unknown_ids_pass_through_and_invalid_payout_fallback(system):
    decision = NaiveDecision(
        vendor_id=2**200, po_id=99, pay_to=ATTACKER, amount=1, invoice_number="NEW"
    )
    proposal = naive_proposal(decision, system[2].registry.vendors, 6)
    assert proposal.vendor_id == 2**200 and proposal.po_id == 99
    decision.vendor_id, decision.pay_to = 1, "bad address"
    assert naive_proposal(decision, system[2].registry.vendors, 6).pay_to == PAYOUT
    decision.vendor_id = 99
    with pytest.raises(ValueError):
        naive_proposal(decision, system[2].registry.vendors, 6)


def test_event_deduplication_keeps_chain_and_vault_in_identity(system):
    def event(network="testnet", vault=VAULT):
        return ChainEvent(
            network=network,
            contract_address=vault,
            tx_hash=TX,
            log_index=0,
            block_number=1,
            block_time="2026-10-06T00:00:00+00:00",
            name="Paid",
            args={},
        )

    with Session(system[0].engine) as session:
        session.add_all([event(), event("mainnet"), event(vault=PAYOUT)])
        session.commit()
        session.add(event())
        with pytest.raises(IntegrityError):
            session.commit()


def test_settings_disable_spend_and_hide_synthetic_secrets(monkeypatch):
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    settings = Settings(_env_file=None, scam_screening_enabled=False, tokenrouter_api_key="fake-test-secret")
    assert settings.llm_enabled is False
    assert "fake-test-secret" not in repr(settings)
    assert "fake-test-secret" not in settings.model_dump_json()
    assert human_amount(1, 18) == "0.000000000000000001"
    assert human_amount(10**40, 0) == str(10**40)
