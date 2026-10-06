"""Verify and record public testnet receipts. No credentials or .env are loaded."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.chain.indexer import REASONS, decode_receipt, save_events  # noqa: E402
from app.db import AttemptStore  # noqa: E402
from app.pipeline.amounts import invoice_hash  # noqa: E402


def main():
    report_path = ROOT / "docs/deployments/testnet.json"
    report = json.loads(report_path.read_text())
    assert report["chain_id"] == 968
    w3 = Web3(
        HTTPProvider(
            "https://rpc.bohr.life",
            request_kwargs={"timeout": 20},
            exception_retry_configuration=None,
        )
    )
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.eth.chain_id == 968
    contract = w3.eth.contract(
        address=report["contract_address"],
        abi=json.loads((ROOT / "backend/app/chain/abi/Countersign.json").read_text()),
    )
    stages = {}
    for name, count in (("Setup.s.sol", 8), ("Execute.s.sol", 8), ("TestnetProof.s.sol", 4)):
        artifact = json.loads(
            (ROOT / f"contracts/broadcast/{name}/968/run-latest.json").read_text()
        )
        hashes = [tx["hash"] for tx in artifact["transactions"]]
        assert len(hashes) == count, f"Unexpected transaction count for {name}"
        stages[name] = hashes

    def verify(tx_hash):
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        assert receipt["status"] == 1
        return decode_receipt(w3, contract, receipt, chain_id=968, network="testnet")

    hashes = [tx for group in stages.values() for tx in group]
    with ThreadPoolExecutor(max_workers=4) as pool:
        groups = list(pool.map(verify, hashes))
    events = [event for group in groups for event in group]
    queued = {event["args"]["id"]: event for event in events if event["name"] == "ChangeQueued"}
    executed = [event for event in events if event["name"] == "ChangeExecuted"]
    assert len(queued) == len(executed) == 8
    for event in executed:
        original = queued[event["args"]["id"]]
        queued_time = int(datetime.fromisoformat(original["block_time"]).timestamp())
        execution_time = int(datetime.fromisoformat(event["block_time"]).timestamp())
        # ETA is computed from each queued transaction's own block timestamp.
        assert original["args"]["eta"] == queued_time + 120
        assert execution_time >= original["args"]["eta"]

    payments = [event for event in events if event["name"] in {"Paid", "Blocked"}]
    assert len(payments) == 4
    evidence = {}
    for event in payments:
        reason = "Paid" if event["name"] == "Paid" else REASONS[event["args"]["reason"]]
        assert reason not in evidence
        receipt = w3.eth.get_transaction_receipt(event["tx_hash"])
        transaction = w3.eth.get_transaction(event["tx_hash"])
        assert transaction["type"] == 0 and transaction["chainId"] == 968
        assert receipt["from"].lower() == event["args"]["agent"].lower()
        evidence[reason] = event
    assert set(evidence) == {"Paid", "PayoutMismatch", "OverBudget", "DuplicateInvoice"}
    expected_invoice = invoice_hash(1, "CSLIVE20261006A")
    assert evidence["Paid"]["args"]["invoiceHash"] == expected_invoice
    assert evidence["DuplicateInvoice"]["args"]["invoiceHash"] == expected_invoice
    assert evidence["Paid"]["args"]["amount"] == 100000
    assert evidence["DuplicateInvoice"]["args"]["amount"] == 200000
    assert evidence["Paid"]["args"]["payTo"].lower() == "0x419d0c4f429981b45548724404e5a2cefcb303d0"
    assert (
        evidence["PayoutMismatch"]["args"]["payTo"].lower()
        == "0x3135ee6aa8e71e2e51e56314f23c7a96c72df47b"
    )
    assert w3.eth.get_transaction_receipt(report["funding_tx"])["status"] == 1
    assert contract.functions.vaultBalance().call() == 19900000
    assert contract.functions.poRemaining(1).call() == 9900000
    assert contract.functions.poRemaining(2).call() == 5000000
    assert contract.functions.poRemaining(3).call() == 3000000
    assert contract.functions.remainingToday().call() == 14900000
    for agent in (
        "0x10840Aea6D6f835560f43656768a0d5B2A4ef063",
        "0x8CF8109e5817fACB3235c01E93E233BF478c0659",
    ):
        assert contract.functions.isAgent(agent).call()
    token = w3.eth.contract(
        address=report["token"],
        abi=[
            {
                "type": "function",
                "name": "balanceOf",
                "stateMutability": "view",
                "inputs": [{"name": "account", "type": "address"}],
                "outputs": [{"name": "", "type": "uint256"}],
            }
        ],
    )
    assert token.functions.balanceOf("0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b").call() == 0
    store = AttemptStore(ROOT / "data/countersign.db")
    save_events(store.engine, events)
    report.update(
        evidence=evidence,
        execute_txs=stages["Execute.s.sol"],
        timelock_verified=True,
        testnet_proof_complete=True,
        vault_balance_base="19900000",
        remaining_today_base="14900000",
        provenance="Direct scripted contract proof; no AI calls or AI-fooled claim.",
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "contract": report["contract_address"],
                "source_verified": report["source_verified"],
                "timelock_verified": True,
                "vault_balance_tusdt": "19.9",
                "evidence": {name: value["tx_hash"] for name, value in evidence.items()},
                "indexed_events": len(events),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
