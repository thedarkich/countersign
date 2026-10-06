---
name: botchain-ecosystem
description: "Use when helping a project onboard onto BOT Chain, applying to the $50M BOT Chain ecosystem support program (Scheme A DEX, Scheme B CEX listing, Scheme C community), quoting BOT/WBOT prices, integrating official APIs, or explaining roadmap, governance, and audits. Triggers: \"bot chain ecosystem\", \"botchain grant\", \"ecosystem support program\", \"BOT price api\", \"CaryPact\", \"BOT chain roadmap\"."
---

# BOT Chain - Ecosystem, Grants & Onboarding

This skill covers the BOT Chain ecosystem program, market/price APIs, official
integration resources, and the onboarding checklist for project teams.

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain website](https://www.botchain.ai), the
> [developer docs](https://dev-docs.botchain.ai), and live market/explorer APIs. When
> extending this skill, only pull from these sources.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Network setup | `botchain-network` | Adding chain 677/968 to wallets |
| Deploy & verify | `botchain-deploy` | Contract deployment, faucet |
| DEX & liquidity | `botchain-dex` | Scheme A incentives, WBOT price |
| Bridge | `botchain-bridge` | USDT liquidity, cross-chain support |
| Staking & governance | `botchain-staking` | Tokenomics, governance roadmap |

## Ecosystem Support Program ($50M)

Apply at `https://www.botchain.ai/en/ecosystem-support` or email `ecosystem@botchain.info`.
Maximum funding per project: **$1,000,000**. Each project picks one of Scheme A/B/C and
may combine "Additional Ecosystem Benefits".

### Scheme A - DEX Incentive Support
Reward = Base Reward + (Tx Fee Revenue + Gas Revenue) × 30%, capped per tier (token/BOT pairs boosted +20%):

| Min LP (7d) | Cum. vol (15d) | Cum. txs | Base | Rev share | Tier max |
|---|---|---|---|---|---|
| $50K | $125K | 1,250 | $1,250 | 30% | $4,000 |
| $200K | $500K | 5,000 | $5,000 | 30% | $16,000 |
| $1M | $2M | 15,000 | $8,000 | 30% | $40,000 |
| $5M | $8M | 50,000 | $15,000 | 30% | $160,000 |
| $10M | $20M | 100,000 | $20,000 | 30% | $240,000 |

### Scheme B - CEX Listing Support
CMC Top 1-8 → $60,000; Top 9-30 → $10,000; Top 30-50 → $2,000.

### Scheme C - Community Growth & User Conversion
Valid user = address holds ≥0.1 BOT + ≥$100 USDT, ≥24h account age, ≤20 interactions/day, 10% Sybil counter. Tiers from ≥4,000 users / ≥30,000 interactions / ≥$150K TVL ($12,000) up to ≥800,000 / ≥6M / ≥$3.5M ($350,000).

### Additional benefit - Tiered Gas Fee Rebate (weekly)
Cumulative fees: ≥$50K → 5%, $100K → 8%, $150K → 11%, $200K → 14%, $250K → 18%, $300K → 22%, $350K → 26%, $400K → 30%, ≥$500K → 35%.

### Process
1. Submit application (website form or email) with project materials, team info, on-chain addresses.
2. Preliminary review - feedback within **10 business days**.
3. Technical coordination with a dedicated Account Manager.
4. Contract signing with milestones, launch timelines, recovery clauses.
   Rewards settle monthly (data recorded on-chain); gas rebates weekly.

Additional support: rapid dev kit, one-click deployment, BO Wallet DApp-store feature slot, Launchpad priority, targeted airdrops via official Discord/Twitter (50,000+ real addresses), market-maker fast track, CEX listing recommendation, official certification badge.

## Price / market APIs

### BOT (native) - Coinstore
```bash
curl "https://api.coinstore.com/api/v1/ticker/price;symbol=BOTUSDT"
curl "https://api.coinstore.com/v3/public/orderbook/market_pair?market_pair=BOT_USDT&depth=100"
```

### WBOT price
```bash
curl "https://dex-wallet.botchain.ai/api/graph/price?token=0xD5452816194a3784dBa983426cCe7c122F4abd30"
# => {"data":{"path":[...],"pools":["0x64f4..."],"price":"9.34...","token":"0xd545..."},"success":true}
```

### Market trackers
- CoinGecko: https://www.coingecko.com/en/coins/wrapped-bot (platform `bot-chain`, contract `0xd545...`)
- CoinMarketCap: https://coinmarketcap.com/currencies/bot-chain/
- Explorer coin price: `GET https://scan.botchain.ai/api/v2/stats` (tracks WBOT feed)

## Official integration resources

- Integration guide (Google Doc): https://docs.google.com/document/d/1xYzdfJlD08UOV9CKE3nV7NTSQg6lPz9B17aIW2NF5Wg/edit
- Developer docs: https://dev-docs.botchain.ai
- Git: https://github.com/BOTChain-bot
- Brand kit: https://drive.google.com/drive/folders/1AYVj_gvnffA4T-QyXN3opgWNG5M7oD_1

## Audits (CertiK)

- Chain: https://www.botchain.ai/docs/Chain.pdf
- DEX: https://dex.botchain.ai/docs/Dex-Audit-Report.pdf
- Bridge: https://bridge.botchain.ai/docs/Bridge-Audit-Report.pdf
- Skynet: https://skynet.certik.com/projects/botchain

## Onboarding checklist (project teams)

1. Add BOT Chain mainnet (677) to wallet; get test BOT from https://faucet.botchain.ai/basic.
2. Deploy + verify contracts (see `botchain-deploy`).
3. Choose an incentive scheme (A/B/C) and apply via ecosystem-support or email.
4. Integrate official products as needed: bridge (USDT liquidity), BDEX (pairs/liquidity), BO Wallet, Safe multisig (`app.safe.global`, BOT Chain supported).
5. Wire price feeds using the APIs above; monitor via explorer stats.
6. Keep gas topped up (BOT) - either via DEX swap or bridge BOT-gas prefund.

## Ecosystem context

- Flagship protocol: **CaryPact** - decentralized supercomputing matching protocol (roadmap 2025 Q3-2026 Q1).
- Project directory: 631 ecosystem apps/partners, 127 live on mainnet (live API: `https://www.botchain.ai/api/projects`).
- Investors: NIX Foundation ($10M), Alpha Capital ($3M), Gemhead Capital ($2M) - $15M total.
- Roadmap highlights: MPL framework, vCompute v1.0, Compute Node Activation, BOT Cross-Chain Bridge (2025Q3-2026Q1); BOT Infrastructure Grant, BDex, Bo Wallet (2026Q2-Q3); governance framework + BIP spec (2027Q1-Q2); BRN relay network, global nodes, 50% modular components (2027Q2-2028Q2).
