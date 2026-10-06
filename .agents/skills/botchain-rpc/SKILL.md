---
name: botchain-rpc
description: "Use when calling BOT Chain JSON-RPC endpoints, checking which RPC methods are supported, reading blob sidecars, handling gas fees and gas price, debugging transaction issues, or hitting API limits/error codes on the BOT Chain EVM Layer 1 (chainId 677/968). Triggers: \"botchain rpc\", \"eth_getBlobSidecars\", \"rpc.botchain.ai\", \"eth_getLogs disabled\", \"bot chain gas\"."
---

# BOT Chain - JSON-RPC, Gas & Blob API

BOT Chain's JSON-RPC is **Geth-compatible** (and BSC-flavored). This skill documents
endpoints, supported methods, BOT-specific methods, gas behavior, and API restrictions.

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai) (JSON-RPC endpoints page)
> and verified against the live RPC endpoints. When extending this skill, only pull
> from these sources.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Network parameters | `botchain-network` | Chain IDs, RPC/WSS endpoints, wallet setup |
| Gas sponsorship | `botchain-paymaster` | Zero-gas txs, `pm_isSponsorable`, bundlers |
| Self-run nodes | `botchain-nodes` | Exposing `debug_*` or `eth_getLogs` yourself |

## Endpoints

| Network | HTTP | WSS |
|---|---|---|
| Mainnet (677) | `https://rpc.botchain.ai` | `wss://ws-rpc.botchain.ai` |
| Testnet (968) | `https://rpc.bohr.life` | `wss://ws-rpc.bohr.life` |
| ERC-4337 bundler (mainnet) | `https://bundler.botchain.ai/rpc` | - |
| ERC-4337 bundler (testnet) | `https://bundler.bohr.life/rpc` | - |

> Debug RPCs (`rpc-debug.botchain.ai`, `ws-rpc-debug.botchain.ai`) are internal-only,
> not publicly reachable. `debug_*` methods return `-32601` on public endpoints.

## Verification examples

```bash
# chain id
curl -s https://rpc.botchain.ai -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# => {"jsonrpc":"2.0","id":1,"result":"0x2a5"}  (677 mainnet)

curl -s https://rpc.bohr.life -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# => {"jsonrpc":"2.0","id":1,"result":"0x3c8"}  (968 testnet)

curl -s https://rpc.botchain.ai -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
```

## Method support & restrictions

- **Geth-compatible**: `eth_*`, `net_*`, `web3_*`, `txpool_*`, plus PubSub (`eth_subscribe`) and BSC-specific methods (`eth_getFinalizedHeader`, `eth_getBlobSidecars`, `eth_health`, `eth_simulateV1`).
- **`eth_getLogs` is DISABLED on mainnet public endpoints.** Use WSS subscriptions or third-party endpoints (Covalent/Alchemy) for log-heavy indexing.
- **No EIP-1559.** `baseFeePerGas` is `0x0`; fee model is flat/BSC-style. Observed `eth_gasPrice` ~50 Gwei (live 2026; explorer reports ~29 Gwei).
- **Consensus**: Parlia (BEP-126 finality, BEP-341 multi-block proposers). Blocks can be sealed by a validator producing several consecutive blocks.
- Finality: wait for blocks sealed by >⅔·N+1 validators; with slashing, ½·N+1 blocks suffice. Fast Finality (Plato upgrade) finalizes within two blocks when ≥⅔·N validators vote.

## BOT-specific / blob methods (EIP-4844)

BOT Chain implements **EIP-4844 Shard Blob Transactions**.

### `eth_getBlobSidecarByTxHash`
```bash
curl -X POST http://localhost:8545/ -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBlobSidecarByTxHash","params":["0x377d3615d2e76f4dcc0c9a1674d2f5487cba7644192e7a4a5af9fe5f08b60a63"],"id":1}'
# full_blob_flag (optional, default true); false returns only first 32 bytes of each blob
curl -X POST http://localhost:8545/ -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBlobSidecarByTxHash","params":["0x377d3615d2e76f4dcc0c9a1674d2f5487cba7644192e7a4a5af9fe5f08b60a63", false],"id":1}'
```

### `eth_getBlobSidecars`
`blockNumber`: hex block number | hex block hash | `"earliest" | "latest" | "safe" | "finalized"`.
```bash
curl -X POST http://localhost:8545/ -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBlobSidecars","params":["latest"],"id":1}'
curl -X POST http://localhost:8545/ -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBlobSidecars","params":["0xc5043f", false],"id":1}'
```

Response shape (per element): `blobSidecar { blobs[], commitments[], proofs[] }`, `blockHash`, `blockNumber`, `txHash`, `txIndex`. Verified live: returns `[]` for blocks without blob txs.

## Error codes & troubleshooting

Standard Geth JSON-RPC error codes apply:

| Code | Meaning | Example |
|---|---|---|
| `-32601` | Method not found / not available | `debug_*`, `pm_isSponsorable` on the bundler endpoint |
| `-32602` | Invalid params | wrong arg count/types |
| `-32000` | Execution/revert-style errors | out-of-gas, nonce too low, insufficient funds |

Common issues:
- **`eth_getLogs` returns `[]` on mainnet** → logs filtered; use WSS or third-party indexers.
- **`eth_sendRawTransaction` with EIP-1559 fields** → chain has no EIP-1559; send legacy or use defaults; `--rpc.allow-unprotected-txs` needed for non-EIP-155 protected txs on a self-hosted node.
- **Low/zero gas price txs** → see the `botchain-paymaster` skill (EOA Paymaster sponsorship).

## Paymaster / bundler methods

- EOA Paymaster (BEP-414): `pm_isSponsorable` + `eth_sendRawTransaction`. See `botchain-paymaster`.
- ERC-4337 bundlers expose `eth_supportedEntryPoints` → `0x0000000071727De22E5E9d8BAF0edAC6f37da032` (EntryPoint v0.7) and standard `eth_sendUserOperation`/`eth_estimateUserOperationGas`.

## Gas guidance for deployments

- Fund the deployer with ~0.1-0.5 BOT on testnet (faucet) - plenty for many deploys at ~$0.01-0.10/tx.
- Blocks are 0.75s, so confirmations are fast; 1-2 blocks of confirmations are generally sufficient for UI purposes; use finality semantics (⅔·N+1 seals) for high-value flows.
