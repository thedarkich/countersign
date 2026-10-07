# Backend security review — 7 October 2026

Scope: the invoice upload boundary, native document parsing, queue/batch admission, and AI call accounting. This is a focused engineering review and regression pass, not an independent penetration test or proof that every attack is prevented. Frontend files and contract behavior are unchanged.

## Findings fixed

### CS-BE-01 — Native parser failure could disrupt payment processing

- **Rule:** FASTAPI-UPLOAD-001 / untrusted upload resource isolation. **Severity:** High when invoice admission is enabled; the current public preview has admission disabled.
- **Location/evidence before fix:** `backend/app/api/runtime.py`, `Runtime.ingest`, used `await asyncio.to_thread(ingest_bytes, data)`. `pipeline/ingest.py` loads native PyMuPDF/Pillow in that process. File/page/pixel bounds existed, but no parser CPU/address-space/wall limit. Cancelling an asyncio thread task does not stop native work; a native crash can terminate the API process.
- **Fix:** API, operator CLI and evaluation parse files in a fresh Linux interpreter. Each file has 384 MiB address-space, 6 CPU-second, 12 wall-second and 24 MiB serialized-result limits; core dumps and regular-file growth are disabled with resource limits. At most two API parsers run simultaneously. The parent bounds stdout, validates JSON, and kills/reaps the process group on timeout, failure or cancellation. No shell, pickle, inherited application environment or uploaded filename is used to start the child.
- **Evidence:** actual subprocess tests cover malformed files, crash, excessive allocation using the production limit function, timeout, oversized output and cancellation. PDF/JPEG success and white/tiny/off-page injection evidence are verified after serialization. Existing ingestion/guard tests remain green.
- **Residual boundary:** this is resource/failure isolation, **not** a filesystem/network sandbox. The worker has the same OS user and filesystem visibility. A native code-execution exploit is not contained by these limits alone. Keep the native libraries current; stronger UID/container isolation with no secrets/data mounts would be a separate deployment hardening step. No such exploit was demonstrated here.

### CS-BE-02 — Slow bodies and concurrent uploads could retain resources

- **Rule:** FASTAPI-UPLOAD-001 / bounded request resource use. **Severity:** Medium.
- **Location/evidence before fix:** `backend/app/api/security.py`, `RequestBoundary.__call__`, buffered POST/PUT/PATCH bodies with `await receive()` until completion. The byte cap existed, but there was no complete-body deadline or admission count. The Caddy configuration showed a size cap, not these application controls.
- **Fix:** one 15-second deadline covers the entire body, including chunked requests; drip-fed chunks cannot reset it. At most eight modifying requests are admitted at once, held through processing so completed bodies waiting for parser/RPC work remain bounded. Overload returns bilingual 503, timeout 408, oversized input 413; all retain no-store/security headers. Cancellation/disconnection releases capacity. GET requests do not consume upload slots.
- **Evidence:** tests exercise slow chunk streams, overload before body read, cancellation, subsequent capacity reuse, chunked over-size rejection, and GET access during upload saturation.
- **Residual boundary:** this limits per-process resource retention; it does not prevent distributed denial of service or all forms of service saturation. Existing device/nickname/global submission limits and the reverse proxy remain relevant.

### CS-BE-03 — Restart reset the paid AI call allowance

- **Rule:** application cost-abuse control. **Severity:** Medium when paid processing is enabled; paid traffic remains disabled on the preview.
- **Location/evidence before fix:** `backend/app/llm.py`, `ModelGateway._reserve`, counted calls in an in-memory `deque`. A new runtime began with an empty counter. Existing submission rate limits were durable, but the model budget was not.
- **Fix:** production gateways share a SQLite rolling-hour reservation table. A transaction with `BEGIN IMMEDIATE` counts and commits a reservation before contacting TokenRouter. API/CLI/evaluation runtimes use the same data directory budget. Failed, cancelled or uncertain calls retain their reservation. A storage failure prevents the provider call. The old memory-only option is retained for isolated injected unit-test gateways.
- **Evidence:** restart with a new engine/gateway still rejects a call after a failed provider response; simultaneous reservations across separate connections cannot exceed the cap; expiration restores capacity; storage failure results in zero HTTP calls.
- **Residual boundary:** this is a call-count cap, **not a dollar limit**. Changing/resetting the database or restoring an older backup can lose recent reservations; never do so to regain allowance. Historic calls made before this patch are not reconstructed. Budget settings/gates remain operator-controlled; no public paid traffic is authorized by this patch.

### CS-BE-04 — Queue item limits did not bound rendered-document memory

- **Rule:** FASTAPI-UPLOAD-001 / resource retention. **Severity:** Medium when invoice admission is enabled.
- **Evidence before fix:** the queue held `(attempt_id, document)` and batch preparation held every rendered document in `prepared`. A 60-item cap limits count, not decoded image/text memory. Idle workers also retained their last document while waiting.
- **Fix locations:** `backend/app/api/runtime.py:112` and `:147`, `backend/app/api/batch.py:31`, and `backend/app/api/submissions.py`. Queue entries are now only attempt IDs. Workers read stored inputs only from uploads/invoices, cap the actual read at 5 MiB + 1, and revalidate in the isolated parser. Batch admission releases each rendered object after saving its private preview. Workers drop finished documents before waiting for another job.
- **Evidence:** weak-reference tests prove rendered documents are not retained by waiting jobs, batch preparation, or idle workers. Queued uploads still complete normally; a missing/outside/oversized input becomes an error with no transaction, and the same worker then processes a valid job. Terminal job redelivery sends nothing.
- **Tradeoff/residual boundary:** files are parsed once for admission/preview and again when a worker is ready, adding bounded parser work. Stored files must remain available until processing completes. This removes queue-sized decoded payload accumulation; it is not a bound on total process RSS, persistent disk use or distributed attack volume.

### CS-BE-05 — Cancelled batch preparation could leave orphaned private previews

- **Rule:** FASTAPI-UPLOAD-001 / upload lifecycle. **Severity:** Low; the batch endpoint requires admin authorization.
- **Evidence before fix:** `create_batch` cleaned preview files only in `except Exception`; task cancellation derives from `BaseException` and bypassed that cleanup. Admission settings were checked only before waiting for the batch lock.
- **Fix locations:** `backend/app/api/batch.py:21` and `:65`, `backend/app/storage.py:7`. Cancellation/error cleanup removes only files created by the uncommitted batch and re-raises the failure. Admission gates are rechecked after waiting and before committing. Upload/preview writes create mode-0600 files exclusively and remove partial files after write failure without touching existing files.
- **Evidence:** cancellation, parse failure and a disabled admission gate all leave no new database jobs, queue entries or previews; prior evidence files remain intact. Tests also verify file permissions, refusal to overwrite and partial-write cleanup.
- **Residual boundary:** a hard process/host crash can still leave artifacts created before the database commit. Automatic retention/deletion of historical invoice evidence is not introduced by this patch.

## Security properties retained

The AI proposes; deterministic checks and the vault constrain payments. Vendor payout pinning, budgets, duplicate identity, revocation, pause, delayed rule relaxation and canonical receipt checks retain their existing tests. Failed transfers are errors, never marked paid. Hidden document text stays outside the initial vision request. Uploaded URLs are never fetched by application code. Private invoices/previews require the submitting device capability or admin authorization; public reputation does not reveal invoice contents or treat a refusal as fraud.

Fabricated invoices can still pay approved vendors within approved budgets. Reputation records observed proposals/outcomes and evidence; it does not prove a person's intent or invoice authenticity. Mainnet, real adversarial-stage reliability and public bounty launch acceptance are still pending in `docs/BACKEND_STATUS.md`.

Nine new HTTP-to-Anvil rehearsals verify these properties across actual upload, worker, signing, receipt and API boundaries. Controlled model doubles prove enforcement, not model accuracy. A separate two-call real hidden-PDF check produced one guarded refusal and one naive extraction error, with no transaction. Allowlisted diagnostic codes now distinguish incomplete/empty/invalid model output and transport failures without recording rejected content or provider bodies. Fourteen mocked regressions verify codes, no retries, no payments and privacy. This fixes an observability gap, not a newly claimed funds-loss vulnerability. Current regression totals are **174 unit/API + 31 Anvil tests**, Ruff clean; the deployment evidence below describes the preceding release.

## Batched RPC read integrity

The performance follow-up preserves chain-ID, bytecode and canonical-block checks while batching read-only views/native balances. Every batch includes an identity check and pinned block tags; IDs must be complete, unique integers and are mapped independently of reply order. Invalid envelopes, provider errors, wrong chains, malformed/noncanonical ABI, oversized responses or any failed chunk discard the entire read. At most 63 data reads plus identity are sent per batch and at most 2 MiB of decoded response bytes are consumed. Errors omit provider bodies and endpoints. No transaction signing path or public response shape changed, and no retry/redirect/partial-state fallback was added.

Twenty-three mocked tests cover hostile or incomplete responses and resource bounds; three disposable-chain tests cover policy changes after the pinned block, final block-hash mismatch and reads concurrent with a legacy payment. These are regression checks for a performance change, not a new claim that the previous sequential reader lost funds. The configured RPC remains trusted for state: chain ID and block-hash consistency do not cryptographically prove a malicious provider's responses. Public testnet business values matched in one before/after measurement; real-model reliability remains unresolved.

Protocol reference: [JSON-RPC batch response IDs](https://www.jsonrpc.org/specification), [eth-abi decoding](https://eth-abi.readthedocs.io/en/latest/decoding.html). SDK signatures were also checked against the installed locked dependencies.

## Validation and deployment

Regression commands: `ruff check app tests integration ../scripts/make_invoices.py ../scripts/configure_wallets.py`, `pytest -q`, and `pytest -q integration/` from `backend/`. All tests use mocked models and disposable/local-chain accounts. No paid model calls or public-chain writes are needed for this patch. **137 unit/API tests and 19 isolated Anvil integration tests pass**, with Ruff clean. The queue/admission release `a962754` was deployed and healthy after a verified private backup; it includes the queue/admission follow-up. Network-disabled smoke verified stored-input revalidation, path confinement and mode-0600 file creation. Public HTTPS preserved all 21 receipts and closed admission. The earlier `ffa05c4` rollout verified the upload deadline through Caddy. A network-disabled Docker smoke verified parser success/rejection and persistent budget exhaustion; public HTTPS retained all 21 displayed receipts, rejects unauthorized/closed submissions, and returned 408 after 15.2 seconds for one controlled incomplete upload while a concurrent health read passed. Full deployment evidence is recorded in `docs/PROGRESS.md`.

Reference guidance: [OWASP file upload controls](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [Python subprocess lifecycle](https://docs.python.org/3.11/library/asyncio-subprocess.html), [Linux/Python resource limits](https://docs.python.org/3.11/library/resource.html). The subprocess stream buffer setting alone is not an output-size limit; the parent explicitly counts output bytes.

Diagnostics follow-up deployment: image `c22ede6` is healthy on the same closed testnet preview after backup `pre-diagnostics-c22ede6.db`, a network-disabled smoke and HTTPS evidence-retention checks. Runtime/frontend success shapes are unchanged. See `docs/PROGRESS.md` for the two-call partial real-model rehearsal and its unresolved output-quality limitation.

RPC-read follow-up deployment: image `6fd9d14` is healthy after verified backup `pre-rpc-6fd9d14.db` and network-disabled smoke. Public HTTPS preserved exact ledger/registry/config/agent history values and the frontend HTML hash, with fresh coverage and the same private-route/closed-admission responses. Current validation is **174 unit/API + 31 Anvil tests**, Ruff clean. No paid calls or public-chain writes were made for this release.
