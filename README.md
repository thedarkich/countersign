# Countersign

**AI does the paperwork. The chain holds the purse strings.**

**AI 做账，链管钱。**

Countersign is an invoice-payment demo for the 汉客松 S1 & ETH Wuhan 2026 hackathon. An AI agent reads an invoice and proposes a payment. A vault on BOT Chain checks the registered vendor address, approved purchase-order budget, daily cap and duplicate-invoice hash before paying. Risky policy changes wait through a time lock; immediate restrictions let the owner pause payments or revoke an agent.

The rules bound spending authority. They do **not** prove an invoice is genuine: a convincing fake can still pay a registered vendor within the approved limits.

## Status — 9 October 2026

**Hackathon result:** 1st place, Public Goods, and 2nd place, Main Track, at 汉客松 S1 & ETH Wuhan 2026. The Blockchain track result is still to be announced.

**The live demo is offline.** During the hackathon (7–9 October 2026) a public site at `139-180-194-19.sslip.io` ran the real backend: invoices read by a real AI model and paid or blocked by the vault on BOT Chain testnet, a public challenge, and a Wallet page that sent real BOT on mainnet. That server has been shut down. Everything it did is still public on chain (see [on-chain evidence](#on-chain-evidence)), and you can run the whole app yourself: [mock frontend](#try-the-frontend) or [backend and contract](#backend-and-contract-checks).

| Part | What it does |
|---|---|
| Inbox | Upload a PDF, image or text invoice. The AI reads it, the server checks hidden text, the vendor registry, budgets, duplicates and scam wallets, and an AI guard reviews it. A clean invoice becomes a `pay()` request that the vault checks again on chain. Each result shows what the AI found and which contract rules passed. |
| Vault | Solidity contract on BOT Chain testnet: vendor registry with payout addresses, purchase-order budgets, daily cap and duplicate-invoice check; new permissions wait through a time lock, restrictions are instant. |
| Wallet | Pay from your own MetaMask (or another browser wallet) on BOT Chain mainnet: link it by signature, keep a whitelist where a new address waits 60 s, set your own maximum, and the server checks every sent transaction on chain. These rules are enforced by the service, not on chain. |
| Accounts | Email sign-up; each account sees only its own invoices and wallet. Controls (the vault's owner page) can be limited to team accounts. |
| Challenge | A public bounty: try to trick the guarded agent into paying you. The vault only ever pays registered vendors at their registered addresses. |

See the [backend overview](docs/BACKEND_STATUS.md) and [deployment notes](docs/DEPLOYMENT.md) for details.

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
| `#/inbox` | Upload invoices and open a result to see the processing steps, what the AI found and which contract rules passed |
| `#/ledger` | Overview, agent wallets/activity, receipts and counters; `#/ledger?stage=1` opens projector mode |
| `#/controls` | Vendor payouts, budgets, agent keys, pause/revoke and delayed rule changes |
| `#/bounty` | The public challenge: submit an invoice or message and follow its processing steps |
| `#/wallet` | Pay from your own wallet (needs the live backend and a browser wallet; not available in mock mode) |

Mock activity is simulated; real chain evidence is linked below.

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

The guarded agent is the product: the Inbox and the public challenge always use it. A deliberately unguarded agent remains only for internal tests, to show that the vault still blocks what a fooled agent proposes. Transfer failures and other execution errors remain separate from policy blocks; failed transfers never count as paid.

Reputation describes observed payment-agent proposals, not vendor honesty or proven fraud. A refusal that stops an attack is not agent misconduct. See [product boundaries](docs/PRODUCT.md) and [exact specification](docs/SPEC.md).

## On-chain evidence

### Live demo, 7–9 October 2026

Real AI model, real transactions, uploaded through the Inbox:

- [Paid: a clean PDF invoice, 0.09 USDT to the vendor's registered address](https://scan.bohr.life/tx/0x6c9c9b03d3af6860a53e686f2ae516d5a43ce7680f8d66fd30ed5e0da72618da)
- [Paid: a clean text invoice](https://scan.bohr.life/tx/0x2eddb42ba52b9c2501fb245f34678b892e62e13510883e56f3a771d2009f9063)
- Payout changed to an attacker's wallet: the guarded agent refused it before signing anything; the unguarded test agent proposed it and the vault blocked it, [text](https://scan.bohr.life/tx/0xa3ffec8f49f338235cc3ea32ba6e762290a4b14975ad504f7a3e9b71d567a0f1) and [PDF](https://scan.bohr.life/tx/0xdee5da7cfa1eb76b1d72e4835a51832fb736977d0bda068cc2b111c9471b2a18)
- [Blocked: over the purchase-order budget](https://scan.bohr.life/tx/0x0f0d485ea19d7f1557e5f36738aff05f5deac290fa1690c3bb8b0370d327deaa)
- [Blocked by the contract alone: an invoice from a removed vendor that the AI found nothing wrong with](https://scan.bohr.life/tx/0x21eb8d2d67d90fa912755bcb33e7551cfe5572690751eeefb1bd06a092e69a6b)

Wallet page on BOT Chain mainnet (chain ID **677**), real BOT signed in the user's own MetaMask and verified by the service: [1](https://scan.botchain.ai/tx/0x17615a53bf9630473580b1b08d0c3fffea6f9ca065aa123255cb27c9d09a9777), [2](https://scan.botchain.ai/tx/0xbe20628e134e7d0a9f1c7c5908401949223a1c1e683b14ba8d6da0df5072b8b3), [3](https://scan.botchain.ai/tx/0xbf7740a347a70a0e4ec03194256bd165b86652dc669c60c59156202fc5bd31fb).

### Contract checks

BOT Chain testnet, chain ID **968**. Vault: [`0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B`](https://scan.bohr.life/address/0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B).

- [Paid: 0.1 tUSDT](https://scan.bohr.life/tx/0x5740d22bab9ea68e5293a39915da8f9e1039901856b3907044f5ec895b9ad0a4)
- [Blocked: payout mismatch](https://scan.bohr.life/tx/0x80b7a3de74dd44267062feb896c77c5dd09b03e83dc7d39853f04cf5aaa7242c)
- [Blocked: over budget](https://scan.bohr.life/tx/0x457da15f0b4f54f363077f7a0bdc3d3104b98a4489a474eeba0c9374d356f02c)
- [Blocked: duplicate invoice with a changed amount](https://scan.bohr.life/tx/0xf03ecdbbe816c16cf2693c34723379866626846c1a081657ce237ef9a49779f6)
- [Queued vendor change](https://scan.bohr.life/tx/0xe49dcc4a4b18e3050ad4dba8d60c944817c41726d3d876072827ef48e1df43cf) and [execution after the delay](https://scan.bohr.life/tx/0x6936331119488fe8856b8493ff9a5ee051664f4dd070c63484131e3b66cc6d2e)

The receipts above are direct scripted contract checks, not evidence that an AI was fooled. A separate real Qwen Flash clean-invoice rehearsal paid 0.05 tUSDT: [AI-to-testnet receipt](https://scan.bohr.life/tx/0x69ab3f76a936ba4543fdd0f7f9dec6825580500b1f6ba4d66b1917ee8372f357). It used two model calls and took 47.5 seconds. Full receipts/setup records: [testnet deployment](docs/deployments/testnet.json). The vault itself was not deployed on mainnet; mainnet use was the Wallet page above.

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

Last recorded results: **92 contract tests and 239 backend tests passed**, plus the isolated Anvil integration tests in `backend/integration/`. The default and Anvil suites use mocks/disposable local accounts; they do not spend model credit or broadcast public-chain transactions. Test details and limits: [backend README](backend/README.md) and [contract review](docs/security/CONTRACT_REVIEW.md).

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

## Wallet screening

Scam Sniffer screening is integrated into both agent paths, with a public lookup in Ledger. The free feed is delayed seven days; a missing or stale feed holds enabled processing. [Behavior, limits and source license](docs/WALLET_SCREENING.md). [Handbook criteria review and mainnet funding steps](docs/CRITERIA_REVIEW.md).

## License

MIT, see [LICENSE](LICENSE). Third-party skills under `.agents/skills` keep their own licences, listed in [THIRD_PARTY.md](.agents/skills/THIRD_PARTY.md).
