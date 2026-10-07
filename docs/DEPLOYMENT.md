# Backend deployment and recovery

The frontend team owns `frontend/`. Backend changes preserve the existing HTTP response shapes. New internal recovery fields are filtered from public responses. The build packages the team's frontend unchanged.

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
- Image: `countersign-api:ffa05c4`; server release directory `/opt/countersign/releases/ffa05c4`. Previous `c2c5de5` image/release retained for rollback.
- Persistent data: `/opt/countersign/shared/data`, UID/GID 10001. Generated admin/privacy settings are in that release's private `deploy/runtime.env`; preserve/reuse the configuration on the next release without printing it. No agent/provider/owner/deployer key was installed for this preview.
- Latest security rollout backup: `/opt/countersign/shared/data/backups/pre-security-ffa05c4.db`, integrity checked before replacement. The new image passed parser and persistent-budget smoke tests with networking disabled. External HTTPS verifies unchanged receipts and closed admission; one incomplete upload returned 408 after 15.2 seconds while health reads remained available.
- Live containers: `countersign-api-1` (healthy, internal port only) and `countersign-caddy-1` (80/443). Previous connectivity containers remain stopped for rollback. The loopback QA container is stopped.
- TLS/HTML/config/registry/ledger/reputation checks passed. AI, transactions, bounty and batches are disabled. The non-green readiness response is expected for this closed preview.
- Verified backup: `/opt/countersign/shared/data/backups/preview-c2c5de5.db`; a controlled API restart retained all 21 displayed ledger events, including the real AI testnet receipt. A restart with no in-flight jobs is not a live crash-during-broadcast rehearsal; that case has isolated Anvil coverage.

Use this environment prefix with operational commands on this release:

```bash
cd /opt/countersign/releases/ffa05c4
export IMAGE_TAG=ffa05c4
export COUNTERSIGN_DATA_DIR=/opt/countersign/shared/data
docker compose -f deploy/docker-compose.yml ps
```

## Upload and model resource controls

The API admits at most eight simultaneous modifying requests and allows 15 seconds for each complete upload body; the deadline does not reset per chunk. At most two document parsers run concurrently. Each Linux worker has 384 MiB address-space, 6 CPU-second, 12 wall-second and 24 MiB result limits. Native parser processes are terminated/reaped on cancellation or failure. These processes run under the same OS user; do not describe them as a full filesystem/network sandbox.

AI call reservations use an additive SQLite table shared by API/operator/evaluation runtimes. Reservations commit before provider access and survive restart, even for failed or uncertain requests. Keep this database in persistent storage. Restoring an earlier backup can lose recent reservations; keep AI disabled after restoration until the previous rolling-hour window has expired or usage has been independently reconciled. Calls made before this patch are not reconstructed. A call limit does not enforce a dollar budget. All existing paid-work and public-launch gates still apply.
