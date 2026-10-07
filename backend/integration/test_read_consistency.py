import asyncio

import pytest
from test_anvil import live  # noqa: F401 -- disposable real vault fixture

from app.chain.errors import ChainSendError
from app.chain.reads import PinnedReads, contract_read
from app.chain.state import read_state
from app.config import Settings


def test_batched_reads_keep_original_block_when_owner_changes_policy(live):  # noqa: F811
    w3, contract, client, _, _, _, attacker, owner_tx = live
    pinned = w3.eth.block_number
    owner_tx(contract.functions.pause())
    owner_tx(contract.functions.queueSetPayout(1, attacker))
    w3.provider.make_request("evm_increaseTime", [3])
    w3.provider.make_request("evm_mine", [])
    owner_tx(contract.functions.execute(contract.functions.changeIds(4).call()))
    with PinnedReads(w3.provider.endpoint_uri, pinned, 968) as reads:
        old = reads.many(
            {
                "paused": contract_read(contract, "paused"),
                "vendor": contract_read(contract, "vendors", 1),
            }
        )
    assert old["paused"] is False and old["vendor"][0].lower() == live[5].lower()
    new = read_state(client, "testnet", Settings(_env_file=None, scam_screening_enabled=False))
    assert new["registry"]["paused"] is True
    assert new["registry"]["vendors"][0]["payout"] == attacker


def test_public_state_still_rejects_changed_canonical_block(live, monkeypatch):  # noqa: F811
    w3, _, client, *_ = live
    original = w3.eth.get_block

    def changed(identifier, *args, **kwargs):
        result = dict(original(identifier, *args, **kwargs))
        if identifier != "latest":
            result["hash"] = bytes.fromhex("ff" * 32)
        return result

    monkeypatch.setattr(w3.eth, "get_block", changed)
    with pytest.raises(ChainSendError, match="State block changed"):
        read_state(client, "testnet", Settings(_env_file=None, scam_screening_enabled=False))


def test_snapshot_public_state_and_payment_can_run_concurrently(live):  # noqa: F811
    from test_anvil import payment

    async def run():
        return await asyncio.gather(
            live[2].snapshot("testnet"),
            asyncio.to_thread(read_state, live[2], "testnet", Settings(_env_file=None, scam_screening_enabled=False)),
            live[2].send("testnet", "guarded", payment(live), lambda _: None),
        )

    snapshot, state, receipt = asyncio.run(run())
    assert snapshot.chain_id == state["config"]["chain_id"] == 968
    assert receipt["event"] == "Paid"
    transaction = live[0].eth.get_transaction(receipt["hash"])
    assert transaction["type"] == 0 and transaction["chainId"] == 968
