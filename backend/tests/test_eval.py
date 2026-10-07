import asyncio
from dataclasses import replace

import pytest
from test_fixtures import registry

from app.eval.run import attack_example, build_prompt, judge, write_private
from app.eval.split import may_promote, split_attacks, wilson
from app.pipeline.ingest import ingest_text
from app.schemas import Extraction, GuardVerdict


def test_group_split_stable_no_device_or_technique_leak():
    records = [
        {
            "id": f"{source}-{group}-{i}",
            "source": source,
            "device_id": f"device{group}",
            "technique": f"technique{group}",
        }
        for source in ("bounty", "seed")
        for group in range(5)
        for i in range(2)
    ]
    records += [
        {"id": "excluded", "source": "seed", "technique": "duplicate"},
        {"id": "missing", "source": "bounty"},
    ]
    train, heldout, excluded = split_attacks(records)
    assert len(train) == 12 and len(heldout) == 8
    assert not {r["group"] for r in train} & {r["group"] for r in heldout}
    assert split_attacks(list(reversed(records))) == (train, heldout, excluded)
    assert excluded == {"state_dependent": 1, "missing_group": 1}


def test_wilson_edges_and_promotion():
    assert wilson(0, 10) == pytest.approx((0, 0.2775328))
    assert wilson(10, 10) == pytest.approx((0.7224672, 1))
    assert wilson(5, 10) == pytest.approx((0.2365931, 0.7634069))
    with pytest.raises(ValueError):
        wilson(0, 0)
    old = {"catch": 0.5, "false_alarm": 0.1}
    assert may_promote(old, {"catch": 0.6, "false_alarm": 0.1})
    assert not may_promote(old, {"catch": 0.6, "false_alarm": 0.2})
    assert not may_promote(old, old)


def test_offline_guard_drops_budget_rule_and_budget_from_prompt():
    state = registry()
    state = replace(state, pos=[replace(po, remaining_base=0) for po in state.pos])
    invoice = Extraction(
        is_invoice=True,
        vendor_name="Vendor 1",
        invoice_number="old-paid",
        currency="USDT",
        amount_total=0.1,
        po_reference="PO-1",
        payee_address=state.vendors[0].payout,
    )

    class Models:
        async def guard(self, payload, versions):
            assert "remaining_base" not in payload["purchase_order"]
            assert payload["flags"] == []
            return GuardVerdict(verdict="ok", risk=0, reasons=[])

    assert not asyncio.run(judge(Models(), ingest_text("invoice"), invoice, state, {}))
    # Payout checking remains active even when duplicate/budget checks are disabled.
    invoice.payee_address = "0x" + "bb" * 20
    assert asyncio.run(judge(Models(), ingest_text("invoice"), invoice, state, {}))


def test_training_prompt_bounded_and_run_marker_exclusive(tmp_path):
    from app.models import Attempt

    item = Attempt(
        network="testnet",
        chain_id=968,
        contract_address="vault",
        agent_address="agent",
        agent="guarded",
        source="seed",
        guard={"instructions_found": ["ignore rules" * 100] * 10},
    )
    row = {"attempt": item, "technique": "test"}
    assert len(attack_example(row)["instructions_found"]) == 3
    prompt = build_prompt("v1", [row] * 15, [{"label": "clean"}] * 8)
    assert prompt.count('"technique"') == 12 and prompt.count('"label"') == 6
    write_private(tmp_path / "marker", "first")
    with pytest.raises(FileExistsError):
        write_private(tmp_path / "marker", "retry")
