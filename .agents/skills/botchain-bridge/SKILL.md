---
name: botchain-bridge
description: "Use when integrating with or debugging the BOT Chain cross-chain bridge - supported chains (Ethereum, BNB Chain, Tron), fees, contract addresses, deposit/execute flow, bot gas prefund, or when USDT bridge transfers don't arrive. Triggers: \"bot chain bridge\", \"bridge.botchain.ai\", \"BOT bridge USDT\", \"cross chain botchain\", \"bridge fee\", \"bridge contract\"."
---

# BOT Chain - Cross-Chain Bridge

The official BOT Chain bridge transfers **USDT** between **BOT Chain (677)** and
**Ethereum (1)**, **BNB Chain (56)**, and **Tron (728126428, non-EVM)**. It is a
**lock-and-release (liquidity) bridge** with decentralized validators + relayers
(powerful, threshold-signed attestations submitted via `BohrBridge.execute`).

- App: `https://bridge.botchain.ai`
- Backend API: `https://api-bridge.botchain.ai`
- Docs: https://dev-docs.botchain.ai/docs/Bridge/

> **Source constraint:** All information in this skill is sourced from the
> [BOT Chain developer docs](https://dev-docs.botchain.ai/docs/Bridge/), the bridge
> app and backend API, and verified against on-chain contracts. When extending this
> skill, only pull from these sources.

## Related skills

| Topic | Skill | Load when |
|-------|-------|-----------|
| Gas prefund rate | `botchain-dex` | BDEX rate used for the BOT gas prefund |
| Ecosystem & onboarding | `botchain-ecosystem` | Integration checklist, audits |
| Deploy & verify | `botchain-deploy` | Building contracts that receive bridged USDT |

## Supported chains & assets

USDT is bridged to/from all four chains (single shared resource ID):

`resourceId = 0xac589789ed8c9d2c61f17b13369864b5f181e58eba230a6ee4ec4c3e7750cd1d`

| Chain | BohrBridge (router) | Registry | USDT |
|---|---|---|---|
| **BOT Chain (677)** | `0xef8DC669ECa13E612b67Ff09478352E85bD6CC53` | `0xB230BDA1D8971eCB2E59ceD8f8F73aC5F128AEf0` | `0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C` (6) |
| **Ethereum (1)** | `0x2945d3aF6f012e49f7421252b5fB57D1bb7E6Edd` | `0x6A39dE7CB8BBAf62Ce50a4BEBda4253F13751333` | `0xdac17f958d2ee523a2206206994597c13d831ec7` (6) |
| **BNB Chain (56)** | `0x3cd6fB6b0CDdD3610f0f4769AA7Bb686Cd4a4b55` | `0x979572fa3E2A08919B19adCEF9f55bD9e501ef7F` | `0x55d398326f99059ff775485246999027b3197955` (18) |
| **Tron** | `TGhXbQpjBgC6bDp5jAexzeQPHEXXsx5f35` | `TCosCuUsWGYW2GFwLKKUGmX92kccKGzWG8` | `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` (6) |

BOT Chain bridge proxies are TransparentUpgradeableProxy; admin `0x3cd6fB6b0CDdD3610f0f4769AA7Bb686Cd4a4b55`.
`serverAddress()` on BOT BohrBridge = `0x1f261a04bacd21f54f1e15f50ac9212728a654d5`.

## Fees (verified on-chain)

| Direction | Fee |
|---|---|
| **Bridge-in** (external → BOT) | **Free** (chainAndTokenFee = 0) |
| **Bridge-out** (BOT → external) | **0.1%**, minimum **1 USDT** (`max(amount×0.1%, 1)`; `minFee()=1`) |
| Limits | `minAmountUsd()` = 10, `maxAmountUsd()` = 30,150 (BOT/BSC/ETH); Tron max 50,000 |

**BOT gas prefund (optional, NOT a fee):** the UI offers "Receive 0.1 BOT for Future Gas"
on bridge-in; 0.1 BOT is credited on BOT Chain and its USDT-equivalent is deducted from
the received amount at the BDEX rate. `/api/hasEnoughBotGas` thresholds ~20 BOT balance.
On-chain `getBotGasConfig()`: `{destinationChainId:677, resourceId, amount:0.1 BOT (1e17),
oracle:0x912dc8aadcf22d73b93710805a1ecb7167a6f068, baseToken:0xd545..., quoteToken:USDT,
twapWindow:1800, enabled:true}`.

## Deposit flow (developer)

1. `GET https://api-bridge.botchain.ai/config` - chains/tokens.
2. `GET https://api-bridge.botchain.ai/bridge_risk/status` - gate on `bridge_paused` / `bridge_out_paused`.
3. Pre-checks: min/max USD, daily IP limit (`POST /api/ip/limit`), blacklist, `getMinFee()`.
4. **Approve** USDT to the source BohrBridge.
5. Optionally enable BOT gas prefund if the wallet holds < 20 BOT.
6. Estimate gas, then call deposit:
   - EVM: `deposit(uint256 destinationChainId, bytes32 resourceId, address recipient, uint256 amount)` - payable (native value only if token is the native coin). Selector `0x53ab615d`.
   - Tron: `BridgeContract.deposit(destChainId, resourceId, recipient, amount)` with `feeLimit: 2e9`.
   - Prefund variant: `depositWithBotGas(destinationChainId, resourceId, recipient, amount)`.
7. Validators attest `DepositEvent`; relayers call `BohrBridge.execute(...)` on the destination, releasing USDT minus fee. Observed completion **22-96s**.
8. Track in `https://api-bridge.botchain.ai/history` - `bridge_status`: 1 pending, 3 completed, 4 security check, 5 refunded, 6 under review, 7 restricted, 8 frozen.

### Key ABI selectors
- `deposit(uint256,bytes32,address,uint256)` `0x53ab615d` (payable)
- `deposit(uint256,bytes32,bytes)` `0x2b681307` (registry, payable)
- `chainAndTokenFee(uint256,bytes32)` `0xd6a496f1` · `getMinFee()` `0x5cf34bcf` · `minAmountUsd()` `0x02d92812` · `maxAmountUsd()` `0xb7d57c52`
- `getBotGasConfig()` `0x5851e22f` · `getBridgePause()` `0xfc4e3b89` · `localNonce()` `0x13cb3591` · `serverAddress()` `0xdb420fe3`
- `execute(bytes32,uint256,address,address,uint256,uint256,uint256,uint256,bytes32,uint8,uint256)` (relayer only)
- Events: `DepositEvent(depositer,recipient,amount,receiveAmount,tokenAddress,depositNonce,destinationChainId)`, `ExecuteEvent`, `SetResource`, `Deposit(destinationChainId,resourceID,depositNonce,data)`, `Refunded`.

## Troubleshooting "transfer not arrived"

1. Save the TxHash + source/dest network, token, amount, time.
2. Check `https://bridge.botchain.ai` history / Track Your Transaction.
3. Pending/Processing → do not resubmit; escalate only after an extended period. Failed → confirm refund before retrying. Completed → switch to BOT Chain, add USDT via its official contract address.
4. Verify balance at https://scan.botchain.ai.
5. For support, provide wallet address, networks, token, amount, time, TxHash, and a status screenshot - never a recovery phrase/private key.

## Audit

CertiK Bridge audit (02/2026): 25 findings (6 resolved, 19 acknowledged), 1 Critical resolved. Report: https://bridge.botchain.ai/docs/Bridge-Audit-Report.pdf
