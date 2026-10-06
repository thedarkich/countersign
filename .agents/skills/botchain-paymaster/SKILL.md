---
name: botchain-paymaster
description: "Use when integrating gas sponsorship / gasless transactions on BOT Chain via the EOA Paymaster (BEP-414, pm_isSponsorable), or the ERC-4337 bundler (EntryPoint v0.7) endpoints bundler.botchain.ai and bundler.bohr.life. Triggers: \"bot chain paymaster\", \"gasless botchain\", \"pm_isSponsorable\", \"zero gas price\", \"sponsored transaction\"."
---

# BOT Chain - EOA Paymaster & ERC-4337 Bundlers

BOT Chain offers two ways to sponsor user gas:

1. **EOA Paymaster** (BEP-414) - sponsors ordinary EOA transactions (no smart-contract wallet needed).
2. **ERC-4337** - standard Account Abstraction with bundlers on both networks (EntryPoint v0.7).

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai) (paymaster page), the
> [BEP-414 specification](https://github.com/bnb-chain/BEPs), and verified against the
> live bundler endpoints. When extending this skill, only pull from these sources.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| RPC methods & gas | `botchain-rpc` | RPC error codes, gas price, EIP-1559 absence |
| Network parameters | `botchain-network` | Endpoints and chain IDs |

## 1. EOA Paymaster (BEP-414) - how it works

This is NOT the EIP-4337 paymaster. It works for standard EOAs:

1. **User initiates** a tx; the wallet calls `pm_isSponsorable` first.
2. If sponsorable, the wallet sets the tx **gas price to zero** and submits it to the Paymaster via `eth_sendRawTransaction`.
3. The Paymaster checks its **Sponsor Policy** (sender/recipient/token/limits whitelists).
4. If eligible: Paymaster creates a **sponsor tx** with a higher gas price, bundles it atomically with the user tx, and submits to MEV builders (PBS, BEP-322).
5. The proposer picks the most profitable block; both txs execute atomically.
6. The Paymaster Manager deducts the sponsored gas from the sponsor account.

### RPC methods

**`pm_isSponsorable`** - check eligibility before touching gas price.
```json
{
  "jsonrpc": "2.0", "id": 1, "method": "pm_isSponsorable",
  "params": [{
    "to": "0x...",
    "from": "0x...",
    "value": "0x1b4",
    "data": "0x",
    "gas": "0x101b4"
  }]
}
```
Response:
```json
{
  "jsonrpc": "2.0", "id": 1,
  "result": { "Sponsorable": true, "SponsorPolicy": "a sample policy name" }
}
```
(BEP-414 canonical schema uses lower-case `sponsorable` plus optional `sponsorName`, `sponsorIcon`, `sponsorWebsite`; return `sponsorable: false` when not eligible.)

**`eth_sendRawTransaction`** - submit the signed zero-gas tx (standard Ethereum spec). Response is the 32-byte tx hash:
```json
{ "id": 1, "jsonrpc": "2.0",
  "result": "0xe670ec64341771606e55d6b4ca35a1a6b75ee3d5145a99d05921026d1527331" }
```

### Wallet integration steps
1. Call `pm_isSponsorable` before modifying gas prices.
2. Notify the user the tx is gas-free, sponsored by the returned policy name.
3. Sign the zero-gas-price tx.
4. Submit via `eth_sendRawTransaction` to the Paymaster endpoint.
5. On failure, fall back to normal (self-paid) tx or inform the user.
6. Monitor the tx as usual.

Best practices: always check sponsorability first; give clear user feedback; implement fallback for non-sponsored txs.

### Hosted implementation
**NodeReal MegaFuel** (https://docs.nodereal.io/docs/megafuel-overview) is a paymaster
implementation based on BOT Chain Paymaster for EOA wallets. Sponsors configure policies
(whitelists, NFT-gating, credit/deposit accounts) and can charge via pre-deposited crypto
or off-chain billing.

> Note: the official bundler endpoints do NOT expose `pm_isSponsorable`; the EOA paymaster
> is delivered as a hosted service. The endpoints below are ERC-4337 bundlers.

## 2. ERC-4337 (Account Abstraction)

Bundler endpoints (live, verified):

| Network | Bundler RPC |
|---|---|
| Mainnet | `https://bundler.botchain.ai/rpc` |
| Testnet | `https://bundler.bohr.life/rpc` |

- `eth_supportedEntryPoints` returns **EntryPoint v0.7**: `0x0000000071727De22E5E9d8BAF0edAC6f37da032` (both networks).
- Standard methods supported: `eth_sendUserOperation`, `eth_estimateUserOperationGas`, `eth_getUserOperationReceipt`, `eth_getUserOperationByHash`.

### Quick check
```bash
curl -s https://bundler.botchain.ai/rpc -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_supportedEntryPoints","params":[]}'
# => {"jsonrpc":"2.0","id":1,"result":["0x0000000071727de22e5e9d8baf0edac6f37da032"]}
```

### v0.7 `eth_sendUserOperation` skeleton
```js
const op = {
  sender, nonce,
  factory, factoryData,
  callData, callGasLimit,
  verificationGasLimit, preVerificationGas, maxFeePerGas, maxPriorityFeePerGas,
  paymaster, paymasterVerificationGasLimit, paymasterPostOpGasLimit, paymasterData,
  signature,
};
// bundle op via entryPoint address 0x0000000071727De22E5E9d8BAF0edAC6f37da032
```

## Gas / fee notes

- BOT chain has no EIP-1559 (`baseFeePerGas: 0x0`); gas price observed ~50 Gwei (live `eth_gasPrice` 2026; explorer reports ~29 Gwei); typical tx ~$0.01-0.10.
- Zero-gas-price txs are only accepted through a paymaster/bundle path (PBS), not directly by the RPC.
- Official docs (json-rpc-endpoint page) state the paymaster workflow is BEP-322 PBS-based.
