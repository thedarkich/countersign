"""Bounded, read-only RPC batches pinned to a caller-verified block.

No signer, RPC writes, CCIP redirects, retries or shared Web3 batching state.
The caller still checks vault bytecode and the block hash before returning data.
"""

import json
import re
from dataclasses import dataclass

import httpx
from eth_abi import decode, encode
from eth_utils import to_checksum_address
from eth_utils.abi import get_abi_output_types

from app.chain.errors import ChainSendError

MAX_BATCH_READS = 63  # plus one fresh chain-ID check in every HTTP batch
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Read:
    method: str
    params: tuple
    outputs: tuple[str, ...] | None = None


def contract_read(contract, name, *args):
    function = contract.get_function_by_name(name)
    if function.abi.get("stateMutability") not in {"view", "pure"}:
        raise ValueError("Only contract views may be batched")
    return Read(
        "eth_call",
        ({"to": contract.address, "data": contract.encode_abi(name, args=list(args))},),
        tuple(get_abi_output_types(function.abi)),
    )


def balance_read(address):
    return Read("eth_getBalance", (to_checksum_address(address),))


def quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)", value):
        raise ValueError("Invalid RPC quantity")
    return int(value, 16)


class PinnedReads:
    def __init__(self, endpoint, block, chain_id, *, client=None):
        if type(block) is not int or block < 0 or chain_id not in {677, 968}:
            raise ValueError("Invalid pinned read identity")
        self.endpoint, self.block, self.chain_id = endpoint, hex(block), chain_id
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)
        self.owns_client = client is None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.owns_client:
            self.client.close()

    def many(self, operations):
        if len(operations) > 4000:
            raise ChainSendError("Pinned read phase exceeds limit")
        items, output = list(operations.items()), {}
        # Validate the whole phase before issuing any request. Read objects are
        # application-owned; arbitrary RPC methods are never accepted here.
        for _, operation in items:
            if operation.method not in {"eth_call", "eth_getBalance"}:
                raise ChainSendError("Only pinned read methods are permitted")
        try:
            for start in range(0, len(items), MAX_BATCH_READS):
                chunk = items[start : start + MAX_BATCH_READS]
                requests = [{"jsonrpc": "2.0", "id": 0, "method": "eth_chainId", "params": []}]
                requests.extend(
                    {
                        "jsonrpc": "2.0",
                        "id": index,
                        "method": operation.method,
                        "params": [*operation.params, self.block],
                    }
                    for index, (_, operation) in enumerate(chunk, 1)
                )
                with self.client.stream("POST", self.endpoint, json=requests) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    for data in response.iter_bytes(chunk_size=65536):
                        raw.extend(data)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise ValueError("RPC batch response exceeds limit")
                results = self._responses(json.loads(raw), len(requests))
                if quantity(results[0]) != self.chain_id:
                    raise ValueError("RPC chain identity changed")
                for index, (key, operation) in enumerate(chunk, 1):
                    value = results[index]
                    if operation.method == "eth_getBalance":
                        output[key] = quantity(value)
                        continue
                    if not isinstance(value, str) or not re.fullmatch(
                        r"0x(?:[0-9a-fA-F]{2})*", value
                    ):
                        raise ValueError("Invalid RPC ABI result")
                    encoded = bytes.fromhex(value[2:])
                    decoded = decode(operation.outputs, encoded)
                    # Reject noncanonical offsets, trailing bytes and malformed ABI.
                    if encode(operation.outputs, decoded) != encoded:
                        raise ValueError("Noncanonical RPC ABI result")
                    output[key] = decoded[0] if len(decoded) == 1 else decoded
            return output
        except Exception:
            # RPC errors may contain a credential-bearing endpoint or provider body.
            raise ChainSendError("Pinned RPC batch failed validation or transport") from None

    @staticmethod
    def _responses(payload, count):
        if not isinstance(payload, list) or len(payload) != count:
            raise ValueError("Incomplete RPC batch")
        results = {}
        for row in payload:
            if not isinstance(row, dict) or row.get("jsonrpc") != "2.0":
                raise ValueError("Invalid RPC envelope")
            index = row.get("id")
            if type(index) is not int or not 0 <= index < count or index in results:
                raise ValueError("Unexpected or duplicate RPC identity")
            if "result" not in row or "error" in row:
                raise ValueError("RPC read failed")
            results[index] = row["result"]
        return results
