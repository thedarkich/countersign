import httpx
import pytest
from sqlmodel import Session, select

from app.chain.backfill import ExplorerLogs, IncompleteHistory, discover
from app.chain.indexer import save_events
from app.db import AttemptStore
from app.models import ChainEvent, EventAudit

ADDRESS = "0x" + "11" * 20
TX = "0x" + "22" * 32


def row(block=1, index=0):
    return {
        "address": ADDRESS,
        "transactionHash": TX,
        "blockNumber": hex(block),
        "logIndex": hex(index),
    }


def test_full_range_is_split_without_trusting_page_or_offset():
    calls = []

    def fetch(address, low, high):
        calls.append((low, high))
        return [row()] * 1000 if (low, high) == (1, 2) else [row(low, low)]

    assert discover(fetch, ADDRESS, 1, 2) == {(TX, 1): 1, (TX, 2): 2}
    assert calls == [(1, 2), (1, 1), (2, 2)]


def test_single_block_cap_and_budget_never_claim_complete():
    def fetch(*_):
        return [row()] * 1000

    with pytest.raises(IncompleteHistory, match="Single block"):
        discover(fetch, ADDRESS, 1, 1)
    with pytest.raises(IncompleteHistory, match="budget"):
        discover(fetch, ADDRESS, 1, 100, budget=2)


@pytest.mark.parametrize(
    "changes",
    [
        {"address": "0x" + "33" * 20},
        {"blockNumber": "0x5"},
        {"transactionHash": "invalid"},
        {"removed": True},
        {"logIndex": -1},
    ],
)
def test_wrong_explorer_identity_does_not_advance(changes):
    with pytest.raises(IncompleteHistory):
        discover(lambda *_: [row() | changes], ADDRESS, 1, 2)


def test_duplicate_rows_are_not_accepted_as_complete():
    with pytest.raises(IncompleteHistory):
        discover(lambda *_: [row(), row()], ADDRESS, 1, 2)


def test_http_errors_are_not_empty_history():
    bodies = [
        {"status": "0", "message": "No logs found", "result": []},
        {"status": "0", "message": "rate limited", "result": []},
        {"status": "1", "message": "OK", "result": "bad"},
    ]

    def handler(request):
        assert request.url.params["fromBlock"] == "1"
        return httpx.Response(200, json=bodies.pop(0))

    explorer = ExplorerLogs("https://example.test", transport=httpx.MockTransport(handler))
    try:
        assert explorer.fetch(ADDRESS, 1, 2) == []
        for _ in range(2):
            with pytest.raises(IncompleteHistory):
                explorer.fetch(ADDRESS, 1, 2)
    finally:
        explorer.close()


def test_remined_receipt_corrects_log_position_and_retains_audit(tmp_path):
    store = AttemptStore(tmp_path / "test.db")
    original = {
        "network": "testnet",
        "contract_address": ADDRESS,
        "tx_hash": TX,
        "log_index": 0,
        "block_number": 1,
        "block_time": "2026-10-07T00:00:00+00:00",
        "name": "Paid",
        "args": {"amount": 1},
    }
    save_events(store.engine, [original])
    changed = original | {"log_index": 2, "block_number": 2}
    receipt = {"blockNumber": 2, "blockHash": bytes.fromhex("33" * 32)}
    save_events(store.engine, [changed], receipt=receipt)
    save_events(store.engine, [changed], receipt=receipt)
    with Session(store.engine) as session:
        events = session.exec(select(ChainEvent)).all()
        assert len(events) == 1 and events[0].log_index == 2
        history = session.exec(select(EventAudit)).all()
        assert len(history) == 1 and history[0].payload["block_number"] == 1
    store.engine.dispose()
