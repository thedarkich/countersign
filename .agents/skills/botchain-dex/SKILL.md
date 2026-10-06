---
name: botchain-dex
description: "Use when integrating with or querying BOT Chain's B DEX / BDEX - Uniswap-style v2/v3 contracts, universal router, quoter, contract addresses, price APIs, or the dex-wallet graph API on chainId 677/968. Triggers: \"bdEx\", \"B DEX\", \"bot chain dex\", \"dex.botchain.ai\", \"universal router botchain\", \"WBOT price\", \"botchain liquidity\"."
---

# BOT Chain - B DEX (BDEX) Integration

B DEX is the official DEX of BOT Chain: **BDEX v2** (constant-product AMM, x·y=k) and
**BDEX v3** (concentrated liquidity), based on the Uniswap v2/v3 design. It powers swaps,
liquidity provision, and liquidity mining, and is the only official way to acquire BOT on
mainnet.

- App: `https://dex.botchain.ai/#/swap`
- Docs: https://dev-docs.botchain.ai/docs/DEX/

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai/docs/DEX/), the live DEX
> backend (`dex-wallet.botchain.ai`), and the official integration guide. When
> extending this skill, only pull from these sources and verify contract addresses
> against the live `/config`.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Token addresses | `botchain-network` | Native BOT, WBOT, USDT contracts |
| Deploy & index | `botchain-deploy` | Building dApps on top of BDEX |
| Price feeds | `botchain-ecosystem` | BOT/WBOT market data, trackers |
| Liquidity incentives | `botchain-ecosystem` | Scheme A DEX incentive support |

## Core tokens

| Token | Address (mainnet 677) | Decimals |
|---|---|---|
| BOT (native) | no contract - native coin | 18 |
| WBOT | `0xD5452816194a3784dBa983426cCe7c122F4abd30` | 18 |
| USDT (bridged) | `0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C` | 6 |

## Contract addresses (mainnet, chainId 677)

Deployer: `0xf0A2f56505f0dfea980567DA88830146B6b5c0b2`

### v3 (deployed 2026-02-26)
| Contract | Address |
|---|---|
| Factory | `0x1C51c173323ec11BB4e3C4fD2314c225Dc4b5419` |
| SwapRouter | `0x07032d47A1b9f8460cBeE9dC17c1d3E438693929` |
| Quoter | `0x1e8bb093ade678ABAa49623D4c3a1a7F37716DEd` |
| QuoterV2 | `0x034A705b36067cff99ABf5C662Be881cBd8d0176` |
| BDEX Multicall | `0x5FC578616301E56137dc3872593d496668525362` |
| NFT Descriptor | `0x829D215662e89881adE3C7b15a0af812c4364dA4` |
| NFT Position Descriptor | `0x89b084964AF60BeE7bEc324Ea62267C97f6656E3` |
| NFT Position Manager | `0xDAc3FcFF004d8a8675b94E44941A1a2e3b240090` |
| **Universal Router** | `0xaE6ae8630f7A888dEc0B9195C85F7515d5887655` |

### Testnet (chainId 968)
| Contract | Address |
|---|---|
| **Universal Router** | `0x73Be0A1d8011B335A7aBeF6c45544E8ca4448AB5` |

> Verify against live `/config` from the dex backend when integrating - contract
> addresses are upgradeable/shipped via the graph API; always confirm with the official
> integration guide.

## Using the Universal Router

```js
// WBOT -> USDT swap through the Universal Router (mainnet)
const router = new Contract(
  "0xaE6ae8630f7A888dEc0B9195C85F7515d5887655",
  UNIVERSAL_ROUTER_ABI,
  signer
);
const params = {
  tokenIn: "0xD5452816194a3784dBa983426cCe7c122F4abd30",
  tokenOut: "0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C",
  amountIn, amountOutMin, recipient, deadline,
};
await router.swap(params);
```

Standard Uniswap Universal Router command encoding applies (V2_SWAP_EXACT_IN,
V3_SWAP_EXACT_IN, PERMIT2 approve → swap). Check the quoter for minimum-out and price
impact before sending.

## Price & market APIs (live, verified)

### WBOT price API
```bash
curl "https://dex-wallet.botchain.ai/api/graph/price?token=0xD5452816194a3784dBa983426cCe7c122F4abd30"
# => {"data":{"path":[wbot,usdt],"pool_type":"all","pool_types":["v3"],
#     "pools":["0x64f418471a1a7932a190e10da5a8551db5abec05"],"price":"9.34...","token":"0xd545..."},"success":true}
```
Pool `0x64f418471a1a7932a190e10da5a8551db5abec05` is the WBOT/USDT 0.3% v3 pool.

### Graph API - `dex-wallet.botchain.ai/api/v1/*`
| Endpoint | Notes |
|---|---|
| `/api/v1/klines?pair=` or `?token=` | OHLCV; intervals map `1m/5m/30m/1H/2H/1D → MINUTE1/MINUTE5/MINUTE30/HOUR1/HOUR2/DAY1`, limit 2000. Do NOT pass pair+token together (`INVALID_IDENTIFIER_PARAMETER`). |
| `/api/v1/orders` | order-kind filter `swap\|mint\|burn\|collect\|all` (NOT time intervals). Returns `{id: tx_hash, type, attributes{kind, from/to token+amount, prices, volume_in_usd, pool_address, pool_type, block_number/timestamp}}`. |
| `/api/v1/swaps/pool/{address}` | per-pool swap records (`direction`, `token_in/out`, `amount_usd`, `origin` EOA, `sender/recipient`, `gas_used`, `gas_price_wei`, `log_index`, `event_id`). |
| `/api/v1/swaps/token/{address}` | per-token swap records (same shape). |
| `/api/v1/pool-charts` | OHLCV for pools: `periodStartUnix, open/high/low/close, volumeUSD, feesUSD, tvlUSD`. |
| `/api/v1/klines/pair` | single kline `{open,high,low,close,volume,time,volumeUSD,volumeToken0/1}`. |
| `/api/v1/klines/pair/summary` | 24h stats: `currentPrice, price24hAgo, change24h, low/high24h, points`. |
| `/api/v1/klines/token/{addr}` | token OHLC (`{value}` wrappers). |
| `/api/v1/price-weighted` | multi-path weighted price; each path `{edges{pools,pool_type,tvl}, price, weight}`. |
| `/api/v1/tokens` | token registry (`id, token_address, chain_id, symbol, name, decimals`). |
| `/api/v1/token-pool-stats` | pool stats per token. |

Testnet graph host: `https://dex-wallet.bohr.life` (401 pairs on chain 968). The root path returns 404 (no pong endpoint); reachability check: `curl https://dex-wallet.bohr.life/api/v1/tokens` → `{chain_id: 968, tokens: [...]}`.

## Swapping flow (user-facing)

1. Connect wallet, switch to BOT Chain Mainnet, keep BOT for gas.
2. Pick sell/buy tokens; the **first USDT/token swap needs an Approve tx** before Swap.
3. Review rate, price impact, minimum received, fees.
4. Keep default slippage unless execution fails.
5. Approve → Swap → verify received balance on explorer.

## Liquidity & mining

- Provide liquidity via v2 (x·y=k) or v3 (concentrated) using the NFT Position Manager / v3 factory.
- Liquidity mining incentives are part of the official ecosystem program (see `botchain-ecosystem`).

## Audits

CertiK DEX audit: https://dex.botchain.ai/docs/Dex-Audit-Report.pdf
