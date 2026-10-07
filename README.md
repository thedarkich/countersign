# Countersign

**AI does the paperwork. The chain holds the purse strings.**

**AI 做账，链管钱。**

Countersign is an invoice-payment demo for the 汉客松 S1 & ETH Wuhan 2026 hackathon. An AI agent reads an invoice and proposes a payment. A vault on BOT Chain checks the registered vendor address, approved purchase-order budget, daily cap and duplicate-invoice hash before paying. Risky policy changes wait through a time lock; immediate restrictions let the owner pause payments or revoke an agent.

The rules bound spending authority. They do **not** prove an invoice is genuine: a convincing fake can still pay a registered vendor within the approved limits.

## Current build — 7 October 2026

| Part | What works | What remains |
|---|---|---|
| Frontend | Four redesigned screens, English/Chinese, themes, mobile layout; local HTTP API flows checked | Live-model/funded-network acceptance and public deployment |
| Vault | Tested Solidity contract; verified BOT testnet deployment and real payment/block receipts | Mainnet funding and deployment |
| Backend | Invoice pipeline/API, recovery/backfill, reputation, fixtures/CLI, offline evaluation tools and Docker deployment | Stage attack validation, paid evaluation, mainnet acceptance and final public launch |
| Agent reputation | Public evidence-backed reputation API | Frontend integration in Ledger/Controls |
| Bounty and evaluation | Submission API and offline evaluation tooling | Approved public launch, real attack collection and paid held-out evaluation |

The frontend supports mock mode and the implemented local API. Browser API checks used simulated AI/chain adapters; separate read-only checks verified the deployed testnet vault. The [HTTPS preview](https://139-180-194-19.sslip.io/#/ledger) now serves the real backend and frontend on testnet. It is read-only: paid AI processing, transaction submission and public bounty admission are disabled. See the [full backend overview](docs/BACKEND_STATUS.md) and [current progress](docs/PROGRESS.md) for evidence and remaining work.

## Try the frontend

Use Node.js 20 and npm. On Windows, the project development environment is Ubuntu in WSL; keep the checkout in your Linux home directory.

```bash
git clone https://github.com/thedarkich/countersign.git
cd countersign/frontend
npm ci
npm run dev -- --mode mock
```

Open the local URL printed by Vite (normally `http://localhost:5173`). No API key, wallet key, backend or paid model call is needed for mock mode. The mock admin gate accepts any text token.

| Route | Demo |
|---|---|
| `#/ledger` | Overview, agent wallets/activity, receipts and counters; `#/ledger?stage=1` opens projector mode |
| `#/inbox` | Invoice review and both-agent comparison; try the hidden-white-text stage invoice |
| `#/controls` | Vendor payouts, budgets, agent keys, pause/revoke and delayed rule changes |
| `#/bounty` | Submit an invoice/message and follow its five processing steps |

In the Inbox, select **Both agents** and the hidden-white-text example: the guarded agent refuses while the naive agent proposes the changed payout and the mock vault blocks it. Mock activity is simulated; chain evidence is linked separately below.

```bash
npm run typecheck
npm run build:mock
npm run preview -- --host 127.0.0.1
```

More detail: [frontend README](frontend/README.md), [redesign and provenance](docs/FRONTEND_REDESIGN.md).

## How it works

```text
Invoice (PDF, photo or text)
  -> extraction -> hidden-text check -> vendor/PO match -> guard
       | refusal -> Inbox with reasons
       | proposal
       v
BOT Chain vault
  -> registered payout + PO budget + daily cap + duplicate check
       | valid -> Paid to registry address
       | rule failure -> Blocked(reason)

Owner: restrictions are immediate; risky policy changes wait.
```

The guarded agent is the intended product. The deliberately naive agent is a demo comparison. Transfer failures and other execution errors remain separate from policy blocks; failed transfers never count as paid.

Reputation describes observed payment-agent proposals, not vendor honesty or proven fraud. A refusal that stops an attack is not agent misconduct. See [product boundaries](docs/PRODUCT.md) and [exact specification](docs/SPEC.md).

## Verified testnet evidence

BOT Chain testnet, chain ID **968**. Vault: [`0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B`](https://scan.bohr.life/address/0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B).

- [Paid: 0.1 tUSDT](https://scan.bohr.life/tx/0x5740d22bab9ea68e5293a39915da8f9e1039901856b3907044f5ec895b9ad0a4)
- [Blocked: payout mismatch](https://scan.bohr.life/tx/0x80b7a3de74dd44267062feb896c77c5dd09b03e83dc7d39853f04cf5aaa7242c)
- [Blocked: over budget](https://scan.bohr.life/tx/0x457da15f0b4f54f363077f7a0bdc3d3104b98a4489a474eeba0c9374d356f02c)
- [Blocked: duplicate invoice with a changed amount](https://scan.bohr.life/tx/0xf03ecdbbe816c16cf2693c34723379866626846c1a081657ce237ef9a49779f6)
- [Queued vendor change](https://scan.bohr.life/tx/0xe49dcc4a4b18e3050ad4dba8d60c944817c41726d3d876072827ef48e1df43cf) and [execution after the delay](https://scan.bohr.life/tx/0x6936331119488fe8856b8493ff9a5ee051664f4dd070c63484131e3b66cc6d2e)

The receipts above are direct scripted contract checks, not evidence that an AI was fooled. A separate real Qwen Flash clean-invoice rehearsal paid 0.05 tUSDT: [AI-to-testnet receipt](https://scan.bohr.life/tx/0x69ab3f76a936ba4543fdd0f7f9dec6825580500b1f6ba4d66b1917ee8372f357). It used two model calls and took 47.5 seconds; attack reliability and average latency remain unmeasured. Full receipts/setup records: [testnet deployment](docs/deployments/testnet.json). Mainnet is not yet deployed.

## Backend and contract checks

Prerequisites: Python 3.11, uv and Foundry. Contract dependencies are intentionally not vendored; install them using the pinned commands in the [contract README](contracts/README.md).

```bash
cd contracts
forge build
forge test -vv
cd ../backend
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen pytest -q integration/
```

Recorded results for the current implementation: **92 contract tests, 108 backend tests and 19 isolated Anvil integration tests passed**. The default and Anvil suites use mocks/disposable local accounts; they do not spend model credit or broadcast public-chain transactions. Test details and limits: [backend README](backend/README.md) and [contract review](docs/security/CONTRACT_REVIEW.md).

The HTTP server is implemented: run `uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1` from `backend/`. It serves the production frontend build when present. Paid model calls, real transactions, public bounty admission and paid batches are disabled by default; the current model allowance is small tests only. See the [backend run instructions](backend/README.md).

## Working together

- Read [AGENTS.md](AGENTS.md), [PRODUCT.md](docs/PRODUCT.md), [SPEC.md](docs/SPEC.md), and the README for the component you change.
- The frontend team owns UI/UX; Codex focuses on the backend. Read the [backend handoff](docs/BACKEND_HANDOFF.md) for the additive reputation route. Keep interface changes coordinated across `frontend/src/api/types.ts`, the live/mock clients and the backend. The vault ABI is the chain interface.
- Work in focused branches and pull before starting. Update `docs/PROGRESS.md` with verified results and limitations.
- Use `.env.example` to learn configuration names. Never commit `.env`, wallet keys, provider credentials, uploads or databases. The mainnet owner key stays in the human's wallet.

## Provenance

The supplied frontend existed before implementation. [FRONTEND_BASELINE.json](docs/FRONTEND_BASELINE.json) records its file hashes, and commit `87135b1` records the supplied baseline and approved scope. The human explicitly authorized development before the original 20:00 schedule; subsequent commits retain their actual timestamps.

```bash
git log --format='%h %aI %s' 87135b1..HEAD
```

The redesign takes layout ideas from the user-supplied SpendMate screenshots/video and [ETHGlobal showcase](https://ethglobal.com/showcase/spendmate-wmewx). No SpendMate source code or media assets were copied into the application. Reused dependencies include React, Vite, Tailwind, wagmi/viem, OpenZeppelin and forge-std; versions are recorded in lockfiles and `contracts/dependencies.json`. Bundled third-party development skills retain their own [notices](.agents/skills/THIRD_PARTY.md).

This is a team development checkpoint. Final team credits, the project license, live bounty results, evaluation results, mainnet proof and the submission package remain to be completed; no missing result is presented as finished.

## Wallet screening and current acceptance

Scam Sniffer screening is integrated into both agent paths, with a public lookup in Ledger. The free feed is delayed seven days; a missing or stale feed holds enabled processing. [Behavior, limits and source license](docs/WALLET_SCREENING.md). [Handbook criteria review and mainnet funding steps](docs/CRITERIA_REVIEW.md). The current public preview is testnet and does not satisfy mainnet deployment acceptance.
