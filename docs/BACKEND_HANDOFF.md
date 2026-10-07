# Backend handoff to the frontend team

Frontend/UI/UX belongs to the team. At the user's request, the 7 October integration imports their frontend presentation and adapts it to this backend; see [integration notes](FRONTEND_INTEGRATION.md). Existing HTTP response shapes remain compatible with `frontend/src/api/types.ts`. Backend-only proposal fields such as `amount_base` are private and filtered from those responses.

Read-only deployed preview: [Ledger](https://139-180-194-19.sslip.io/#/ledger), [API config](https://139-180-194-19.sslip.io/api/config), [reputation](https://139-180-194-19.sslip.io/api/reputation). Paid processing is closed; the preview does not consume model credit.

## Existing contract

- Public reads: `/api/health`, `/api/config`, `/api/registry`, `/api/stats`, `/api/leaderboard`, `/api/ledger`, `/api/eval`, `/api/attempts/{id}`.
- Bounty submission: multipart `POST /api/bounty/attempts`, with `X-Device-Id` and the existing fields. Closed admission returns a bilingual 503.
- Team routes: bearer-authenticated `/api/team/attempts`, `/api/team/demo-invoices`, `/api/team/batch`, `/api/team/batch/{id}`, `/api/team/owner-tx`.
- Private image: `/api/attempts/{id}/preview.png`, authenticated with admin bearer or the originating device. Use the existing authenticated blob-loading flow.
- `/api/eval` returns `{}` until real results exist. Do not fill that state with simulated scores in the live client.
- The API is served from the same HTTPS origin as the production bundle. Local Vite development already proxies `/api` to a local backend. A local backend with simulated adapters/mocks is sufficient for UI work; do not distribute signing keys or provider credentials to frontend builds.

## New additive endpoint

`GET /api/reputation?network=testnet&limit=20` needs no authentication. `network` is `testnet` or `mainnet` (default: team network); `limit` is 1–100 recent observations **per agent**. Counters cover all stored scoped observations, not just that recent list. Unavailable initial chain state returns a bilingual 503. A previously verified in-memory snapshot may be served with `coverage.stale=true` and `CHAIN_STATE_STALE` after a refresh failure.

The authoritative JSON Schema is [REPUTATION.schema.json](REPUTATION.schema.json), generated from the backend response model. Root shape:

```text
{ agents: AgentHistory[], updated_at: ISO timestamp, coverage: Coverage }
```

`AgentHistory` includes stable `id` (chain:vault:address), identity fields, guarded/naive label, bilingual role/status labels, active state, first/last observed times, aggregate `counts`, `breakdown` by source/scenario/model/guard, and `recent_observations`. Unknown external receipts have source/scenario `unknown` and empty model metadata: never present them as proven AI activity.

| Field | Meaning |
|---|---|
| status | `no_history`, `no_flag_observed`, or `suspicious_observed` |
| counts.suspicious_proposals | Known attack led to a payment proposal, or a verified `PayoutMismatch`; both together count once |
| counts.known_attack_refusals | Successful defensive refusals; do not subtract reputation for these |
| counts.confirmed_payments / policy_blocks | Matched verified receipt evidence, not merely an application outcome string |
| counts.receipt_only / unverified | External receipt with unknown context / claimed chain outcome without indexed receipt proof |
| observation.evidence | `application_record`, `verified_transaction`, or both |
| observation.transaction_url | Verified transaction explorer URL, otherwise null |
| observation.reason_codes | `KNOWN_ATTACK_PROPOSAL` and/or verified contract reason; render as text, never HTML |
| coverage | Configured vault scope, observed block bounds, scan bounds, last sync, stale flag and gap codes |

Coverage always includes `OBSERVED_HISTORY_ONLY` and `EXPLORER_DISCOVERY_DEPENDENCY`. Other gaps include `INDEXER_DISABLED`, `BACKFILL_NOT_VERIFIED`, `INDEXER_STALE`, `BACKFILL_INCOMPLETE`, `BACKFILL_CATCHING_UP`, `REORG_REBUILD`, and `CHAIN_STATE_STALE`. Fresh data is still observed history, not a global agent score. Preserve history after revocation/key rotation; a new address has a separate identity.

Public observations contain fixed bilingual summaries, public addresses, model/version metadata and evidence links. They omit private invoice content, hidden instructions, device/IP identifiers and nicknames. Budget, duplicate, pause and execution errors alone do not receive a suspicious flag. A known fake invoice paid to an approved vendor stays suspicious even when outside-registry outflow is zero.

## Frontend integration checklist

Items 1–4 below are implemented by the teammate integration. Browser viewport checks passed; physical phone/WeChat acceptance in item 5 remains.

1. Add reputation types/live client/mock together, using the schema. Display in the existing Ledger and Controls workflows, retaining the naive demo label, evidence source and coverage warnings.
2. Render `money_lost` as “Funds sent outside registered payouts” (or equivalent), not total fraud losses. Show paid fake invoices to registered vendors separately.
3. Use `/api/config` for network/asset/vault identity. The current preview is testnet; final stage/mainnet activation is a separate gate. Keep declined/error/pending states distinct.
4. Preserve admin/device authorization for previews and team operations, and display “not open”/“not evaluated” states honestly. No approve-anyway button is part of this build.
5. Recheck responsive layouts, Chinese/English, mobile data and WeChat against the deployed build. No external CDN/font dependency should be introduced.

Coordinate any changes to existing response shapes with the backend before merging. This new endpoint does not change payment authority or owner signing.

## Agent creation and chat: current boundary

There is no user-facing agent/wallet creation API and no conversational transaction API. `agent` accepts the two configured roles, `guarded` or `naive`. The owner can authorize an address through the contract's delayed AddAgent operation; that does not provision a wallet, model process, user account or chat session. Typed invoice input is a single pipeline submission, not a conversation. Do not present mock Add Agent/chat controls as live functionality.

Proposal only, discussed 7 October: after core launch acceptance, a bounded assistant could explain payments/blocks/budgets and submit approved invoice requests through the same authenticated pipeline. It must not expose arbitrary wallet transfers, let conversation text alter the trusted registry, or bypass owner approval/time locks. Self-service agent creation additionally requires customer authentication/isolation, agent-to-vault ownership, secure key lifecycle, revocation and per-agent permissions/budgets. It is outside the current four-screen demo scope, and no implementation was started. This recommendation follows [OWASP's excessive-agency guidance](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) to minimize permissions/functions and enforce authorization downstream of the model.

## Model failure diagnostics — 7 October follow-up

Authenticated attempt step details can now contain safe codes for `MODEL_OUTPUT_INCOMPLETE`, `MODEL_OUTPUT_EMPTY`, `MODEL_OUTPUT_INVALID`, `MODEL_TIMEOUT`, `MODEL_AUTH_FAILED`, `MODEL_RATE_LIMITED` or `MODEL_PROVIDER_ERROR`; generic `MODEL_UNAVAILABLE` remains supported. Attempt response fields and terminal `error` behavior are unchanged. These are processing failures, not refusals, policy blocks or proof of fraud. Never turn the display into an automatic paid retry. Public anonymous attempts remain redacted; raw provider errors and rejected output are not returned. Latest backend verification is 151 unit/API plus 28 local-chain tests; real attack repeatability remains pending.

## Wallet-screening API addition — 7 October 2026

`GET /api/security/wallets?address=0x…` is public, read-only and typed as `WalletSecurityView`. Omit the address for feed readiness/provenance. Both live/mock clients are updated. Ledger/Controls preserve bilingual delay, evidence and freshness labels. `WALLET_SCREENING_UNAVAILABLE` closes bounty UI admission; `SCAM_SNIFFER_LISTED` is an off-chain refusal and, only after an attributable proposal, an application-evidence reputation signal. See [full API and operations](WALLET_SCREENING.md).
