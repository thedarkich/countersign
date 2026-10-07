# Countersign backend

The invoice pipeline, transaction adapter and HTTP API are implemented. The four frontend routes have been exercised against the real local API with simulated AI/chain adapters. Funded-network end-to-end acceptance and public deployment remain pending. See [the full backend overview](../docs/BACKEND_STATUS.md).

## Implemented

- Bounded PDF/image/text ingestion, visual extraction, hidden-text inspection, vendor/PO matching and exact amount/invoice-hash conversion.
- Guarded and deliberately naive decision paths, five tracked steps, SQLite persistence, three workers and a bounded queue.
- Agent/network/vault snapshots, actual provider model IDs, guard version and server-derived scenario for later reputation aggregation.
- TokenRouter transport with paid calls disabled by default, bounded outputs, an hourly process-local call ceiling and no automatic paid retries. This ceiling is not a dollar budget.
- Legacy transaction signing, per-agent serialization, nonce resynchronization and receipt checks against the network, vault, agent and proposal. Reverts and unconfirmed outcomes remain errors. No `eth_getLogs` dependency.
- Public config/registry, attempts, stats, leaderboard, ledger and evaluation-result reads; authenticated team submissions, demo manifest, clean-batch runs and owner-receipt reporting.
- Admin authentication, durable per-device/nickname/global rate limits, upload validation, private preview access, sanitized bilingual errors and explicit public response projections.
- Pinned-block chain-state reads with a final canonical-block check, periodic refresh and persisted cache records; idempotent receipt-event storage. Fresh cached reads do not wait for a background refresh.

## Run locally

Use the Ubuntu checkout. Configure private settings locally using the variable names in `.env.example`; never commit runtime secrets.

```bash
cd ~/countersign/frontend
npm ci
npm run build
cd ../backend
uv sync --frozen
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000/#/ledger`. The API serves the frontend's production `dist/` when it exists. For frontend development, Vite proxies `/api` to port 8000. A configured vault is required for verified chain-state responses; unavailable state returns a sanitized 503, not invented balances.

`LLM_ENABLED`, `TRANSACTIONS_ENABLED`, `BOUNTY_ENABLED` and `BATCH_ENABLED` default to false and have separate purposes. The current approximately $2 allowance is for small tests only; public AI traffic and paid batches remain disabled. Mainnet owner signing is never part of this backend. Use one backend process: workers, model-call accounting and transaction locks are process-local.

On restart, unfinished attempts become `INTERRUPTED_REVIEW_REQUIRED` errors and preserve any broadcast hash. They are never automatically resubmitted. Read-only receipt reconciliation is still required before recovering those jobs. The persisted state cache is diagnostic; startup requests require a newly verified snapshot.

## Checks

```bash
cd ~/countersign/backend
uv run --frozen ruff check app tests integration ../scripts/configure_wallets.py
uv run --frozen pytest -q
cd ../contracts && forge build
cd ../backend
uv run --frozen pytest -q integration/
```

Recorded on 7 October: **81 unit/API tests and 8 isolated Anvil integration tests passed**. The default tests use synthetic documents, HTTP mocks and temporary SQLite files, without the project `.env`, real keys or paid requests. Integration tests deploy the actual vault on loopback Anvil with disposable accounts and mocked AI. They cover payments/blocks/reverts, concurrent nonces, resynchronization, receipt identity/deduplication, owner changes, registry reads and the full pipeline.

Browser verification covered authenticated Inbox submissions, private PDF previews, both-agent outcomes, Controls registry data, Ledger receipts and Bounty submission/polling. AI and chain responses were simulated. A separate read-only BOT testnet check at block 25969339 returned three vendors, three POs, two agents and a vault balance of 19.9 tUSDT. No paid AI calls or public-chain writes were made for this milestone.

Uploads are untrusted. PDFs are limited to 20 pages and 200,000 text-layer characters; images to 20 million pixels, in addition to the 5 MB file limit. Only two PDF pages are rendered; later pages trigger refusal in the guarded path. Hidden text does not enter the initial vision request. The naive path intentionally receives the full text layer. No uploaded URL is fetched. Offline evaluation disables only duplicate and remaining-budget checks.

## Remaining

Dataset/CLI, read-only receipt recovery and Blockscout backfill/reorg repair, persistent public reputation, evaluation tooling, deployment and real-model/funded-network acceptance. The clean-folder JSON batch used by the UI works; the specification's additional multipart batch-upload mode is not implemented. Statistics cover locally indexed receipts and do not yet claim complete chain history.
