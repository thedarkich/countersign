# Countersign backend

Phase 2 is in progress. The invoice workflow and chain adapter are implemented and tested locally. There is no deployed API server yet.

Implemented:

- Bounded PDF/image/text ingestion, visual extraction, hidden-text inspection, vendor/PO matching and exact amount/invoice-hash conversion.
- Guarded and deliberately naive decision paths, five tracked steps, SQLite persistence, three concurrent pipelines and atomic job claiming.
- Agent/network/vault identity snapshots, actual provider model IDs, guard version and server-derived scenario for later reputation aggregation.
- TokenRouter transport with paid calls disabled by default, bounded outputs, an hourly process-local call ceiling and no automatic paid retries. This ceiling is not a dollar budget.
- Legacy transaction signing, per-agent serialization, one nonce-resync retry and receipt checks against the network, vault, agent and proposal. Reverts and unconfirmed outcomes remain errors. No `eth_getLogs` dependency.
- Idempotent receipt-event storage. Read-only reconciliation, owner-transaction reporting, periodic state caches and Blockscout backfill are still pending.

Run in Ubuntu:

```bash
cd ~/countersign/backend
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen ruff check app tests integration ../scripts/configure_wallets.py
```

The 57 default tests use synthetic documents, HTTP mocks and temporary SQLite files. They make no paid requests and do not use the project `.env` or real wallet keys. The private helper's tests generate disposable keys in memory and use temporary files only.

The seven integration tests start isolated Anvil nodes on loopback, deploy the actual vault and use disposable accounts. They cover successful payment, policy blocks, non-policy revert, concurrent nonces, resynchronization, receipt deduplication, identity checks, registry updates, and the full pipeline with mocked AI.

```bash
cd ~/countersign/contracts && forge build
cd ../backend
uv run --frozen pytest -q integration/
```

`LLM_ENABLED=false` and `TRANSACTIONS_ENABLED=false` are independent defaults. The current $2 allowance is for small tests only; public AI traffic and paid batches remain disabled. Mainnet owner signing is never part of this backend. Use one backend process: the worker semaphore, hourly model ceiling and transaction locks are process-local. A repeated job is never automatically resubmitted; interrupted jobs and ambiguous broadcast hashes require read-only receipt reconciliation before recovery.

Uploads are untrusted. PDFs are limited to 20 pages and 200,000 text-layer characters; images to 20 million pixels, in addition to the 5 MB limit. Only two PDF pages are rendered; later pages trigger refusal in the guarded path. Hidden text does not enter the initial vision request. The naive path intentionally receives the full text layer. No uploaded URL is fetched. Chain views provide payouts and remaining budgets. Offline evaluation disables only duplicate and remaining-budget checks.

Pending: API/auth/rate limiting and response projections, CLI, dataset generator, indexing recovery/backfill and caches, deployment, public reputation aggregation and frontend wiring. Real-fixture AI quality and funded-network end-to-end acceptance are unverified.
