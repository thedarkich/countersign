import threading

from eth_account import Account
from eth_utils import to_checksum_address, to_hex

from app.chain.errors import ChainSendError
from app.chain.indexer import LABELS, REASONS, decode_receipt, save_events
from app.pipeline.agents import PaymentProposal


class TransactionWriter:
    """One instance per (chain, agent). Keep one backend process for nonce ownership."""

    def __init__(
        self,
        w3,
        contract,
        *,
        chain_id: int,
        network: str,
        explorer_url: str,
        expected_address: str,
        private_key: str,
        enabled: bool = False,
        engine=None,
    ):
        self.w3, self.contract = w3, contract
        self.chain_id, self.network, self.explorer_url = chain_id, network, explorer_url
        self.expected_address = to_checksum_address(expected_address)
        self._private_key = private_key
        self.enabled, self.engine = enabled, engine
        self._lock = threading.Lock()
        self._next_nonce = None

    def send(self, proposal: PaymentProposal, on_broadcast) -> dict:
        if not self.enabled:
            raise ChainSendError("Transactions are disabled")
        with self._lock:
            return self._send(proposal, on_broadcast)

    def _send(self, proposal: PaymentProposal, on_broadcast) -> dict:
        tx_hash = None
        try:
            account = Account.from_key(self._private_key)
            if account.address != self.expected_address or self.w3.eth.chain_id != self.chain_id:
                raise ChainSendError("Signing identity mismatch")
            if not self.w3.eth.get_code(self.contract.address):
                raise ChainSendError("Configured vault has no bytecode")
            function = self.contract.functions.pay(
                proposal.vendor_id,
                to_checksum_address(proposal.pay_to),
                proposal.po_id,
                proposal.amount_base,
                proposal.invoice_hash,
            )
            for trial in range(2):
                if self._next_nonce is None:
                    self._next_nonce = self.w3.eth.get_transaction_count(account.address, "pending")
                tx = {
                    "from": account.address,
                    "to": self.contract.address,
                    "chainId": self.chain_id,
                    "nonce": self._next_nonce,
                    "value": 0,
                    "gasPrice": self.w3.eth.gas_price,
                    "data": self.contract.encode_abi(
                        "pay",
                        args=[
                            proposal.vendor_id,
                            to_checksum_address(proposal.pay_to),
                            proposal.po_id,
                            proposal.amount_base,
                            proposal.invoice_hash,
                        ],
                    ),
                }
                try:
                    tx["gas"] = (function.estimate_gas({"from": account.address}) * 13 + 9) // 10
                except Exception:
                    tx["gas"] = 300000
                signed = account.sign_transaction(tx)
                tx_hash = to_hex(signed.hash)
                try:
                    returned = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                    if to_hex(returned) != tx_hash:
                        raise ChainSendError("RPC returned a different transaction hash", tx_hash)
                    self._next_nonce += 1
                    on_broadcast(tx_hash)
                    break
                except Exception as exc:
                    self._next_nonce = None
                    if trial == 0 and "nonce too low" in str(exc).lower():
                        continue
                    # The signed hash permits read-only reconciliation after an ambiguous timeout.
                    raise ChainSendError(
                        "Broadcast failed or acceptance is unknown", tx_hash
                    ) from None
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=30, poll_latency=0.5
            )
            if to_hex(receipt["transactionHash"]) != tx_hash:
                raise ChainSendError("Receipt transaction mismatch", tx_hash)
            events = decode_receipt(
                self.w3, self.contract, receipt, chain_id=self.chain_id, network=self.network
            )
            payments = [
                event
                for event in events
                if event["name"] in {"Paid", "Blocked"}
                and event["args"]["agent"].lower() == account.address.lower()
            ]
            if len(payments) != 1:
                raise ChainSendError("Expected one payment outcome in the receipt", tx_hash)
            event = payments[0]
            args = event["args"]
            if (
                args["vendorId"] != proposal.vendor_id
                or args["poId"] != proposal.po_id
                or args["amount"] != proposal.amount_base
                or args["invoiceHash"].lower() != proposal.invoice_hash.lower()
                or args["payTo"].lower() != proposal.pay_to.lower()
            ):
                raise ChainSendError("Receipt does not match the proposed payment", tx_hash)
            reason = None
            if event["name"] == "Blocked":
                index = args["reason"]
                if not 0 < index < len(REASONS):
                    raise ChainSendError("Unknown block reason", tx_hash)
                reason = REASONS[index]
            if self.engine is not None:
                save_events(self.engine, events)
            labels = LABELS.get(reason, (None, None))
            return {
                "hash": tx_hash,
                "explorer_url": self.explorer_url.rstrip("/") + "/tx/" + tx_hash,
                "event": event["name"],
                "reason": reason,
                "reason_label_en": labels[0],
                "reason_label_zh": labels[1],
                "network": self.network,
            }
        except ChainSendError:
            raise
        except Exception:
            self._next_nonce = None
            raise ChainSendError("Transaction processing failed", tx_hash) from None
