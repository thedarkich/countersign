---
name: botchain-deploy
description: "Use when deploying or verifying Solidity smart contracts on BOT Chain with Hardhat, Foundry, Remix, or ethers.js, getting testnet tBOT from the faucet, configuring deployment scripts for chainId 677/968, or choosing indexing tools (TheGraph, Covalent). Triggers: \"deploy to bot chain\", \"hardhat botchain\", \"verify contract botchain\", \"tBOT faucet\"."
---

# BOT Chain - Smart Contract Deployment & Verification

BOT Chain is 100% EVM-compatible, so Ethereum deployment workflows transfer with almost
zero changes. Chain IDs: **677 mainnet** / **968 testnet**. This skill documents the
full path from faucet to verified contract.

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai) (deployment page), the
> [faucet](https://faucet.botchain.ai/basic), and the Blockscout explorers. When
> extending this skill, only pull from these sources.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Network parameters | `botchain-network` | Wallet/RPC setup for chain 677/968 |
| Indexing & APIs | `botchain-rpc` | Log indexing, `eth_getLogs` restrictions |
| Gas sponsorship | `botchain-paymaster` | Zero-gas or gasless transactions |
| DEX & liquidity | `botchain-dex` | Post-deploy token liquidity |
| Grants & support | `botchain-ecosystem` | Ecosystem program, onboarding |

## Prerequisites

1. A wallet on BOT Chain (mainnet 677 or testnet 968). See the `botchain-network` skill.
2. Test tokens: https://faucet.botchain.ai/basic
3. A deployment tool: Hardhat, Foundry, Remix, or ethers.js/web3.js.

## Getting test BOT (faucet)

- URL: `https://faucet.botchain.ai/basic` (also `/en/basic`, `/zh/basic`)
- Auth: Cloudflare Turnstile captcha only (no Twitter/GitHub OAuth).
- Rewards per address per 24h: **10 tBOT** (native) and **1000 tUSDT** (ERC-20 from `0x75edC9335175Fc0552D51D48439F229c10420fe3`).
- tBOT has no monetary value and cannot be used on mainnet.

### Faucet API (for scripting)
Base: `https://faucet.botchain.ai/api/v1/faucet`

```bash
# Get claim config
curl https://faucet.botchain.ai/api/v1/faucet/info

# Claim (needs a valid Turnstile token; returns tx hash in data.tx_hash)
curl -X POST https://faucet.botchain.ai/api/v1/faucet/claim \
  -H "content-type: application/json" \
  -d '{"address":"0x...","turnstileToken":"<token>","asset":"BOT"}'
```

Error codes: `10002` invalid address · `10003` turnstile failed · `10004/10005` rate limited (24h cooldown) · `10001/10006/10008` send failed · `10007` service unavailable.

## Hardhat deployment

```ts
// hardhat.config.ts
import { HardhatUserConfig } from "hardhat/config";

const config: HardhatUserConfig = {
  solidity: "0.8.24",
  networks: {
    botchainMainnet: {
      url: "https://rpc.botchain.ai",
      chainId: 677,
      accounts: [process.env.PRIVATE_KEY!],
    },
    botchainTestnet: {
      url: "https://rpc.bohr.life",
      chainId: 968,
      accounts: [process.env.PRIVATE_KEY!],
    },
  },
  etherscan: { apiKey: { botchainMainnet: "empty", botchainTestnet: "empty" } },
  customChains: [
    { network: "botchainMainnet", chainId: 677, urls: { apiURL: "https://scan.botchain.ai/api", browserURL: "https://scan.botchain.ai" } },
    { network: "botchainTestnet", chainId: 968, urls: { apiURL: "https://scan.bohr.life/api", browserURL: "https://scan.bohr.life" } },
  ],
};

export default config;
```

Deploy:

```bash
npx hardhat run scripts/deploy.ts --network botchainTestnet
npx hardhat run scripts/deploy.ts --network botchainMainnet
```

Verify (Blockscout, no API key needed - pass an empty string):

```bash
npx hardhat verify --network botchainMainnet <CONTRACT_ADDRESS> <constructor-args...>
```

## Foundry deployment

```bash
# .env
RPC_MAINNET=https://rpc.botchain.ai
RPC_TESTNET=https://rpc.bohr.life
PRIVATE_KEY=0x...
```

```bash
forge create src/Counter.sol:Counter \
  --rpc-url $RPC_TESTNET \
  --private-key $PRIVATE_KEY \
  --chain 968

# verify via Blockscout
forge verify-contract <ADDRESS> src/Counter.sol:Counter \
  --chain 968 --verifier blockscout --verifier-url https://scan.bohr.life/api/
```

## Remix

1. In Remix, Deploy & Run → Environment → **Injected Provider** (MetaMask on BOT Chain), or **Custom / External HTTP Provider** → enter `https://rpc.botchain.ai` (mainnet) or `https://rpc.bohr.life` (testnet).
2. Compile and deploy as usual. Verify later via the explorer's "Verify & Publish" (Blockscout) using the flattened source.

## ethers.js / web3.js

All standard Ethereum SDKs work. Any EVM SDK's "custom network" config accepts the
values in the `botchain-network` skill (chainId 677/968, BOT with 18 decimals).

## Contract verification (Blockscout)

Both explorers are Blockscout. Verification supports flattened Solidity source, Vyper,
and standard JSON input. No API key required.

- Mainnet: https://scan.botchain.ai/address/<addr>#code → "Verify & Publish"
- Testnet: https://scan.bohr.life/address/<addr>#code

## Indexing options

- **TheGraph** (subgraphs) - works against BOT Chain RPC.
- **Covalent** - supported per official docs.
- Note: `eth_getLogs` is disabled on the mainnet **public** RPC - for heavy log
  indexing use WSS subscriptions, a self-hosted node, or third-party indexers.

## Ecosystem wallet/token notes

- BOT is the **native coin** (no contract address).
- Wrapped BOT (WBOT): `0xD5452816194a3784dBa983426cCe7c122F4abd30` (18 decimals).
- USDT on BOT Chain: `0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C` (6 decimals).
- BDEX Universal Router - mainnet: `0xaE6ae8630f7A888dEc0B9195C85F7515d5887655`, testnet: `0x73Be0A1d8011B335A7aBeF6c45544E8ca4448AB5`.

## Integration checklist

1. Add BOT Chain to the wallet (chain 677 or 968).
2. Get test tokens from the faucet.
3. Deploy via Hardhat/Foundry/Remix using the official RPC.
4. Verify the contract on the explorer (Blockscout, no key).
5. Test the product; for grants/support see the `botchain-ecosystem` skill.
