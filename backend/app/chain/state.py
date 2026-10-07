"""Public state from pinned-block contract views; no signing or log-range RPCs."""

from datetime import UTC, datetime

from eth_abi import decode
from eth_utils import to_hex

from app.chain.client import TOKEN_ABI, ZERO
from app.chain.errors import ChainSendError
from app.chain.indexer import decode_receipt, save_events
from app.pipeline.agents import human_amount

KINDS = ("AddVendor", "SetPayout", "AddPO", "AddAgent", "RaiseDailyCap", "Unpause", "Withdraw")
CHANGE_TYPES = (
    ("uint256", "address"),
    ("uint256", "address"),
    ("uint256", "uint256", "uint256", "uint64", "uint32"),
    ("address",),
    ("uint256",),
    (),
    ("uint256",),
)
CHANGE_FIELDS = (
    ("vendor_id", "payout"),
    ("vendor_id", "new_payout"),
    ("po_id", "vendor_id", "cap", "expiry", "period_days"),
    ("agent",),
    ("new_cap",),
    (),
    ("amount",),
)


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def read_state(vault, network, settings):
    client = vault._client(network)
    w3, contract = client.w3, client.contract
    block = w3.eth.get_block("latest")
    number = block["number"]
    if not w3.eth.get_code(contract.address, block_identifier=number):
        raise ChainSendError("Configured vault has no code")

    def read(name, *args):
        return getattr(contract.functions, name)(*args).call(
            block_identifier=number, ccip_read_enabled=False
        )

    asset = read("token")
    decimals, symbol = 18, "BOT"
    if asset.lower() != ZERO:
        token = w3.eth.contract(address=asset, abi=TOKEN_ABI)
        decimals = token.functions.decimals().call(block_identifier=number, ccip_read_enabled=False)
        symbol = token.functions.symbol().call(block_identifier=number, ccip_read_enabled=False)
    if not 0 <= decimals <= 77 or not symbol:
        raise ChainSendError("Unsupported token metadata")

    def money(value):
        return human_amount(value, decimals)

    names = {v["id"]: v for v in vault.vendor_names}
    refs = {po["po_id"]: po["ref"] for po in vault.po_names}
    vendor_ids, po_ids = set(names), set(refs)
    agent_addresses = {address.lower(): label for label, address in vault.addresses.items()}
    pending = []
    count = read("changeCount")
    if count > 1000:
        raise ChainSendError("Change history exceeds demo sync bound")
    for i in range(count):
        change_id = read("changeIds", i)
        kind, data, eta, executed, cancelled = read("getChange", change_id)
        if kind >= len(KINDS):
            raise ChainSendError("Unknown change kind")
        values = dict(zip(CHANGE_FIELDS[kind], decode(CHANGE_TYPES[kind], data), strict=True))
        if kind == 0:
            vendor_ids.add(values["vendor_id"])
        elif kind == 2:
            po_ids.add(values["po_id"])
        elif kind == 3:
            agent_addresses.setdefault(values["agent"].lower(), "other")
        if executed or cancelled:
            continue
        for field in ("cap", "new_cap", "amount"):
            if field in values:
                values[field] = money(values[field])
        if "expiry" in values:
            values["expiry"] = iso(values["expiry"])
        pending.append(
            {
                "id": to_hex(change_id),
                "kind": KINDS[kind],
                "decoded": values,
                "eta": iso(eta),
                "ready": block["timestamp"] >= eta,
            }
        )
    vendors, pos = [], []
    for vendor_id in sorted(vendor_ids):
        payout, active, exists = read("vendors", vendor_id)
        if exists:
            name = names.get(vendor_id, {})
            vendors.append(
                {
                    "id": vendor_id,
                    "payout": payout,
                    "active": active,
                    "name_en": name.get("name_en", f"Vendor {vendor_id}"),
                    "name_zh": name.get("name_zh", f"供应商 {vendor_id}"),
                }
            )
    for po_id in sorted(po_ids):
        vendor_id, cap, _, expiry, period, _, exists, closed = read("pos", po_id)
        if exists:
            pos.append(
                {
                    "po_id": po_id,
                    "ref": refs.get(po_id, f"PO-{po_id}"),
                    "vendor_id": vendor_id,
                    "cap": money(cap),
                    "remaining": money(read("poRemaining", po_id)),
                    "expiry": iso(expiry),
                    "period_days": period,
                    "closed": closed,
                }
            )
    agents = []
    for address, label in agent_addresses.items():
        checksum = w3.to_checksum_address(address)
        agents.append(
            {
                "address": checksum,
                "label": label,
                "active": read("isAgent", checksum),
                "balance": human_amount(w3.eth.get_balance(checksum, block_identifier=number), 18),
                "gas": "self",
            }
        )
    config = {
        "network": network,
        "chain_id": client.chain_id,
        # Only the public wallet RPC is exposed, never a credential-bearing server endpoint.
        "rpc_url": "https://rpc.botchain.ai" if network == "mainnet" else "https://rpc.bohr.life",
        "explorer_url": client.explorer_url,
        "contract_address": contract.address,
        "token": {"address": asset, "symbol": symbol, "decimals": decimals},
        "owner_address": read("owner"),
        "agents": dict(vault.addresses),
        "public_base_url": settings.public_base_url,
        "timelock_seconds": read("delay"),
        "bounty_network": settings.bounty_network,
    }
    registry = {
        "vendors": vendors,
        "pos": pos,
        "pending_changes": pending,
        "agents": agents,
        "daily_cap": money(read("dailyCap")),
        "remaining_today": money(read("remainingToday")),
        "vault_balance": money(read("vaultBalance")),
        "paused": read("paused"),
    }
    if w3.eth.get_block(number)["hash"] != block["hash"]:
        raise ChainSendError("State block changed while reading")
    return {
        "config": config,
        "registry": registry,
        "block_number": number,
        "block_time": iso(block["timestamp"]),
    }


def report_receipt(vault, network, tx_hash, engine):
    client = vault._client(network)
    receipt = client.w3.eth.get_transaction_receipt(tx_hash)
    if to_hex(receipt["transactionHash"]).lower() != tx_hash.lower():
        raise ChainSendError("Receipt hash mismatch")
    events = decode_receipt(
        client.w3, client.contract, receipt, chain_id=client.chain_id, network=network
    )
    save_events(engine, events, receipt=receipt)
    return events
