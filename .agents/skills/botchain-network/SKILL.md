---
name: botchain-network
description: "Use when connecting to BOT Chain, adding the network to wallets, choosing RPC/WSS endpoints, looking up chain IDs, explorers, block times, gas, or network parameters for the BOT Chain EVM Layer 1 (mainnet 677, testnet 968). Triggers: \"bot chain\", \"botchain\", \"chainId 677\", \"rpc.botchain.ai\", \"add bot chain to metamask\"."
---

# BOT Chain - Network Configuration

BOT Chain is a 100% EVM-compatible Layer 1 (PoSA consensus, geth-based, BSC fork lineage).
All Ethereum tooling works out of the box. This skill covers the canonical network
parameters and how to connect.

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai) and verified against live
> endpoints (RPCs, explorers). When extending this skill, only pull from these sources
> and the chain IDs registered in [ChainList](https://chainlist.org/chain/677).

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Contract deployment | `botchain-deploy` | Deploying/verifying on chain 677/968 |
| JSON-RPC & gas | `botchain-rpc` | RPC methods, blob sidecars, fee handling |
| Gas sponsorship | `botchain-paymaster` | Gasless/zero-gas transactions |
| Node operation | `botchain-nodes` | Running or maintaining a node |
| Validators & staking | `botchain-staking` | Becoming a validator, delegation |

## Authoritative network parameters

### Mainnet
| Parameter | Value |
|---|---|
| Network Name | BOT Chain Mainnet |
| Chain ID | **677** (`0x2a5`) |
| RPC (HTTPS) | `https://rpc.botchain.ai` |
| RPC (WSS) | `wss://ws-rpc.botchain.ai` |
| Native Token | BOT (18 decimals, ERC-20/BEP-20 dual-compatible) |
| Total Supply | 150,000,000 (hard cap) |
| Explorer | `https://scan.botchain.ai` (Blockscout) |
| Staking dApp | `https://staking.botchain.ai` |
| Faucet (testnet only) | `https://faucet.botchain.ai/basic` |

### Testnet
| Parameter | Value |
|---|---|
| Network Name | BOT Chain Testnet (internally "Bohr") |
| Chain ID | **968** (`0x3c8`) |
| RPC (HTTPS) | `https://rpc.bohr.life` |
| RPC (WSS) | `wss://ws-rpc.bohr.life` |
| Native Token | BOT (18 decimals) |
| Explorer | `https://scan.bohr.life` |
| Staking dApp | `https://staking.bohr.life` |
| Faucet | `https://faucet.botchain.ai/basic` (10 tBOT + 1000 tUSDT per 24h) |

## Chain facts & performance model

- **Block time**: 0.75 seconds (mainnet)
- **Finality**: ~0.9s average; irreversible within ~2 seconds ("Fast Finality", Plato upgrade); single-slot economic finality >99.9%
- **Parallel execution**: 64 tx/batch
- **Average fee**: ~$0.01-0.10 / tx depending on gas used; live `eth_gasPrice` observed **~50 Gwei** (2026), explorer reports ~29 Gwei; **no EIP-1559** (`baseFeePerGas: 0x0`), flat BSC-style fee model
- **Consensus**: PoSA / SPoA (Parlia), BEP-126 (finality) + BEP-341 (multi-block proposer), geth-based client `Geth/v1.5.x`
- **EVM features**: full EVM, EIP-4844 blob support, ERC-4337 EntryPoint v0.7 (`0x0000000071727De22E5E9d8BAF0edAC6f37da032`) via bundler endpoints

## Adding the network to wallets

### MetaMask
1. Open MetaMask → network selector → **Add a custom network**.
2. Enter exactly: Network name `BOT Chain Mainnet`, RPC URL `https://rpc.botchain.ai`, Chain ID `677`, Currency symbol `BOT`, Explorer `https://scan.botchain.ai`.
3. Save, switch to BOT Chain Mainnet, verify Chain ID is 677.
4. A small BOT balance is required as gas before transacting.

### Programmatic add (ethers.js v6)
```js
const { BrowserProvider } = require("ethers");

await provider.send("wallet_addEthereumChain", [{
  chainId: "0x2a5", // 677
  chainName: "BOT Chain Mainnet",
  nativeCurrency: { name: "BOT", symbol: "BOT", decimals: 18 },
  rpcUrls: ["https://rpc.botchain.ai"],
  blockExplorerUrls: ["https://scan.botchain.ai"],
}]);
```

### EIP-155 / chain metadata (for RPC providers, chainlist-style config)
```json
{
  "name": "BOT Chain Mainnet",
  "chain": "BOT",
  "chainId": 677,
  "networkId": 677,
  "shortName": "bot",
  "nativeCurrency": { "name": "BOT", "symbol": "BOT", "decimals": 18 },
  "rpc": ["https://rpc.botchain.ai", "wss://ws-rpc.botchain.ai"],
  "explorers": [{ "name": "botscan", "url": "https://scan.botchain.ai/" }],
  "infoURL": "https://www.botchain.ai/",
  "faucets": []
}
```

## Getting BOT for gas

- **Testnet**: claim from the faucet - https://faucet.botchain.ai/basic (Cloudflare Turnstile captcha, up to 10 tBOT / 24h per address; also drips 1000 tUSDT/24h). See the `botchain-faucet` notes in the deploy skill.
- **Mainnet**: swap for BOT on the official DEX (https://dex.botchain.ai/#/swap) or receive BOT as gas via the bridge's "Receive 0.1 BOT for Future Gas" option on bridge-in.

## Explorers

Both are branded **BOTScan** and run **Blockscout**, so both REST v2 and legacy Etherscan-style APIs work:

- Mainnet: `https://scan.botchain.ai`
- Testnet: `https://scan.bohr.life`

### Blockscout REST v2 examples
```
GET https://scan.botchain.ai/api/v2/stats
GET https://scan.botchain.ai/api/v2/addresses/{hash}
GET https://scan.botchain.ai/api/v2/transactions/{txhash}
```

### Legacy Etherscan-style API (works on both explorers)
```
GET https://scan.botchain.ai/api?module=account&action=balance&address=0x...
GET https://scan.botchain.ai/api?module=contract&action=getsourcecode&address=0x...
GET https://scan.botchain.ai/api?module=account&action=txlist&address=0x...
```

## Troubleshooting

- **`eth_getLogs` is disabled on the mainnet public RPC.** Use WSS subscriptions or third-party endpoints (Alchemy/Covalent) for log-heavy indexing.
- **`debug_*` methods are not exposed publicly** (`-32601`); only on self-run nodes.
- **Testnet chain 968 is NOT in ChainList / ethereum-lists/chains** (that ID is registered to another chain there). Always add testnet manually.
- **Don't trust explorer front-page price figures** - live Blockscout `/api/v2/stats` is authoritative for price/market data.

## Useful links
- Developer docs: https://dev-docs.botchain.ai
- Chainlist entry: https://chainlist.org/chain/677
- Network status / integration guide: https://docs.google.com/document/d/1xYzdfJlD08UOV9CKE3nV7NTSQg6lPz9B17aIW2NF5Wg/edit
