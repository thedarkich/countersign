import json

import httpx
import pytest
from eth_abi import encode
from web3 import Web3

from app.chain.client import ABI
from app.chain.errors import ChainSendError
from app.chain.reads import MAX_RESPONSE_BYTES, PinnedReads, Read, balance_read, contract_read

ADDRESS = "0x" + "11" * 20
CONTRACT = Web3().eth.contract(address=ADDRESS, abi=ABI)
PRIVATE = "synthetic private endpoint token"


def invoke(handler, operations=None):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with PinnedReads("https://rpc.invalid", 123, 968, client=client) as reads:
            return reads.many(operations or {"cap": contract_read(CONTRACT, "dailyCap")})


def valid(request):
    return [
        {
            "jsonrpc": "2.0",
            "id": row["id"],
            "result": "0x3c8"
            if row["method"] == "eth_chainId"
            else "0x2a"
            if row["method"] == "eth_getBalance"
            else "0x" + encode(["uint256"], [row["id"]]).hex(),
        }
        for row in json.loads(request.content)
    ]


def test_reordered_replies_are_matched_by_id_and_all_reads_are_pinned():
    def handler(request):
        payload = json.loads(request.content)
        assert payload[0]["method"] == "eth_chainId"
        assert all(row["params"][-1] == "0x7b" for row in payload[1:])
        assert payload[1]["params"][0]["to"] == ADDRESS
        return httpx.Response(200, json=list(reversed(valid(request))))

    assert invoke(
        handler, {"cap": contract_read(CONTRACT, "dailyCap"), "balance": balance_read(ADDRESS)}
    ) == {"cap": 1, "balance": 42}


@pytest.mark.parametrize(
    "attack",
    [
        "missing",
        "duplicate",
        "unknown",
        "boolean_id",
        "string_id",
        "missing_id",
        "wrong_version",
        "rpc_error",
        "both_result_error",
        "nonarray",
        "wrong_chain",
        "malformed_json",
        "malformed_hex",
        "trailing_abi",
        "short_abi",
        "http_failure",
        "redirect",
        "oversized",
    ],
)
def test_bad_batch_fails_closed_without_retry_or_private_error(attack):
    requests = []

    def handler(request):
        requests.append(request)
        rows = valid(request)
        if attack == "missing":
            rows.pop()
        elif attack == "duplicate":
            rows[1]["id"] = 0
        elif attack == "unknown":
            rows[1]["id"] = 300
        elif attack == "boolean_id":
            rows[1]["id"] = True
        elif attack == "string_id":
            rows[1]["id"] = "1"
        elif attack == "missing_id":
            del rows[1]["id"]
        elif attack == "wrong_version":
            rows[1]["jsonrpc"] = "1.0"
        elif attack == "rpc_error":
            del rows[1]["result"]
            rows[1]["error"] = {"message": PRIVATE, "code": -32000}
        elif attack == "both_result_error":
            rows[1]["error"] = {"message": PRIVATE, "code": -32000}
        elif attack == "nonarray":
            rows = {"error": PRIVATE}
        elif attack == "wrong_chain":
            rows[0]["result"] = "0x2a5"
        elif attack == "malformed_json":
            return httpx.Response(200, content=PRIVATE)
        elif attack == "malformed_hex":
            rows[1]["result"] = "0xxyz"
        elif attack == "trailing_abi":
            rows[1]["result"] += "00" * 32
        elif attack == "short_abi":
            rows[1]["result"] = "0x01"
        elif attack == "http_failure":
            return httpx.Response(500, content=PRIVATE)
        elif attack == "redirect":
            return httpx.Response(302, headers={"Location": "https://elsewhere.invalid/" + PRIVATE})
        elif attack == "oversized":
            return httpx.Response(200, content=b" " * (MAX_RESPONSE_BYTES + 1))
        return httpx.Response(200, json=rows)

    with pytest.raises(ChainSendError) as error:
        invoke(handler)
    assert PRIVATE not in str(error.value)
    assert len(requests) == 1


def test_large_read_phase_is_chunked_with_identity_check_each_time():
    sizes = []

    def handler(request):
        rows = json.loads(request.content)
        sizes.append(len(rows))
        assert rows[0]["method"] == "eth_chainId"
        return httpx.Response(200, json=valid(request))

    result = invoke(handler, {i: balance_read(ADDRESS) for i in range(130)})
    assert sizes == [64, 64, 5] and result == dict.fromkeys(range(130), 42)


def test_later_chunk_failure_returns_no_partial_state():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        rows = valid(request)
        if count == 2:
            rows[0]["result"] = "0x2a5"
        return httpx.Response(200, json=rows)

    with pytest.raises(ChainSendError):
        invoke(handler, {i: balance_read(ADDRESS) for i in range(130)})
    assert count == 2


def test_writes_and_unbounded_phases_are_rejected_before_http():
    def never(request):
        pytest.fail("No network request is permitted")

    with pytest.raises(ValueError, match="views"):
        contract_read(CONTRACT, "pause")
    with pytest.raises(ChainSendError, match="read methods"):
        invoke(never, {"write": Read("eth_sendRawTransaction", ("0x123",))})
    with pytest.raises(ChainSendError, match="limit"):
        invoke(never, {i: balance_read(ADDRESS) for i in range(4001)})


def test_tuple_and_dynamic_string_decode_preserves_values():
    change = (1, b"encoded-owner-change", 12345, False, True)
    string_abi = [
        {
            "type": "function",
            "name": "symbol",
            "stateMutability": "view",
            "inputs": [],
            "outputs": [{"type": "string"}],
        }
    ]
    token = Web3().eth.contract(address=ADDRESS, abi=string_abi)

    def handler(request):
        rows = valid(request)
        rows[1]["result"] = "0x" + encode(["(uint8,bytes,uint64,bool,bool)"], [change]).hex()
        rows[2]["result"] = "0x" + encode(["string"], ["USDT"]).hex()
        return httpx.Response(200, json=rows)

    assert invoke(
        handler,
        {
            "change": contract_read(CONTRACT, "getChange", bytes(32)),
            "symbol": contract_read(token, "symbol"),
        },
    ) == {"change": change, "symbol": "USDT"}
