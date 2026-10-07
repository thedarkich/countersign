"""Read-only reconciliation. This module never signs or broadcasts a transaction."""

from eth_utils import to_hex
from sqlalchemy import func
from sqlmodel import Session, select
from web3.exceptions import TransactionNotFound

from app.chain.client import TOKEN_ABI, ZERO
from app.chain.errors import ChainSendError
from app.chain.indexer import LABELS, REASONS, decode_receipt, save_events
from app.models import Attempt, ChainEvent, EventAudit, ReceiptAnchor, RecoveryCheck, now_iso
from app.pipeline.amounts import to_base_units


def invalidate(session, network, vault, *, tx_hash=None, reason="REORG_REVIEW_REQUIRED"):
    """Archive replaced evidence before removing it from the current read model."""
    query = select(ChainEvent).where(
        ChainEvent.network == network, ChainEvent.contract_address == vault
    )
    if tx_hash:
        query = query.where(ChainEvent.tx_hash == tx_hash)
    for event in session.exec(query).all():
        session.add(EventAudit(reason=reason, payload=event.model_dump()))
        session.delete(event)
    anchors = select(ReceiptAnchor).where(
        ReceiptAnchor.network == network, ReceiptAnchor.contract_address == vault
    )
    if tx_hash:
        anchors = anchors.where(ReceiptAnchor.tx_hash == tx_hash)
    for anchor in session.exec(anchors).all():
        session.delete(anchor)
    attempts = select(Attempt).where(
        Attempt.network == network,
        Attempt.contract_address == vault,
        Attempt.status.in_(["done", "error"]),
        Attempt.outcome.in_(["paid", "blocked"]),
    )
    if tx_hash:
        attempts = attempts.where(Attempt.tx_hash == tx_hash)
    for attempt in session.exec(attempts).all():
        attempt.status = attempt.outcome = "error"
        attempt.error, attempt.tx, attempt.block_reason, attempt.ai_fooled = (
            reason,
            None,
            None,
            False,
        )
        attempt.steps = [
            dict(step, status="failed", detail=reason, ended_at=now_iso())
            if step["name"] == "chain"
            else step
            for step in attempt.steps
        ]
        session.add(attempt)


class Reconciler:
    def __init__(self, vault, store):
        self.vault, self.store = vault, store

    def _receipt(self, attempt):
        client = self.vault._client(attempt.network)
        if (
            attempt.chain_id != client.chain_id
            or attempt.contract_address != client.contract.address.lower()
        ):
            raise ChainSendError("Recovery identity mismatch")
        receipt = client.w3.eth.get_transaction_receipt(attempt.tx_hash)
        if (
            to_hex(receipt["transactionHash"]).lower() != attempt.tx_hash.lower()
            or (receipt.get("to") or "").lower() != attempt.contract_address
            or (receipt.get("from") or "").lower() != attempt.agent_address
        ):
            raise ChainSendError("Recovery identity mismatch")
        block = client.w3.eth.get_block(receipt["blockNumber"])
        if block["hash"] != receipt["blockHash"]:
            raise ChainSendError("Noncanonical receipt")
        # Validate the original calldata even on a revert. A hash alone isn't attribution.
        tx = client.w3.eth.get_transaction(attempt.tx_hash)
        if (
            to_hex(tx["hash"]).lower() != attempt.tx_hash.lower()
            or tx["from"].lower() != attempt.agent_address
            or (tx.get("to") or "").lower() != attempt.contract_address
        ):
            raise ChainSendError("Recovery transaction mismatch")
        function, args = client.contract.decode_function_input(tx["input"])
        proposal = attempt.proposal or {}
        amount = proposal.get("amount_base")
        if amount is None:  # Older attempts saved only human units; read the immutable vault asset.
            asset = client.contract.functions.token().call(
                block_identifier=receipt["blockNumber"], ccip_read_enabled=False
            )
            decimals = (
                18
                if asset.lower() == ZERO
                else client.w3.eth.contract(address=asset, abi=TOKEN_ABI)
                .functions.decimals()
                .call(block_identifier=receipt["blockNumber"], ccip_read_enabled=False)
            )
            amount = to_base_units(proposal["amount"], decimals)
        expected = {
            "vendorId": proposal["vendor_id"],
            "poId": proposal["po_id"],
            "amount": int(amount),
            "payTo": proposal["pay_to"].lower(),
            "invoiceHash": proposal["invoice_hash"].lower(),
        }
        if (
            function.fn_name != "pay"
            or args["vendorId"] != expected["vendorId"]
            or args["poId"] != expected["poId"]
            or args["amount"] != expected["amount"]
            or args["payTo"].lower() != expected["payTo"]
            or to_hex(args["invoiceHash"]).lower() != expected["invoiceHash"]
        ):
            raise ChainSendError("Recovery proposal mismatch")
        events = (
            []
            if receipt["status"] == 0
            else decode_receipt(
                client.w3,
                client.contract,
                receipt,
                chain_id=client.chain_id,
                network=attempt.network,
            )
        )
        if receipt["status"] not in {0, 1}:
            raise ChainSendError("Invalid receipt status")
        payments = [e for e in events if e["name"] in {"Paid", "Blocked"}]
        event = payments[0] if len(payments) == 1 else None
        if receipt["status"] == 1:
            if event is None or event["args"]["agent"].lower() != attempt.agent_address:
                raise ChainSendError("Recovery event mismatch")
            for key, value in expected.items():
                actual = event["args"][key]
                if (actual.lower() if isinstance(actual, str) else actual) != value:
                    raise ChainSendError("Recovery event mismatch")
        return client, receipt, events, event

    def reconcile(self, attempt_id):
        attempt = self.store.get(attempt_id)
        if not attempt.tx_hash or attempt.status not in {"done", "error"}:
            return "not_eligible"
        try:
            client, receipt, events, event = self._receipt(attempt)
        except TransactionNotFound:
            self._check_orphan(attempt)
            return self._record(attempt_id, "pending_or_unavailable")
        except Exception:
            # Preserve existing evidence on an RPC outage; never invent a new outcome.
            return self._record(attempt_id, "receipt_unverified")
        reason = None
        if event and event["name"] == "Blocked":
            number = event["args"]["reason"]
            if not isinstance(number, int) or not 0 < number < len(REASONS):
                return self._record(attempt_id, "receipt_unverified")
            reason = REASONS[number]
        with Session(self.store.engine) as session:
            current = session.get(Attempt, attempt_id)
            if current.tx_hash != attempt.tx_hash or current.status not in {"done", "error"}:
                return "changed"
            current.ai_fooled = current.source in {"bounty", "seed"}
            if event:
                labels = LABELS.get(reason, (None, None))
                current.status, current.outcome, current.error = "done", event["name"].lower(), None
                current.block_reason = reason
                current.tx = {
                    "hash": current.tx_hash,
                    "network": current.network,
                    "explorer_url": client.explorer_url.rstrip("/") + "/tx/" + current.tx_hash,
                    "event": event["name"],
                    "reason": reason,
                    "reason_label_en": labels[0],
                    "reason_label_zh": labels[1],
                }
            else:
                current.status = current.outcome = "error"
                current.error, current.tx, current.block_reason = "TRANSACTION_REVERTED", None, None
            current.steps = [
                dict(
                    step,
                    status="done" if event else "failed",
                    detail="Recovered from verified receipt" if event else current.error,
                    ended_at=now_iso(),
                )
                if step["name"] == "chain"
                else step
                for step in current.steps
            ]
            session.add(current)
            session.commit()
        save_events(self.store.engine, events, receipt=receipt)
        return self._record(attempt_id, "recovered" if event else "reverted")

    def _record(self, attempt_id, result):
        with Session(self.store.engine) as session:
            session.merge(RecoveryCheck(attempt_id=attempt_id, result=result))
            session.commit()
        return result

    def _check_orphan(self, attempt):
        key = f"{attempt.network}:{attempt.contract_address}:{attempt.tx_hash}"
        with Session(self.store.engine) as session:
            anchor = session.get(ReceiptAnchor, key)
            if anchor is None:
                return
            try:
                client = self.vault._client(attempt.network)
                block = client.w3.eth.get_block(anchor.block_number)
            except Exception:
                return
            if to_hex(block["hash"]).lower() != anchor.block_hash.lower():
                invalidate(
                    session, attempt.network, attempt.contract_address, tx_hash=attempt.tx_hash
                )
                session.commit()

    def run(self, limit=20):
        with Session(self.store.engine) as session:
            ids = session.exec(
                select(Attempt.id)
                .outerjoin(RecoveryCheck, RecoveryCheck.attempt_id == Attempt.id)
                .where(Attempt.tx_hash.is_not(None), Attempt.status.in_(["done", "error"]))
                .order_by(
                    func.coalesce(RecoveryCheck.checked_at, ""), Attempt.created_at, Attempt.id
                )
                .limit(limit)
            ).all()
        return [self.reconcile(attempt_id) for attempt_id in ids]
