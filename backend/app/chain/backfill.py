"""Bounded Blockscout discovery, verified against RPC receipts; no eth_getLogs."""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from eth_utils import to_hex
from sqlmodel import Session

from app.chain.indexer import decode_receipt, save_events
from app.chain.recovery import invalidate
from app.models import IndexCursor, now_iso

HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")


class IncompleteHistory(Exception):
    """A bounded or unverified range must not advance the cursor."""


class ExplorerLogs:
    def __init__(self, base_url, *, transport=None):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Explorer must be a configured HTTPS origin")
        self.url = base_url.rstrip("/") + "/api"
        self.http = httpx.Client(timeout=10, follow_redirects=False, transport=transport)

    def close(self):
        self.http.close()

    def fetch(self, address, start, end):
        with self.http.stream(
            "GET",
            self.url,
            params={
                "module": "logs",
                "action": "getLogs",
                "address": address,
                "fromBlock": start,
                "toBlock": end,
            },
        ) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise IncompleteHistory("Explorer response too large")
                chunks.append(chunk)
        body = json.loads(b"".join(chunks))
        rows = body.get("result")
        if not isinstance(rows, list) or str(body.get("status")) not in {"0", "1"}:
            raise IncompleteHistory("Explorer did not return logs")
        if str(body.get("status")) == "0" and (rows or body.get("message") != "No logs found"):
            raise IncompleteHistory("Explorer reported an error")
        return rows


def number(value):
    return (
        int(value[2:] or "0", 16)
        if isinstance(value, str) and value.startswith("0x")
        else int(value)
    )


def discover(fetch, address, start, end, *, budget=20):
    """Bisect capped ranges. A full single block fails closed instead of losing logs."""
    ranges, found, calls = [(start, end)], {}, 0
    while ranges:
        low, high = ranges.pop()
        calls += 1
        if calls > budget:
            raise IncompleteHistory("Range request budget exhausted")
        rows = fetch(address, low, high)
        if not isinstance(rows, list) or len(rows) > 1000:
            raise IncompleteHistory("Unexpected log count")
        if len(rows) == 1000:
            if low == high:
                raise IncompleteHistory("Single block hit explorer limit")
            middle = (low + high) // 2
            ranges.extend([(middle + 1, high), (low, middle)])
            continue
        seen = set()
        for row in rows:
            tx, index, block = (
                row["transactionHash"].lower(),
                number(row["logIndex"]),
                number(row["blockNumber"]),
            )
            if (
                row["address"].lower() != address.lower()
                or not HASH.fullmatch(tx)
                or not low <= block <= high
                or index < 0
                or row.get("removed") is True
                or (tx, index) in seen
            ):
                raise IncompleteHistory("Explorer log identity mismatch")
            seen.add((tx, index))
            found[(tx, index)] = block
    return found


def start_block(settings, network, contract):
    configured = getattr(settings, "indexer_start_block_" + network)
    if configured is not None:
        return configured
    # Public deployment metadata only, never infer a start from the latest observed receipt.
    path = Path(__file__).resolve().parents[3] / "docs" / "deployments" / f"{network}.json"
    if path.is_file():
        metadata = json.loads(path.read_text())
        if metadata.get("contract_address", "").lower() == contract.lower():
            return int(metadata["deploy_block"])
    return 0


class Backfiller:
    def __init__(self, vault, store, settings, *, explorers=None):
        self.vault, self.store, self.settings = vault, store, settings
        self.explorers = (
            explorers
            if explorers is not None
            else {
                network: ExplorerLogs(client.explorer_url)
                for network, client in vault.networks.items()
            }
        )

    def close(self):
        for explorer in self.explorers.values():
            explorer.close()

    def cursor(self, network, client):
        address = client.contract.address.lower()
        key = f"{network}:{address}"
        with Session(self.store.engine) as session:
            cursor = session.get(IndexCursor, key)
            if cursor is None:
                first = start_block(self.settings, network, address)
                cursor = IndexCursor(
                    key=key,
                    network=network,
                    contract_address=address,
                    start_block=first,
                    last_block=first - 1,
                )
                session.add(cursor)
                session.commit()
                session.refresh(cursor)
            session.expunge(cursor)
            return cursor

    def sync(self, network):
        client = self.vault._client(network)
        cursor = self.cursor(network, client)
        try:
            self._sync(network, client, cursor)
            return "synced"
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Backfill incomplete: %s %s", network, type(exc).__name__
            )
            # An explorer failure never discards already verified receipt evidence.
            with Session(self.store.engine) as session:
                current = session.get(IndexCursor, cursor.key)
                current.error = "BACKFILL_INCOMPLETE"
                session.add(current)
                session.commit()
            return "incomplete"

    def _sync(self, network, client, cursor):
        w3, address = client.w3, cursor.contract_address
        head = w3.eth.block_number - self.settings.indexer_lag_blocks
        if cursor.last_hash:
            canonical = to_hex(w3.eth.get_block(cursor.last_block)["hash"])
            if canonical.lower() != cursor.last_hash.lower():
                with Session(self.store.engine) as session:
                    invalidate(session, network, address)
                    current = session.get(IndexCursor, cursor.key)
                    current.last_block, current.last_hash = current.start_block - 1, None
                    current.error, current.updated_at = "REORG_REBUILD", None
                    session.add(current)
                    session.commit()
                cursor.last_block, cursor.last_hash = cursor.start_block - 1, None
        low = max(cursor.start_block, cursor.last_block - self.settings.indexer_overlap_blocks + 1)
        if head < low:
            raise IncompleteHistory("No sufficiently old block yet")
        high = min(head, max(low, cursor.last_block + 1) + self.settings.indexer_block_window - 1)
        end_hash = w3.eth.get_block(high)["hash"]
        logs = discover(
            self.explorers[network].fetch,
            address,
            low,
            high,
            budget=self.settings.indexer_request_budget,
        )
        if len({tx for tx, _ in logs}) > 200:
            raise IncompleteHistory("Receipt verification budget exhausted; reduce block window")
        receipts = []
        for tx_hash in sorted({tx for tx, _ in logs}):
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if to_hex(receipt["transactionHash"]).lower() != tx_hash:
                raise IncompleteHistory("Receipt hash mismatch")
            events = decode_receipt(
                w3, client.contract, receipt, chain_id=client.chain_id, network=network
            )
            decoded = {event["log_index"]: event for event in events}
            for (tx, index), block in logs.items():
                if tx == tx_hash and (
                    index not in decoded or decoded[index]["block_number"] != block
                ):
                    raise IncompleteHistory("Explorer log absent from verified receipt")
            receipts.append((receipt, events))
        if w3.eth.get_block(high)["hash"] != end_hash:
            raise IncompleteHistory("Range changed during backfill")
        # Save only after every discovery candidate in this bounded range was verified.
        for receipt, events in receipts:
            save_events(self.store.engine, events, receipt=receipt)
        with Session(self.store.engine) as session:
            current = session.get(IndexCursor, cursor.key)
            current.last_block, current.last_hash = high, to_hex(end_hash)
            current.updated_at = now_iso()
            current.error = "BACKFILL_CATCHING_UP" if high < head else None
            session.add(current)
            session.commit()

    def health(self):
        reasons = []
        with Session(self.store.engine) as session:
            for network, client in self.vault.networks.items():
                cursor = session.get(IndexCursor, f"{network}:{client.contract.address.lower()}")
                if (
                    cursor is None
                    or cursor.error
                    or cursor.updated_at is None
                    or (
                        datetime.now(UTC) - datetime.fromisoformat(cursor.updated_at)
                    ).total_seconds()
                    > 120
                ):
                    reasons.append("INDEXER_INCOMPLETE:" + network)
        return reasons
