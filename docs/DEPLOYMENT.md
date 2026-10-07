# Backend deployment and recovery

Latest verified release: **countersign-api:f7825b3**, `/opt/countersign/releases/f7825b3`, deployed 7 October 2026: open sign-up (no invite code) with per-account invoices. Each account sees only the team attempts, private details and previews it submitted (new `attemptowner` table); the admin token sees everything; the shared clean batch requires the admin token. Private configuration copied from `33226dc` unread with the `TEAM_INVITE_CODE` line deleted. Immediate rollback: `33226dc`. Backup: `/opt/countersign/shared/data/backups/pre-accounts-f7825b3.db`. HTTPS before/after: config, 21 ledger records, registry, stats and health unchanged; `/api/me` 401; team reads 401; closed bounty 503; no invite field in the served bundle.

Previous release: **countersign-api:33226dc** (first account release, invite-only). Accounts (`/api/register`, `/api/login`, `/api/logout`, `/api/me`; scrypt hashes, hashed durable sessions, rate limits) and the sign-in/create-account pages; tables `useraccount` and `usersession` are created at startup. Its rollback: `ddaffbd`. Backup: `/opt/countersign/shared/data/backups/pre-accounts-33226dc.db`. HTTPS before/after: config, 21 ledger records, registry, stats and health unchanged; `/api/me` 401 without a session; team reads 401; closed bounty 503. AI/payment/bounty/batch admission remains disabled. Use `IMAGE_TAG=33226dc` in that release directory with `COUNTERSIGN_DATA_DIR=/opt/countersign/shared/data`.

Previous release: **countersign-api:ddaffbd**, `/opt/countersign/releases/ddaffbd` (frontend-only: teammate landing layout and fox logo with our palette; backend code unchanged from `c56dded`). Its rollback: `abffa3c`. Backup: `/opt/countersign/shared/data/backups/pre-landing-ddaffbd.db`. Private runtime configuration was copied from `abffa3c` unread. HTTPS before/after comparison: config, all 21 ledger records, registry, stats and health unchanged; reputation changed only in sync freshness fields; team reads 401, closed bounty 503; new bundle `index-CPkmsbDs.css` and the logo served. AI/payment/bounty/batch admission remains disabled. For current operations use `IMAGE_TAG=ddaffbd` in that release directory with `COUNTERSIGN_DATA_DIR=/opt/countersign/shared/data`; older release entries below are historical.

When scripting `docker compose exec` over an SSH heredoc, give it `-T` and `< /dev/null`; otherwise it reads the rest of the heredoc as its own stdin and the remaining commands never run.

Previous release: `countersign-api:abffa3c` (landing motion effects and new hero copy), rollback `c56dded`, backup `pre-landing-abffa3c.db`.

BOT mainnet rollout: not yet executed. See [MAINNET_RUNBOOK.md](MAINNET_RUNBOOK.md), rehearsed on a local fork of mainnet.

The frontend team owns `frontend/`. Backend changes preserve the existing HTTP response shapes. New internal recovery fields are filtered from public responses. The build packages the integrated teammate frontend; the user-requested adaptation is documented in FRONTEND_INTEGRATION.md.

## Release preparation

Use a reviewed commit in a separate server release directory. Build context is the repository root:

```bash
docker build -f backend/Dockerfile -t countersign-api:<commit> .
```

The Docker ignore file excludes private environments, keys, uploads, previews, databases, dependency folders and local output. Runtime image contains locked Python dependencies, backend code, public deployment/registry metadata and the production frontend bundle. It runs as UID/GID 10001 with one worker. Runtime data is outside the image.

Copy `deploy/runtime.env.example` to `deploy/runtime.env` on the server and set mode 0600. Configure that file locally; do not print it or run `docker inspect`/`compose config` without output filtering because they can display credentials. Only the two agent signing keys belong in the application runtime. No owner or deployer key is needed. Keep AI, transactions, bounty and batches disabled until the corresponding acceptance and permission gates pass. Generate admin token and IP salt privately with at least 32 random bytes each before enabling team operations/public submissions.

Create a persistent data directory with ownership 10001:10001 before starting the container. Set `COUNTERSIGN_DATA_DIR` to its absolute server path (for example `/opt/countersign/shared/data`) for every Compose operation; the local default is `../data`. Copy public vendor/PO files and approved invoice fixtures there; preserve any existing database/uploads. Do not overwrite runtime data from a fresh checkout. An empty container data directory receives only the public vendor and PO metadata automatically.

```bash
docker compose -f deploy/docker-compose.yml config --quiet
IMAGE_TAG=<commit> docker compose -f deploy/docker-compose.yml up -d api
docker compose -f deploy/docker-compose.yml exec api python -m app.ops check
```

`ops check` prints readiness booleans and public network labels, never secret values. The Docker health check tests HTTP liveness; `GET /api/health` separately reports disabled services, gas/state/indexer degradation. A running container is not proof that bounty admission is authorized or that a funded payment flow passes.

## HTTPS cutover

Use the existing domain `139-180-194-19.sslip.io` and external certificate volumes `countersign_caddy_data` / `countersign_caddy_config`. After the API is healthy, stop the existing `countersign-connectivity-tls` container and start the Compose Caddy service. Retain the stopped connection page for rollback. Never delete the certificate volumes. Only Caddy publishes ports; the API is reachable over the internal Docker network. Caddy bounds request bodies, and the application applies the tighter file/body limits.

For rollback, stop the Compose Caddy service, then restart `countersign-connectivity-tls`. Switch application images only after saving a database backup. Preserve the runtime data volume across releases. New persistence tables are additive; no existing column is rewritten by this release.

## Recovery and indexing

The signed transaction hash and exact base-unit proposal are persisted before broadcast. Startup does not replay jobs. Every 20 seconds a separate read-only task checks a bounded set of completed/error attempts with hashes. It validates network, vault, signer, calldata, canonical receipt and event fields before repairing an outcome. Reverted transfers remain errors. Unknown or unavailable receipts remain unresolved; recovery never signs or sends.

Another task discovers historical logs through Blockscout and verifies them from RPC receipts. It pins the end block, scans overlapping ranges with a 128-block lag, and advances a durable cursor only after the range is verified. Full 1,000-log ranges are bisected; a full single block or exhausted request/receipt budget marks coverage incomplete instead of silently dropping events. Configure smaller `INDEXER_BLOCK_WINDOW` for dense activity. Every log still depends on the explorer's discovery completeness; do not describe this as an independent full-chain archive.

A changed checkpoint hash triggers a scoped rebuild for that network/vault. Orphaned/replaced events are copied to a private audit table before removal from active ledger/statistics. Recovered payments do not increment counts twice. Revoked or rotated agent addresses retain their original attempt attribution.

Indexer outage does not disable receipt submission or registry reads. `/api/health` reports `INDEXER_INCOMPLETE:<network>` while coverage is incomplete, catching up or stale. The configured deployment block must match the vault. If no explicit start is set, matching public deployment metadata is used; otherwise scanning starts at block zero.

## Backups and restart rehearsal

```bash
docker compose -f deploy/docker-compose.yml exec api \
  python -m app.ops backup /app/data/backups/pre-release.db
```

This uses SQLite's online backup, verifies integrity, creates mode 0600 and refuses to overwrite a file. Protect backups like private invoices. Copy them to a separate private storage location; the app does not automatically transmit them. Also preserve `data/uploads`, `data/previews`, the manifest and registry files. To restore, stop the API, retain the current database for rollback, restore the verified backup with ownership 10001:10001, then restart. Read-only receipt recovery/backfill repairs chain outcomes that arrived after the backup; it never recreates lost private invoice contents.

Before public launch: verify a bounded real-model testnet invoice flow, confirm budget and admission authorization, load the rehearsal fixtures, check gas/PO capacity, complete mainnet deployment/owner actions for the track, and test the HTTPS app on a mainland phone and in WeChat. Keep public bounty and paid batches closed until their gates pass.

Offline evaluation runs from the writable local checkout with explicit budget authorization; it does not run in the read-only production image. Review any generated v2 prompt and its held-out eligibility before packaging it. No deployment command automatically enables v2, AI spending or bounty admission.

## Verified deployment — 7 October 2026

- HTTPS preview: https://139-180-194-19.sslip.io/#/ledger (testnet, read-only).
- Image: `countersign-api:e0dcab4`; server release directory `/opt/countersign/releases/e0dcab4`. Previous `6fd9d14`, `c22ede6`, `a962754`, `ffa05c4` and `c2c5de5` images/releases retained for rollback.
- Persistent data: `/opt/countersign/shared/data`, UID/GID 10001. Generated admin/privacy settings are in that release's private `deploy/runtime.env`; preserve/reuse the configuration on the next release without printing it. No agent/provider/owner/deployer key was installed for this preview.
- Previous security rollout backup: `/opt/countersign/shared/data/backups/pre-security-ffa05c4.db`, integrity checked before replacement. The new image passed parser and persistent-budget smoke tests with networking disabled. External HTTPS verifies unchanged receipts and closed admission; one incomplete upload returned 408 after 15.2 seconds while health reads remained available.
- Latest admission-hardening backup: `/opt/countersign/shared/data/backups/pre-admission-a962754.db`, integrity checked before replacement. The new image passed stored-input revalidation/path-confinement/private-permissions smoke with networking disabled, then public HTTPS preserved all 21 displayed receipts and closed admission.
- Latest diagnostics backup: `/opt/countersign/shared/data/backups/pre-diagnostics-c22ede6.db`, integrity checked before replacement. The image passed a network-disabled diagnostic/fail-closed/call-accounting smoke; HTTPS verified all 21 retained ledger records, three vendors, two reputation identities, 401 for unauthorized team reads and 503 for closed public submissions. No paid credentials were installed; the existing frontend layers were reused.
- Latest RPC-read rollout backup: `/opt/countersign/shared/data/backups/pre-rpc-6fd9d14.db`, integrity checked before replacement. The image passed a network-disabled batch-read smoke; HTTPS before/after comparison preserved exact ledger rows, both agent histories, config/registry and frontend HTML hash. Chain 968, all 21 receipts, fresh coverage, unauthorized 401 and closed bounty 503 verified. No paid model calls or public-chain writes ran in this rollout.
- Frontend integration backup: `/opt/countersign/shared/data/backups/pre-frontend-e0dcab4.db`, integrity checked before replacement. Image `e0dcab4` passed production build and a network-disabled non-root bundle/import smoke. HTTPS before/after comparison preserved exact ledger rows (21), both agent histories, config and registry, while the frontend HTML changed. All lazy route/reputation assets and local font/license files return 200. Live browser checks passed for landing, ledger/reputation, closed bounty and Controls redirect to team access, with no browser errors. Previous image `6fd9d14` remains the immediate rollback. Processing flags and private settings are unchanged.
- Live containers: `countersign-api-1` (healthy, internal port only) and `countersign-caddy-1` (80/443). Previous connectivity containers remain stopped for rollback. The loopback QA container is stopped.
- TLS/HTML/config/registry/ledger/reputation checks passed. AI, transactions, bounty and batches are disabled. The non-green readiness response is expected for this closed preview.
- Verified backup: `/opt/countersign/shared/data/backups/preview-c2c5de5.db`; a controlled API restart retained all 21 displayed ledger events, including the real AI testnet receipt. A restart with no in-flight jobs is not a live crash-during-broadcast rehearsal; that case has isolated Anvil coverage.

Use this environment prefix with operational commands on this release:

```bash
cd /opt/countersign/releases/e0dcab4
export IMAGE_TAG=e0dcab4
export COUNTERSIGN_DATA_DIR=/opt/countersign/shared/data
docker compose -f deploy/docker-compose.yml ps
```

## Upload and model resource controls

The API admits at most eight simultaneous modifying requests and allows 15 seconds for each complete upload body; the deadline does not reset per chunk. At most two document parsers run concurrently. Each Linux worker has 384 MiB address-space, 6 CPU-second, 12 wall-second and 24 MiB result limits. Native parser processes are terminated/reaped on cancellation or failure. These processes run under the same OS user; do not describe them as a full filesystem/network sandbox.

AI call reservations use an additive SQLite table shared by API/operator/evaluation runtimes. Reservations commit before provider access and survive restart, even for failed or uncertain requests. Keep this database in persistent storage. Restoring an earlier backup can lose recent reservations; keep AI disabled after restoration until the previous rolling-hour window has expired or usage has been independently reconciled. Calls made before this patch are not reconstructed. A call limit does not enforce a dollar budget. All existing paid-work and public-launch gates still apply.

The waiting queue stores only attempt IDs. Keep stored uploads and selected fixtures until their jobs finish: workers read them again, enforce path/size limits and parse them in the isolated worker. Missing or invalid input becomes an error without sending a payment; there is no automatic retry. Batch preparation drops decoded images after each preview and cleans its new files on cancellation/error. Preview/upload creation is exclusive and private from the first write. Hard process crashes can still leave uncommitted artifacts; evidence retention/deletion remains an operator decision.

## External wallet feed

New runtimes enable Scam Sniffer screening by default and refresh the free pinned feed in the background; no model/provider credentials are used. Preserve `shared/data/threat-intel` alongside other persistent data. Missing or expired snapshots report `WALLET_SCREENING_UNAVAILABLE` and hold payments. Do not automatically disable screening during an upstream outage. Cache license/provenance and operator commands: [WALLET_SCREENING.md](WALLET_SCREENING.md).
