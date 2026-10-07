> 2026-10-07: integrated the teammate frontend from `yihao0220/countersign` with our existing API, wallet controls and evidence-based reputation. See [provenance and validation](../docs/FRONTEND_INTEGRATION.md).

# Countersign frontend

A landing page and team-access screen surround the four core workflows in one Vite + React app. Public agent history is connected in Ledger and Controls.

| Route | Who | What |
|---|---|---|
| `#/` | public | Bilingual landing page, illustrative payment flow, links to the team workspace and public ledger. |
| `#/login` | team | Validates the existing team access token; no customer signup or password service. |
| `#/bounty` | public, phones | Submit an invoice or a message to the guarded or naive agent and watch it go through the countersign row (读 隐 核 审 链) until the seal lands. Submission is disabled while backend readiness reports closed admission. Also shows live counters, the leaderboard and the rules. Phone photos over 1.5 MB are shrunk in the browser (2400 px long edge, JPEG) so they fit the 5 MB limit. |
| `#/ledger` | public, projector | Evidence-based agent reputation, counters, the QR code to the bounty, the guard v1 vs v2 card and every on-chain event. Press `F` or open `#/ledger?stage=1` for stage mode. New payments and blocks stamp a big seal for three seconds. |
| `#/inbox` | team (admin token) | One-click stage invoices, drag-and-drop upload, the clean batch, and "Both agents": the same invoice through the guarded and the naive agent, side by side, each ending in its own seal. That view is the demo's key moment. Any attempt opens a drawer with the file, hidden-text boxes, fields, flags and the proposal next to the registry address. |
| `#/controls` | team plus the owner wallet | Vendors, budgets, daily cap, agent keys (with their BOT balance and whether BOT Chain's paymaster pays their gas), pause, withdraw, and the queue of waiting changes with countdowns. Instant actions and time-locked ones are labelled on every button. |

Routes use the hash, so the backend needs no SPA fallback, and links survive WeChat's in-app browser.

Every screen comes in Chinese and English, switched with 中文 / EN in the header. On a first visit the language follows the phone or browser, so a mainland phone (WeChat included) opens in Chinese and a foreign one in English. The choice is remembered.

If the backend stops answering (a dropped connection or a 5xx), a thin strip at the top says so on every screen, including the stage, and the last data stays on screen while it retries.

Light and dark themes follow the system setting. The sun or moon button next to the language switch overrides it, and that choice is remembered too. Invoice previews and QR codes stay on white in both themes, because that's what a printed invoice looks like and what phone cameras scan best.

## Run it

```bash
npm install
npm run dev -- --mode mock   # everything works with no backend
npm run dev                  # live: proxies /api to http://localhost:8000
npm run build                # dist/, served by the backend at /
npm run build:mock           # a static build on the mock API, for rehearsals
```

In mock mode a "Mock data" badge sits in the header (a strip under it on phones). The admin gate takes any token.

Things to try in mock mode:
- On the bounty, type a message with an address or 收款地址 in it and pick the naive agent. The vault blocks it with `PayoutMismatch`.
- Words like `ignore`, `系统`, `CEO`, `紧急`, `Acrne`, `重复` or `budget` trigger the other attacks. `clean` or `正常` gives a clean invoice.
- In Controls, pause payments, then submit anything on the bounty: the chain step comes back `Paused`.
- The seeded `SetPayout` to an unknown address counts down from about 95 seconds. Cancel it, or let it run out and execute it.
- In the Inbox, keep "Both agents" selected and click "Hidden white text changes the payout". The guard refuses on the left; the naive agent is blocked on-chain on the right. Stage invoices never get lucky past the guard in the mock, so rehearsals are predictable.

## Mock vs live

`src/api/client.ts` picks the API at build time from `VITE_API_MODE` (`.env.mock` sets it to `mock`). Both implement the same `Api` interface, so pages never know which one they're on.

`src/api/mock.ts` simulates the pipeline step by step with realistic delays, checks rules in the contract's order (paused, inactive vendor, closed PO, budget, daily cap), and simulates owner actions with a 120-second time lock.

## Controls in live mode

- Connects an injected wallet (MetaMask, OKX Wallet and others are discovered automatically) and offers to switch or add chain 677 or 968.
- If the connected address isn't `owner_address` from `/api/config`, owner buttons are disabled. Execute still works, because anyone may execute a change once its wait is over.
- Every write is sent as a legacy transaction (BOT Chain has no EIP-1559). After the receipt, the page posts the hash to `POST /api/team/owner-tx`, since the public RPC has no `eth_getLogs`.
- Amounts are typed in token units and converted with `token.decimals`. Budget expiry dates are stored as 23:59:59 China time on that day.

## The ABI

`src/abi/Countersign.ts` is written by hand from SPEC §2 for now. Once the contract builds:

```bash
cd ../contracts && forge build && cd ../frontend && npm run abi
```

That overwrites it from `contracts/out/Countersign.sol/Countersign.json`.

## What the backend has to send

SPEC §3.9 lists every endpoint and shape; `src/api/types.ts` is the source of truth. The parts most easily missed:

- **Attempt:** `preview_url` (`/api/attempts/{id}/preview.png`, page 1 rendered at upload, so hidden-text boxes land on the real file), `hidden_text.page_size` (`[width, height]` in PDF points; span bboxes use a top-left origin), `file_name`, `input_kind`, `nickname`, `source`, `tx.network`.
- `GET /api/attempts/{id}` must answer a bounty phone without the admin token. Match on the `X-Device-Id` header.
- **Stage invoices:** `GET /api/team/demo-invoices` lists manifest entries with `stage: true`; `POST /api/team/attempts` accepts `demo=<name>` instead of a file.
- **Registry:** `agents: [{address, label, active, balance, gas}]`, with `gas` set to `sponsored` or `self`.
- **Ledger events:** `summary_en` and `summary_zh` for rule-change rows, and `network` when bounty and team transactions are on different chains.
- **Config:** `timelock_seconds` (shown on Controls buttons) and `bounty_network` (the bounty page shows a testnet note when it's `testnet`).

## Layout

```
src/
  api/          types.ts (API shapes), client.ts (live API + switch), mock.ts
  abi/          Countersign.ts
  components/   Seal (round seal, small marks, brand seal), StepRow (会签栏),
                Counters, InvoicePreview, Header, Toggles (中文/EN, theme), ServerBanner,
                bits (Address, TxLink, Countdown, AdminGate, EvalCard)
  i18n/         strings.ts (zh + en), index.tsx (provider, tr helper)
  lib/          format, reasons (Reason enum + labels), attempt, changes, device, upload (photo shrinking),
                net (server-down flag), theme, wagmi
  pages/        Bounty, Ledger, Inbox, Controls (lazy, carries wagmi and viem)
```

Manrope and Geist Mono are bundled locally; the Manrope license is in `public/fonts/`. Chinese uses the system font stack. No request leaves for a CDN or Google Fonts.
