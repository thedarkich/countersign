import asyncio
import json

import pymupdf
import pytest
from test_api import public_state
from test_fixtures import registry
from test_runner import Chain, Models

from app.api.runtime import Runtime
from app.config import Settings
from app.eval import run as evaluation
from app.models import Attempt
from app.schemas import Extraction, GuardVerdict


def test_runtime_lease_prevents_two_nonce_owners(tmp_path):
    async def check():
        settings = Settings(_env_file=None, data_dir=tmp_path)
        first = Runtime(settings, chain=Chain(), models=Models(), state_reader=public_state)
        second = Runtime(settings, chain=Chain(), models=Models(), state_reader=public_state)
        await first.start()
        try:
            with pytest.raises(RuntimeError, match="one backend"):
                await second.start()
        finally:
            await first.stop()
        await second.start()
        await second.stop()

    asyncio.run(check())


def test_comparison_once_no_transactions_and_no_false_improvement(tmp_path, monkeypatch):
    state = registry()
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    monkeypatch.setattr(evaluation, "PROMPTS", prompt_dir)

    def extraction(number, visible=""):
        return Extraction(
            is_invoice=True,
            vendor_name="Vendor 1",
            invoice_number=number,
            currency="USDT",
            amount_total=0.1,
            po_reference="PO-1",
            payee_address=state.vendors[0].payout,
            visible_text=visible,
        )

    paths = {}
    for split in ("clean", "clean_holdout"):
        path = tmp_path / (split + ".pdf")
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 80), "Vendor 1 Invoice")
            document.save(path)
        paths[split] = [path]

    def record(identifier):
        item = Attempt(
            id=identifier,
            network="testnet",
            chain_id=968,
            contract_address="vault",
            agent_address="agent",
            agent="guarded",
            source="seed",
            input_text="Invoice",
            extraction=extraction(identifier).model_dump(),
        )
        return {"id": identifier, "attempt": item, "technique": identifier}

    class OfflineModels:
        guard_prompt = "v1"
        calls = 0

        async def extract(self, document, versions):
            self.calls += 1
            return extraction("clean", document.text)

        async def guard(self, payload, versions):
            self.calls += 1
            bad = self.guard_prompt != "v1"
            return GuardVerdict(verdict="malicious" if bad else "ok", risk=1 if bad else 0)

    models = OfflineModels()
    report = asyncio.run(
        evaluation.compare(
            models, state, [record("TRAIN")], [record("HELDOUT")], paths, tmp_path / "eval"
        )
    )
    assert models.calls == 6 and models.guard_prompt == "v1"
    assert report["v1"]["catch"] == 0 and report["v2"]["catch"] == 1
    assert report["v2"]["false_alarm"] == 1
    audit = json.loads((tmp_path / "eval/audit.json").read_text())
    assert not audit["v2_eligible"] and not audit["deployment_changed"]
    assert "HELDOUT" not in (prompt_dir / "guard_v2.md").read_text()
    with pytest.raises(ValueError, match="Existing"):
        asyncio.run(
            evaluation.compare(
                models, state, [record("TRAIN")], [record("HELDOUT")], paths, tmp_path / "eval"
            )
        )
    assert models.calls == 6
