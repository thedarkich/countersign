# Backend overview — 7 October 2026

The core invoice workflow and the HTTP layer now exist. The frontend can submit work, poll progress, display private invoice previews, read registry/ledger data and report owner transactions to the backend. This is a locally verified development milestone, not a public launch or a completed production payment system.

## Component status

| Component | Implemented and checked | Still required |
|---|---|---|
| Invoice ingestion | PDF, image and text; size/page/pixel bounds; private rendered previews; hidden-text inspection | Generate the actual demo dataset and validate real Chinese/photographed invoices |
| AI processing | Extraction, matching, guarded/naive decisions, five processing steps, model/version/source metadata, bounded TokenRouter calls | Real-fixture quality checks, reliable stage attacks and funded evaluation |
| Payment execution | Legacy transactions, per-agent nonce control, identity checks, Paid/Blocked/error separation, exact amounts and duplicate hashes | Live AI-to-testnet rehearsal, then funded mainnet acceptance |
| Storage and workers | SQLite attempts/events, three workers, bounded queue, durable rate buckets and batch records | Automated read-only recovery of interrupted/broadcast-but-unconfirmed attempts |
| HTTP API | Public and team routes, admin authentication, submission validation, private previews and redacted responses | Optional multipart batch-upload form; deployment hardening and acceptance |
| Chain state | Verified config/registry snapshots, periodic refresh, balance/pending-change reads, idempotent receipt storage and owner-tx reporting | Blockscout pagination/backfill, missing-event recovery and reorg repair |
| Statistics and ledger | Network/vault filtering, separate bounty/seed counters, receipt-backed sums, bilingual ledger labels, neutral leaderboard summaries | Complete-history coverage and public coverage/staleness indicators |
| Agent reputation | Proposal identity, model/guard version and source are persisted as inputs; UI has a bounded activity summary | SPEC §3.11 persistent public read model, evidence links, suspicion rules and coordinated UI/types/client/mock update |
| Learning loop | Evaluation-safe pipeline switch and an endpoint that reads a result file | Dataset splitting, offline runner, false-alarm metrics, confidence intervals and conditional v2 rollout |
| Hosting | VPS connectivity/HTTPS preparation exists; API can serve built frontend files | Application image, Compose/Caddy configuration, persistent volumes, deployment and phone/WeChat acceptance |

## Available routes

- Public: `GET /api/health`, `/api/config`, `/api/registry`, `/api/stats`, `/api/leaderboard`, `/api/ledger`, `/api/eval`; `POST /api/bounty/attempts`; `GET /api/attempts/{id}`.
- Private preview: `GET /api/attempts/{id}/preview.png`, available to the admin or the originating bounty device only.
- Team: submissions/listing under `/api/team/attempts`, demo manifest `/api/team/demo-invoices`, clean-folder batch creation/status under `/api/team/batch`, and `/api/team/owner-tx` receipt reporting. Every team route requires the admin bearer token.

Unrelated callers receive only an attempt's outcome, without invoice text, extraction, proposal, step details or preview access. Rate limits persist in SQLite: 3/minute and 30/day per device, 30/day per normalized nickname, 60/minute globally. Shared venue IPs are not throttled as one person; only salted IP hashes are stored privately. These limits reduce abuse but are not identity verification or a monetary spending cap.

Bounty and paid-batch admission default closed. AI and transaction switches also default disabled. Runtime settings may explicitly enable authorized small tests. The mainnet owner signs in their own wallet; the backend only validates and indexes the resulting receipt.

## Evidence and its limits

- **81 unit/API tests passed:** persistence, pipeline outcomes, authentication/redaction, upload checks, rate limits, manifest confinement, batch isolation, restart behavior and response shapes.
- **8 Anvil integration tests passed:** actual contract with disposable accounts, including pinned state views, owner receipt validation and a complete mocked-AI pipeline.
- Frontend typecheck and production build passed. Browser checks exercised Inbox, preview, Controls, Ledger and Bounty against the real HTTP API with simulated AI/chain adapters.
- Read-only testnet state at block **25969339** confirmed the deployed vault, three vendors, three POs, two agents, six-decimal USDT and **19.9 tUSDT** balance. No credentials were loaded by that probe.
- Existing direct testnet payment/block proofs remain in [deployment evidence](deployments/testnet.json). They prove contract behavior, not that a real AI was fooled.
- No paid model calls or public-chain transactions were made for the API milestone.

The `money_lost` API field describes funds sent outside registered payouts, not total fraud losses. The existing UI label still needs the planned correction. A fake invoice can pay a genuine registered vendor within budget. Current counters use locally indexed events; without backfill they must not be advertised as complete chain history. Public reputation must distinguish suspicious proposals from successful defenses and must never declare proven fraud from a policy block alone.

## Next work, in order

1. **Reliability:** reconcile pending transaction hashes read-only, index missing owner/payment receipts and implement bounded Blockscout backfill with duplicate and reorg checks. Never blindly replay a payment after a restart.
2. **Rehearsal inputs:** generate clean, clean-holdout and poisoned invoice fixtures plus the stage manifest; add run/batch/seed CLI commands. Keep clean holdout out of training and clean-batch selection.
3. **Reputation:** aggregate by chain, vault and agent with source/model/guard version, evidence, deduplication and coverage/staleness. Wire the status into Ledger and Controls, and correct the loss label.
4. **Evaluation:** build device/seed-technique grouped splits, clean holdout checks and Wilson intervals. Disable duplicate/remaining-budget checks consistently during offline comparisons. Switch to v2 only for more caught attacks without more false alarms.
5. **Deployment and acceptance:** package the existing app for the VPS, perform a small explicitly bounded live-model testnet rehearsal, deploy over HTTPS, then check the real app from a mainland phone and WeChat.

Mainnet requires BOT funding and owner setup. Public bounty launch still depends on organizer permission and authorization for public AI usage beyond the current small-tests budget. Testnet development, mocks, recovery, reputation, fixtures and evaluation tooling can continue without those answers. Optional sponsored gas and the separate Sepolia/Public Good lane follow the working core.
