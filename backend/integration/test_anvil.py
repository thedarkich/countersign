"""Explicit integration suite: forge build first, then pytest integration/.

Starts isolated loopback Anvil nodes, generates disposable test keys in memory,
and uses no project .env, real network, funded wallet or paid model.
"""

import asyncio
import json
import shutil
import socket
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest
from eth_account import Account
from sqlmodel import Session, select
from web3 import HTTPProvider, Web3

from app.chain.client import ABI, ZERO, NetworkClient, VaultClient
from app.chain.errors import ChainSendError
from app.chain.indexer import decode_receipt, save_events
from app.chain.tx_writer import TransactionWriter
from app.db import AttemptStore
from app.models import ChainEvent
from app.pipeline.agents import PaymentProposal
from app.pipeline.amounts import invoice_hash

UNIT = 10**18


@pytest.fixture
def live(tmp_path):
    executable = shutil.which("anvil")
    assert executable, "Foundry anvil must be on PATH"
    artifact_path = (
        Path(__file__).resolve().parents[2] / "contracts/out/Countersign.sol/Countersign.json"
    )
    artifact = json.loads(artifact_path.read_text())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [executable, "--host", "127.0.0.1", "--port", str(port), "--chain-id", "968", "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        w3 = Web3(
            HTTPProvider(
                f"http://127.0.0.1:{port}",
                request_kwargs={"timeout": 2},
                exception_retry_configuration=None,
            )
        )
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Local Anvil exited")
            if w3.is_connected():
                break
            time.sleep(0.05)
        assert w3.is_connected()
        owner, vendor, attacker = w3.eth.accounts[:3]
        guarded, naive = Account.create(), Account.create()

        def owner_tx(function):
            tx = function.transact({"from": owner, "gasPrice": w3.eth.gas_price, "gas": 4_000_000})
            receipt = w3.eth.wait_for_transaction_receipt(tx)
            assert receipt["status"] == 1
            return receipt

        factory = w3.eth.contract(abi=ABI, bytecode=artifact["bytecode"]["object"])
        deployed = owner_tx(factory.constructor(owner, ZERO, 2, 10 * UNIT))
        contract = w3.eth.contract(address=deployed["contractAddress"], abi=ABI)
        for recipient in (guarded.address, naive.address, contract.address):
            tx = w3.eth.send_transaction(
                {
                    "from": owner,
                    "to": recipient,
                    "value": 20 * UNIT,
                    "gasPrice": w3.eth.gas_price,
                    "gas": 100000,
                }
            )
            assert w3.eth.wait_for_transaction_receipt(tx)["status"] == 1
        expiry = w3.eth.get_block("latest")["timestamp"] + 86400
        for function in (
            contract.functions.queueAddVendor(1, vendor),
            contract.functions.queueAddPO(1, 1, 5 * UNIT, expiry, 0),
            contract.functions.queueAddAgent(guarded.address),
            contract.functions.queueAddAgent(naive.address),
        ):
            owner_tx(function)
        w3.provider.make_request("evm_increaseTime", [3])
        w3.provider.make_request("evm_mine", [])
        for index in range(4):
            owner_tx(contract.functions.execute(contract.functions.changeIds(index).call()))
        (tmp_path / "vendors.json").write_text(
            json.dumps(
                [{"id": 1, "name_en": "Local Vendor", "name_zh": "本地供应商", "aliases": []}]
            )
        )
        (tmp_path / "pos.json").write_text(
            json.dumps([{"po_id": 1, "ref": "PO-1", "vendor_id": 1}])
        )
        store = AttemptStore(tmp_path / "test.db")
        client = VaultClient(
            {"testnet": NetworkClient(w3, contract, 968, "http://local.invalid")},
            {"guarded": guarded.address, "naive": naive.address},
            {"guarded": guarded.key.hex(), "naive": naive.key.hex()},
            tmp_path,
            transactions_enabled=True,
            engine=store.engine,
        )
        yield w3, contract, client, store, guarded, vendor, attacker, owner_tx
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def payment(live, number="LOCAL-1", amount=UNIT):
    return PaymentProposal(1, live[5], 1, amount, invoice_hash(1, number))


def send(live, proposal, agent="guarded"):
    seen = []
    result = asyncio.run(live[2].send("testnet", agent, proposal, seen.append))
    assert seen == [result["hash"]]
    return result


def test_local_snapshot_payment_and_registered_destination(live):
    w3, contract, client, _, guarded, vendor, _, _ = live
    snapshot = asyncio.run(client.snapshot("testnet"))
    assert snapshot.chain_id == 968 and snapshot.decimals == 18 and snapshot.symbol == "BOT"
    assert snapshot.vendors[0].payout == vendor and snapshot.pos[0].remaining_base == 5 * UNIT
    before = w3.eth.get_balance(vendor)
    result = send(live, payment(live))
    assert result["event"] == "Paid" and result["reason"] is None
    assert w3.eth.get_balance(vendor) - before == UNIT
    assert asyncio.run(client.invoice_paid("testnet", payment(live).invoice_hash))
    transaction = w3.eth.get_transaction(result["hash"])
    assert transaction["type"] == 0 and transaction["chainId"] == 968
    assert transaction["from"] == guarded.address and transaction["to"] == contract.address
    assert "maxFeePerGas" not in transaction


def test_local_policy_blocks_and_non_policy_revert_are_distinct(live):
    w3, contract, _, _, guarded, _, attacker, owner_tx = live
    proposal = payment(live)
    assert send(live, replace(proposal, pay_to=attacker), "naive")["reason"] == "PayoutMismatch"
    assert send(live, proposal)["event"] == "Paid"
    assert send(live, replace(proposal, amount_base=2 * UNIT))["reason"] == "DuplicateInvoice"
    assert send(live, payment(live, "BIG", 6 * UNIT))["reason"] == "OverBudget"
    owner_tx(contract.functions.revokeAgent(guarded.address))
    submitted = []
    with pytest.raises(ChainSendError, match="reverted"):
        asyncio.run(live[2].send("testnet", "guarded", payment(live, "REVOKED"), submitted.append))
    assert len(submitted) == 1
    assert w3.eth.get_transaction_receipt(submitted[0])["status"] == 0


def test_concurrent_sends_use_unique_nonces_and_receipt_ingest_is_idempotent(live):
    async def batch():
        return await asyncio.gather(
            *(
                live[2].send(
                    "testnet", "guarded", payment(live, str(i), UNIT // 10), lambda _: None
                )
                for i in range(5)
            )
        )

    results = asyncio.run(batch())
    nonces = [live[0].eth.get_transaction(item["hash"])["nonce"] for item in results]
    assert sorted(nonces) == list(range(5))
    receipt = live[0].eth.get_transaction_receipt(results[0]["hash"])
    events = decode_receipt(live[0], live[1], receipt, chain_id=968, network="testnet")
    save_events(live[3].engine, events)
    save_events(live[3].engine, events)
    with Session(live[3].engine) as session:
        assert len(session.exec(select(ChainEvent)).all()) == 5


def test_wrong_signer_chain_and_emitter_fail_closed(live):
    w3, contract, client, _, guarded, vendor, _, _ = live
    writer = TransactionWriter(
        w3,
        contract,
        chain_id=968,
        network="testnet",
        explorer_url="",
        expected_address=vendor,
        private_key=guarded.key.hex(),
        enabled=True,
    )
    with pytest.raises(ChainSendError, match="identity"):
        writer.send(payment(live), lambda _: pytest.fail("must not broadcast"))
    writer.expected_address, writer.chain_id = guarded.address, 677
    with pytest.raises(ChainSendError, match="identity"):
        writer.send(payment(live), lambda _: pytest.fail("must not broadcast"))
    result = send(live, payment(live))
    receipt = dict(w3.eth.get_transaction_receipt(result["hash"]))
    receipt["to"] = vendor
    with pytest.raises(ChainSendError, match="identity"):
        decode_receipt(w3, contract, receipt, chain_id=968, network="testnet")


def test_nonce_resynchronizes_once_after_external_transaction(live):
    w3, _, _, _, guarded, vendor, _, _ = live
    send(live, payment(live))
    signed = guarded.sign_transaction(
        {
            "to": vendor,
            "value": 0,
            "gas": 21000,
            "gasPrice": w3.eth.gas_price,
            "chainId": 968,
            "nonce": w3.eth.get_transaction_count(guarded.address, "pending"),
        }
    )
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))
    result = send(live, payment(live, "SECOND"))
    assert result["event"] == "Paid" and w3.eth.get_transaction(result["hash"])["nonce"] == 2


def test_updated_payout_is_read_from_registry(live):
    w3, contract, client, _, _, _, attacker, owner_tx = live
    owner_tx(contract.functions.queueSetPayout(1, attacker))
    w3.provider.make_request("evm_increaseTime", [3])
    w3.provider.make_request("evm_mine", [])
    owner_tx(contract.functions.execute(contract.functions.changeIds(4).call()))
    assert asyncio.run(client.snapshot("testnet")).vendors[0].payout == attacker


def test_full_pipeline_clean_pays_and_naive_attack_is_blocked(live):
    from app.pipeline.ingest import ingest_text
    from app.pipeline.runner import PipelineRunner, new_attempt
    from app.schemas import Extraction, GuardVerdict, NaiveDecision

    class MockModels:
        guard_version = "v1"

        async def extract(self, document, versions):
            versions["extract"] = "mock-local-extractor"
            return Extraction(
                is_invoice=True,
                vendor_name="Local Vendor",
                invoice_number="PIPELINE-1",
                currency="BOT",
                amount_total=1,
                po_reference="PO-1",
                payee_address=live[5],
                visible_text=document.text,
            )

        async def guard(self, payload, versions):
            versions["guard"] = "mock-local-guard"
            return GuardVerdict(verdict="ok", risk=0)

        async def naive(self, payload, versions):
            versions["naive"] = "mock-local-naive"
            return NaiveDecision(
                vendor_id=1, po_id=1, pay_to=live[6], amount=1, invoice_number="PIPELINE-ATTACK"
            )

    async def scenario():
        snapshot = await live[2].snapshot("testnet")
        runner = PipelineRunner(live[3], MockModels(), live[2])
        results = []
        for agent, source in (("guarded", "team"), ("naive", "seed")):
            attempt = new_attempt(snapshot, network="testnet", agent=agent, source=source)
            live[3].save(attempt)
            results.append(await runner.run(attempt.id, ingest_text("Synthetic invoice")))
        return results

    clean, attack = asyncio.run(scenario())
    assert clean.outcome == "paid" and clean.tx["event"] == "Paid"
    assert attack.outcome == "blocked" and attack.block_reason == "PayoutMismatch"
    assert attack.ai_fooled and attack.scenario == "known_attack"
    assert live[3].get(clean.id).outcome == "paid"


def test_public_state_cache_and_owner_receipt_use_real_views(live, tmp_path):
    from app.api.schemas import AppConfig, Registry
    from app.chain.state import read_state, report_receipt
    from app.config import Settings

    w3, contract, client, store, guarded, vendor, attacker, owner_tx = live
    settings = Settings(_env_file=None, data_dir=tmp_path)
    initial = read_state(client, "testnet", settings)
    assert AppConfig.model_validate(initial["config"]).owner_address == w3.eth.accounts[0]
    assert Registry.model_validate(initial["registry"]).vault_balance == "20"
    assert initial["registry"]["pending_changes"] == []
    receipt = owner_tx(contract.functions.queueSetPayout(1, attacker))
    pending = read_state(client, "testnet", settings)["registry"]["pending_changes"]
    assert len(pending) == 1 and pending[0]["kind"] == "SetPayout"
    assert pending[0]["decoded"] == {"vendor_id": 1, "new_payout": attacker.lower()}
    events = report_receipt(
        client, "testnet", Web3.to_hex(receipt["transactionHash"]), store.engine
    )
    assert events[0]["name"] == "ChangeQueued"
    report_receipt(client, "testnet", Web3.to_hex(receipt["transactionHash"]), store.engine)
    with Session(store.engine) as session:
        assert len(session.exec(select(ChainEvent)).all()) == 1
    wrong = w3.eth.send_transaction(
        {"from": w3.eth.accounts[0], "to": vendor, "value": 1, "gasPrice": w3.eth.gas_price}
    )
    w3.eth.wait_for_transaction_receipt(wrong)
    with pytest.raises(ChainSendError):
        report_receipt(client, "testnet", Web3.to_hex(wrong), store.engine)
