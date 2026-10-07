# Wallet risk screening

The user approved Scam Sniffer integration on 7 October 2026. Both payment-agent paths now screen invoice and proposed payout addresses against a local snapshot of the free [Scam Sniffer address database](https://github.com/scamsniffer/scam-database). The vault contract and its reason enum are unchanged.

## What a result means

- `listed`: the exact EVM address appears in the downloaded source. The backend refuses payment before signing/broadcast. This is an off-chain refusal, not an on-chain `Blocked` receipt or proof of fraud on BOT Chain.
- `not_listed`: the address is absent from this snapshot. This does **not** establish safety, authenticate an invoice, or detect every scam.
- `unavailable`: no current negative clearance is available. Enabled screening holds payment processing when data is missing, malformed or stale.

The upstream free list has a **seven-day publication delay** and says it is refreshed every 24 hours. Its flat address list does not attach chain IDs or explain individual incidents. Our six-hour refresh does not remove the upstream delay. The paid real-time offering is not used. No paid model request is needed to refresh or query this feed.

Screening is an extra backend control. A compromised agent key can call the vault directly and bypass it; the contract's registered-recipient, budget, duplicate and authority checks still govern those transactions. The contract does not implement this database as an on-chain denylist. A fake invoice for an approved vendor can still pass if no other check catches it.

## Enforcement and evidence

1. Admission and worker startup require a usable snapshot before spending model credit.
2. After extraction/matching, screen the extracted payee and matched registry payout for both agents.
3. After a proposal is formed, screen its actual payee and selected registry payout again. This catches a changed recipient from the naive model and rechecks freshness after model latency.
4. A match stores `SCAM_SNIFFER_LISTED`, source revision and lookup evidence internally, finishes as `refused`, and sends no transaction. Missing/stale data becomes `WALLET_SCREENING_UNAVAILABLE`, not a fraud flag.
5. Bounty proposals stopped here still count as a proposed attack payment. Refusals before any proposal do not count as the AI being fooled.

Public agent reputation marks a listed payout proposal as suspicious only when our deterministic screening record attributes it to a real proposal. A model-generated reason code is insufficient. Rejecting a malicious input before proposing a payment is not agent misconduct. Evidence remains an application record; no transaction link is fabricated.

## Public interface

`GET /api/security/wallets` returns enabled/readiness/status, source and license links, pinned revision, last successful check time, source commit time, address count, delay and refresh-failure state. Add `?address=0x…` for one exact EVM address lookup. Invalid addresses return 422. The endpoint does not return invoice data, the full downloaded database, credentials or license contents.

The public Ledger includes lookup and provenance; Controls includes vendor payout badges. English and Chinese labels distinguish refusals from AI decisions and contract blocks. Mock mode explicitly reports disabled live screening, with no fabricated live feed result. TypeScript `WalletSecurityView`, live client and mock client match the response model.

## Operation

- `SCAM_SCREENING_ENABLED=true` by default. Turning it off is an explicit operator override, visible in the public endpoint; it is not a response to a transient download error.
- `SCAM_SNAPSHOT_MAX_AGE_SECONDS=172800` by default (48 hours since the last successful validation). Allowed range: 1–72 hours. This is cache freshness, separate from the upstream seven-day publication delay.
- The API loads a validated cache at startup, then refreshes in the background every six hours; failed refreshes retry after 15 minutes. An old snapshot retains its original check timestamp and stops authorizing negative results after expiry.
- Fixed HTTPS GitHub origins only; no redirects or environment proxies. Fetch commit metadata, then address data and GPL license at that same 40-character revision. Cap response size/time; reject invalid formats, digest mismatch, unexpected license and backwards source commit time. Retain the previous snapshot on failure.
- Cache is `DATA_DIR/threat-intel/scamsniffer.json`, atomically replaced with mode 0600, outside Git and Docker build context. Preserve it on the persistent data volume. Raw source JSON, SHA-256, original license and revision remain together.
- Run `cd backend && .venv/bin/python -m app.ops refresh-threat-intel` to validate/download a cache without signing or using models. This standalone command does not replace an already-running process's in-memory snapshot; that process uses its own refresh loop or loads the cache on restart.
- Public checks are local set lookups. Recipient addresses and invoice contents are not sent to Scam Sniffer or GitHub. Upstream trust is HTTPS plus the pinned GitHub revision; this is not an independently signed threat-intelligence feed.

## Source and license

Source: [scamsniffer/scam-database](https://github.com/scamsniffer/scam-database), [address data](https://github.com/scamsniffer/scam-database/blob/main/blacklist/address.json), [GPL-3.0 license](https://github.com/scamsniffer/scam-database/blob/main/LICENSE). Keep the data's license/provenance separate from our original implementation. No upstream executable code or bulk dataset is bundled in this repository or static frontend. Preserve the original license and matching source if distributing a downloaded dataset; this document does not relicense it.

Initial live validation: revision `d48bea2601a0fb7b4bdbcd833bf3860ae45ab7e6`, source commit 7 October 2026 03:55:12 UTC, 2,530 unique addresses. Counts and revisions may change on later refreshes.

Regression coverage includes both agents, invoice/registry/final-proposal matches, stale/missing/malformed feeds, expiry during a model call, redirects, oversized responses, failed-refresh preservation, source rollback, local lookups, public API validation, reputation attribution and continued vault enforcement for unlisted addresses.
