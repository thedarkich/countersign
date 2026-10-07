# Backend launch status — 7 October 2026

The backend can process an invoice end to end on BOT testnet. A real Qwen Flash rehearsal paid 0.05 tUSDT to a registered vendor and returned a verified receipt. The [read-only HTTPS testnet preview](https://139-180-194-19.sslip.io/#/ledger) is deployed and verified; full public bounty/mainnet launch gates remain below. The frontend team owns all UI/UX work.

## What is implemented

| Area | Working backend behavior | Remaining acceptance |
|---|---|---|
| Invoice processing | Bounded PDF/photo/text ingestion; rendered private previews; vision extraction, hidden-text inspection, vendor/PO matching, guarded and deliberately naive paths | More real Chinese/photo quality checks; reliable adversarial stage examples |
| Payments | Exact base-unit amounts; duplicate identity by vendor + invoice number; legacy signing, per-agent nonce serialization; verified Paid/Blocked receipts; transfer reverts remain errors | Mainnet funding/deployment/owner setup and live attack rehearsal |
| Recovery | Persist signed hash before broadcast; restart marks interrupted work; read-only receipt/calldata reconciliation; one process owns a data directory; never automatically resend | Rehearse deployed restart during a controlled demo, with adequate gas and monitoring |
| History | Blockscout discovery with bounded range splitting; canonical RPC receipt verification; durable cursor; overlap/lag; scoped reorg rebuild and private archived evidence | Explorer-dependent coverage is disclosed; cannot claim an independent complete chain archive |
| API/security | Existing frontend shapes preserved; authenticated team routes; private preview access; sanitized bilingual errors; process-isolated parsing; upload deadlines/concurrency limits; durable submission and AI call reservations; ID-only queue; cancellation-safe batch preparation | Final phone/WeChat app test and team frontend integration |
| Reputation | Public `/api/reputation`; chain/vault/address identity, source/scenario/model/guard breakdowns, evidence links and coverage/staleness | Frontend team integrates the additive route in Ledger/Controls; see handoff |
| Rehearsal tooling | Generator produces 20 clean + 20 clean holdout + 24 poisoned PDF/image fixtures; active run manifest; run/batch/seed CLI | Attack reliability unvalidated; clean batch and seed runs require a larger authorized AI allowance |
| Evaluation | Grouped 60/40 split, seed 42; separate clean holdout; training-only v2 examples; offline rules/guard comparison, counts/Wilson intervals and conditional promotion eligibility | Collect eligible attacks, authorize paid evaluation, run heldout once, report real results; live guard stays v1 |
| Operations | Locked Docker image, non-root runtime, Compose/Caddy, persistent data path, health/readiness separation, private SQLite backup command | Final launch gates below; HTTPS preview and backup/restart checks passed |

## Verified evidence

- **137 unit/API tests** and **19 isolated Anvil integration tests** pass. Ruff passes. Anvil uses the actual vault with disposable accounts and mocked models, never public funds.
- Live **clean Chinese invoice**: two Qwen Flash calls, no retries, 0.05 tUSDT paid. [Confirmed receipt](https://scan.bohr.life/tx/0x69ab3f76a936ba4543fdd0f7f9dec6825580500b1f6ba4d66b1917ee8372f357). This proves one clean flow; it does not prove attack catch rates or average latency.
- Pipeline latency was **47,503 ms**. Recorded stages: extraction 11.93 s, matching 2.05 s, guard 8.90 s, chain 4.77 s; initial registry reads account for most remaining time. RPC and model latency need more work before promising fast responses.
- Read-only historical discovery verified **21 vault events** through block **25971526** in the initial probe. The isolated VPS container served registry/ledger/reputation and the built frontend; private routes rejected unauthenticated requests and public submission returned 503 while closed.
- Public HTTPS verification passed: chain 968, three vendors, 19.85 tUSDT vault balance, 21 displayed ledger events including the live AI receipt, two reputation identities, fresh coverage, 401 for unauthenticated team access and 503 for closed bounty admission. A verified SQLite backup and controlled restart retained all displayed receipts. The health endpoint correctly reports AI/transactions/bounty disabled.
- The generator passed ingestion checks for all 64 fixtures. All `stage` flags remain false. Run `LAUNCH1` has one paid invoice: generate a fresh run ID before a full batch; never reuse paid invoice numbers.
- Evaluation planning reports **0 eligible train attacks, 0 held-out attacks, 20 held-out clean**. No paid evaluation ran, no score was invented, and no v2 prompt was activated.
- Existing **92 contract tests** passed at the earlier contract milestone; contract code is unchanged by this backend release.

The [focused backend security review](security/BACKEND_REVIEW.md) records three fixed resource/cost-control gaps and their remaining boundaries. No new paid tests were required. Security/admission image `a962754` is deployed and healthy. A network-disabled smoke also verified stored-input revalidation, path confinement and private file creation. HTTPS checks retained all 21 displayed receipts; a controlled slow upload returned 408 after 15.2 seconds while reads stayed available. AI, transaction, bounty and batch admission remain disabled.

## API handoff

[Backend/frontend handoff](BACKEND_HANDOFF.md) documents the stable API, the new reputation schema and remaining UI work. [Deployment and recovery](DEPLOYMENT.md) covers operation and rollback. [Backend README](../backend/README.md) provides commands.

The `money_lost` field measures outflow outside registered payout addresses, not all possible fraud. A fabricated invoice can still pay a registered vendor within budget. A policy block or execution error alone does not prove fraud. The deliberately naive agent must remain labelled as a demo comparison.

## What still blocks full launch

1. **Real attack and batch rehearsal:** validate chosen stage attacks, test both agent paths, run the 20 clean invoices, and review actual latency. The current ~$2 account allowance authorizes only small tests, not unattended batches, public AI traffic or evaluation.
2. **Mainnet:** fund BOT, deploy, and have the human owner complete setup/signatures. Team screens/stage demo must use mainnet for final track acceptance; the preview is explicitly testnet. Sponsored gas remains unconfirmed, so use self-funded gas.
3. **Public bounty:** obtain organizer permission and a funded operating allowance before enabling admission. Testnet is the configured bounty fallback; public-event permission is still required.
4. **Production configuration:** install only the required agent/provider credentials on the VPS privately, preserve the generated admin/privacy settings, and enable each runtime switch only for its authorized workload. No mainnet owner key belongs on the server.
5. **Team integration and device check:** connect the reputation display, preserve truthful loss/network/status labels, then test the actual HTTPS application on mobile data and WeChat. Earlier connection-page checks do not count as final app acceptance.
6. **Learning loop and submission:** collect attacks, perform the fixed held-out comparison once, keep v1 unless v2 catches more without more false alarms, and finish evidence/video/team/license/submission details. The separate Sepolia/Public Good lane remains optional.

Additional multipart batch-upload mode is not implemented; the existing UI's JSON clean-manifest batch route is implemented. No phase-completion tag is claimed while its acceptance gates remain open.
