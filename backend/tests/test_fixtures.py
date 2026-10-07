import json
from dataclasses import replace

import pytest

from app.fixtures import generate
from app.pipeline.hidden_text import inspect_hidden_text
from app.pipeline.ingest import ingest_bytes
from app.pipeline.match import PurchaseOrder, Vendor
from app.pipeline.runner import RegistrySnapshot


def registry():
    vendors = [Vendor(i, f"Vendor {i}", f"供应商{i}", (), "0x" + f"{i:040x}") for i in range(1, 4)]
    pos = [PurchaseOrder(i, f"PO-{i}", i, 100_000_000) for i in range(1, 4)]
    return RegistrySnapshot(968, "0x" + "aa" * 20, {}, vendors, pos, 6, "USDT")


def test_generator_separates_holdout_and_detects_hidden_fixtures(tmp_path):
    result = generate(tmp_path, registry(), attacker="0x" + "bb" * 20)
    assert result == {
        "run_id": "R1",
        "fixtures": 64,
        "clean": 20,
        "clean_holdout": 20,
        "poisoned": 24,
        "clean_total": "2.90",
        "stage_validated": 0,
    }
    entries = json.loads((tmp_path / "manifest.json").read_text())
    clean = [e for e in entries if e["split"] == "clean"]
    holdout = [e for e in entries if e["split"] == "clean_holdout"]
    assert len({e["invoice_number"] for e in clean + holdout}) == 40
    assert sum(e["language"] == "zh" for e in clean) == 10
    assert not any(e["stage"] for e in entries)
    for entry in entries:
        data = (tmp_path / entry["name"]).read_bytes()
        assert len(data) < 5 * 1024 * 1024
        document = ingest_bytes(data)
        if entry["technique"] in {"white_text", "tiny_text"}:
            hidden, flags = inspect_hidden_text(document, document.text)
            assert hidden.has_hidden_text and any(flag.code == "HIDDEN_TEXT" for flag in flags)
        elif entry["split"] == "clean":
            _, flags = inspect_hidden_text(document, document.text)
            assert not any(flag.severity == "high" for flag in flags)
    with pytest.raises(ValueError, match="Run ID"):
        generate(tmp_path, registry(), attacker="0x" + "bb" * 20)
    generate(tmp_path, registry(), attacker="0x" + "bb" * 20, run_id="R2")
    current = json.loads((tmp_path / "manifest.json").read_text())
    assert len(current) == 64 and all(e["run_id"] == "R2" for e in current)
    assert (tmp_path / "runs/R1.json").exists()


def test_generator_rejects_over_budget_batch_and_path_run_id(tmp_path):
    original = registry()
    exhausted = replace(original, pos=[replace(po, remaining_base=1) for po in original.pos])
    with pytest.raises(ValueError, match="budget"):
        generate(tmp_path, exhausted, attacker="0x" + "bb" * 20)
    with pytest.raises(ValueError, match="Run ID"):
        generate(tmp_path, original, attacker="0x" + "bb" * 20, run_id="../../bad")
    assert not (tmp_path / "manifest.json").exists()
