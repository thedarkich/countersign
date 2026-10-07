# Countersign backend

The invoice pipeline, authenticated HTTP API, transaction recovery, historical indexing, public agent reputation and operator tooling are implemented. A real Qwen Flash clean invoice paid 0.05 tUSDT on BOT testnet. Full bounty/mainnet launch remains gated. See [backend status](../docs/BACKEND_STATUS.md), [frontend handoff](../docs/BACKEND_HANDOFF.md), and [deployment](../docs/DEPLOYMENT.md).

## Run locally

Use the canonical Ubuntu checkout. Learn private variable names from `.env.example`; never commit or print runtime secrets.

```bash
cd ~/countersign/frontend
npm ci && npm run build
cd ../backend
uv sync --frozen
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000/#/ledger`. The API serves the production frontend build. Vite development proxies `/api` to :8000. Verified registry state requires the configured vault/RPC; failures return a sanitized 503 rather than invented balances.

`LLM_ENABLED`, `TRANSACTIONS_ENABLED`, `BOUNTY_ENABLED`, `BATCH_ENABLED` and `EVAL_ENABLED` default false. The current ~$2 allowance is for small tests; public AI traffic, batches and evaluation remain closed. Call limits are not dollar spending limits. Mainnet owner signing never belongs in this backend.

One process owns each data directory through a file lock. It runs three bounded workers. Startup marks unfinished attempts for review; signed hashes saved before broadcast are reconciled read-only against calldata and canonical receipts. Jobs are never automatically resent. Periodic Blockscout discovery verifies receipts, persists scan coverage and archives replaced evidence on reorg. `/api/reputation` publishes scope/staleness; it does not claim global fraud detection.

## Rehearsal commands

Generate without AI calls or transactions; it reads the configured vault and checks PO capacity. Confirm vault funds/daily capacity separately before a paid batch:

```bash
cd ~/countersign/backend
uv run --frozen python ../scripts/make_invoices.py --network testnet --run-id R2 \
  --attacker 0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b
```

Each new run generates 20 clean, 20 clean-holdout and 24 poisoned fixtures plus rendered previews. The active manifest contains only that run; old files remain for audit. Never reuse a paid invoice number. Generated files are local runtime data and ignored by Git. All stage buttons stay disabled until live-model reliability is actually established. A duplicate fixture uses the registered payout so the duplicate check is the intended failure; altered-payout behavior is exercised by other techniques.

After separately authorizing and configuring paid processing:

```bash
uv run --frozen python -m app.cli run ../data/invoices/clean/R2_invoice_000_zh.pdf --agent guarded --network testnet
uv run --frozen python -m app.cli batch --network testnet
uv run --frozen python -m app.cli seed --network testnet
```

Stop the API before these CLI operations: they share its data/nonce ownership. `batch` uses the active clean manifest only; holdout never enters it. `seed` processes the poisoned manifest with both agents. A processing error stops the CLI without automatically repeating paid calls. The UI's JSON clean-manifest batch route works; the additional multipart batch-upload mode remains unimplemented.

## Offline evaluation

```bash
uv run --frozen python -m app.eval.run
```

Default execution only prints dataset counts and a conservative model-call bound; no model calls or transactions. `--run` additionally requires `EVAL_ENABLED=true`, `LLM_ENABLED=true`, sufficient call allowance and actual user authorization beyond the current tests-only budget. Run it from the local writable Ubuntu checkout, not the read-only production image.

Attacks are grouped by public device or seed technique (60/40, seed 42). Clean training and holdout remain separate. Duplicate/over-budget attacks are excluded and those rules are disabled consistently; the LLM also receives no remaining-budget field. Stored attack extraction is reused identically across guards; clean extraction occurs once per input. Training examples are capped at 12 attacks and 6 clean invoices. No-invoice is not counted as a refused attack. Counts and 95% Wilson intervals use attempts, not independent people; grouping does not make correlated attempts independent.

An exclusive start marker prevents silent retries/tuning on the holdout, including after a failure. Private audit files record counts and eligibility; the public `results.json` matches the existing API. Failures do not become zero scores. The generated `guard_v2.md` remains local/private, is not automatically activated, and must be reviewed before deployment. Only promote when catch rate strictly improves and false alarms do not worsen; otherwise retain v1. See [SPEC §7](../docs/SPEC.md) and [Wilson interval reference](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

## Checks

```bash
cd ~/countersign/backend
uv run --frozen ruff check app tests integration ../scripts/make_invoices.py ../scripts/configure_wallets.py
uv run --frozen pytest -q
cd ../contracts && forge build
cd ../backend
uv run --frozen pytest -q integration/
```

On 7 October: **126 unit/API tests and 19 isolated Anvil integration tests passed**. Default/local-chain tests use synthetic inputs, temporary databases and mocked models; no project environment, paid calls or public-chain transactions. Tests cover recovery without resending, revert/policy distinction, prepared-hash persistence, reorg handling, canonical state/receipts, history bounds, reputation attribution/privacy, grouped evaluation and single-process ownership.

The separate real-model rehearsal used exactly two calls and paid 0.05 tUSDT: [receipt](https://scan.bohr.life/tx/0x69ab3f76a936ba4543fdd0f7f9dec6825580500b1f6ba4d66b1917ee8372f357). Its 47.5-second pipeline time is one measured sample, not a latency guarantee or attack-quality benchmark.

Uploads remain untrusted: 5 MB, 20 PDF pages, 200,000 text-layer characters, 20 million image pixels. Only two PDF pages are rendered; later pages trigger a guarded refusal. Hidden text stays out of the first vision request; the deliberately naive path receives the text layer. Uploaded URLs are never fetched.

Security hardening (7 October): file parsing runs in disposable Linux processes with CPU/memory/wall/output limits; uploads have a 15-second body deadline and eight concurrent modifying-request slots. AI rolling-hour reservations persist in SQLite across restarts, including failed calls. These are resource and call-count controls, not a full native-parser sandbox or dollar budget. See [focused backend security review](../docs/security/BACKEND_REVIEW.md).
