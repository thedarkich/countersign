from datetime import UTC, datetime

from eth_utils import to_hex
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from web3.logs import DISCARD

from app.chain.errors import ChainSendError
from app.models import ChainEvent, EventAudit, ReceiptAnchor, now_iso

REASONS = (
    "None",
    "Paused",
    "ZeroAmount",
    "UnknownVendor",
    "VendorInactive",
    "PayoutMismatch",
    "UnknownPO",
    "POVendorMismatch",
    "POExpired",
    "OverBudget",
    "DuplicateInvoice",
    "OverDailyCap",
    "InsufficientFunds",
)
LABELS = {
    "Paused": ("Vault is paused", "金库已暂停"),
    "ZeroAmount": ("Amount is zero", "金额为零"),
    "UnknownVendor": ("Unknown vendor", "未知供应商"),
    "VendorInactive": ("Vendor is inactive", "供应商已停用"),
    "PayoutMismatch": ("Payout differs from registry", "收款地址与登记地址不同"),
    "UnknownPO": ("Unknown purchase order", "未知采购订单"),
    "POVendorMismatch": ("Purchase order belongs to another vendor", "订单属于其他供应商"),
    "POExpired": ("Purchase order expired or closed", "订单已到期或关闭"),
    "OverBudget": ("Purchase order budget exceeded", "超过订单预算"),
    "DuplicateInvoice": ("Invoice already paid", "发票已支付"),
    "OverDailyCap": ("Daily cap exceeded", "超过每日限额"),
    "InsufficientFunds": ("Insufficient vault balance", "金库余额不足"),
}


def json_value(value):
    if isinstance(value, bytes):
        return to_hex(value)
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def decode_receipt(w3, contract, receipt, *, chain_id: int, network: str) -> list[dict]:
    """Only call with receipts fetched from this configured chain's RPC."""
    destination = receipt.get("to") or receipt.get("contractAddress") or ""
    if w3.eth.chain_id != chain_id or destination.lower() != contract.address.lower():
        raise ChainSendError("Receipt identity mismatch")
    if receipt["status"] != 1:
        raise ChainSendError("Transaction reverted", to_hex(receipt["transactionHash"]))
    block = w3.eth.get_block(receipt["blockNumber"])
    if block["hash"] != receipt["blockHash"]:
        raise ChainSendError("Receipt block is no longer canonical")
    timestamp = datetime.fromtimestamp(block["timestamp"], UTC).isoformat()
    events = []
    for entry in contract.abi:
        if entry.get("type") != "event":
            continue
        for log in getattr(contract.events, entry["name"])().process_receipt(
            receipt, errors=DISCARD
        ):
            if log["address"].lower() != contract.address.lower():
                continue
            if (
                log["transactionHash"] != receipt["transactionHash"]
                or log["blockHash"] != receipt["blockHash"]
            ):
                raise ChainSendError("Event identity mismatch")
            events.append(
                {
                    "network": network,
                    "contract_address": contract.address.lower(),
                    "tx_hash": to_hex(receipt["transactionHash"]),
                    "log_index": log["logIndex"],
                    "block_number": receipt["blockNumber"],
                    "block_time": timestamp,
                    "name": log["event"],
                    "args": json_value(log["args"]),
                }
            )
    return sorted(events, key=lambda item: item["log_index"])


def save_events(engine, events: list[dict], *, receipt=None):
    with engine.begin() as connection:
        if events and receipt is not None:
            first = events[0]
            criteria = (
                ChainEvent.network == first["network"],
                ChainEvent.contract_address == first["contract_address"],
                ChainEvent.tx_hash == first["tx_hash"],
            )
            fresh = {event["log_index"]: event for event in events}
            for old in connection.execute(select(ChainEvent.__table__).where(*criteria)).mappings():
                new = fresh.get(old["log_index"])
                if new is None or any(old[key] != value for key, value in new.items()):
                    connection.execute(
                        insert(EventAudit).values(
                            recorded_at=now_iso(), reason="RECEIPT_CORRECTION", payload=dict(old)
                        )
                    )
                if new is None:
                    connection.execute(delete(ChainEvent).where(ChainEvent.id == old["id"]))
        for event in events:
            connection.execute(
                insert(ChainEvent)
                .values(**event)
                .on_conflict_do_update(
                    index_elements=["network", "contract_address", "tx_hash", "log_index"],
                    set_={
                        key: value
                        for key, value in event.items()
                        if key not in {"network", "contract_address", "tx_hash", "log_index"}
                    },
                )
            )
        if events and receipt is not None:
            first = events[0]
            values = {
                "key": f"{first['network']}:{first['contract_address']}:{first['tx_hash']}",
                "network": first["network"],
                "contract_address": first["contract_address"],
                "tx_hash": first["tx_hash"],
                "block_number": receipt["blockNumber"],
                "block_hash": to_hex(receipt["blockHash"]),
            }
            connection.execute(
                insert(ReceiptAnchor)
                .values(**values)
                .on_conflict_do_update(index_elements=["key"], set_=values)
            )
