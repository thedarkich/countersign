---
name: countersign-demo-check
description: Use before launching the public bounty, before each rehearsal, before the feature freeze (Oct 7 21:30) and before judging (Oct 8 13:30), or when asked whether the demo is ready. Runs the Countersign readiness checklist and reports what fails.
---

# Is the demo ready?

Go through every item, run what can be run, and report a short table: item, pass or fail, evidence (a command output or a link). Don't fix things silently during the check. List failures first, then fix them in order of the build priority in `docs/PRODUCT.md`.

## Chain (BOT Chain track)

- [ ] Contract on mainnet 677, verified on Blockscout. Address and explorer link in `docs/PROGRESS.md`.
- [ ] Mainnet evidence: one `Paid`, one `Blocked` per stage reason (`PayoutMismatch`, `OverBudget`, `DuplicateInvoice`), and one time-locked change queued then executed. Links in PROGRESS.md.
- [ ] `cast call $CONTRACT_ADDRESS_MAINNET "paused()(bool)"` is `false`; `remainingToday()` covers the demo plus the clean batch.
- [ ] Each agent key has gas (`cast balance <addr> --rpc-url https://rpc.botchain.ai`), or `GAS_MODE=paymaster` and a sponsored test tx went through today.
- [ ] Budgets still have room for the batch. If not, queue new POs now: they wait out the time lock.

## Pipeline

- [ ] `uv run python -m app.cli run ../data/invoices/clean/<file> --agent guarded --network mainnet` ends `paid`.
- [ ] Each stage invoice (manifest `stage: true`) fooled the naive agent 5 out of 5 times on testnet, and the guarded agent refused it.
- [ ] Clean batch: 20 paid, 0 false alarms (or each false alarm written down with a reason).
- [ ] Qwen-VL answers within 10 s. If not, check the model names in `.env` against SPEC §4.1.

## Server and phones

- [ ] `curl -s https://<domain>/api/health` returns `{"ok": true}`.
- [ ] A mainland phone on mobile data opens the bounty page from the QR code **inside WeChat** and submits an attempt that finishes.
- [ ] A phone photo of an invoice (not a screenshot) goes through.
- [ ] The counters move within 5 s of an attempt.

## Screens

- [ ] `#/ledger?stage=1` on the projector at its real resolution: counters readable from the back, QR code scannable from a seat, a new attempt stamps the big seal.
- [ ] Inbox: "Both agents" plus a stage invoice shows guarded refused next to naive blocked, with a working explorer link.
- [ ] Controls with the owner's MetaMask on 677: pause, then queue Unpause and watch the countdown. Cancel a queued SetPayout.
- [ ] Mock mode is off on the server: no "Mock data" badge anywhere.
- [ ] The eval card shows real v1 and v2 numbers from `data/eval/results.json`, or is hidden. Never show mock numbers.

## Fallbacks ready

- [ ] Backup video of the full demo, recorded on Oct 7 evening, saved on two laptops.
- [ ] The laptop can run the whole stack without Docker (SPEC §8, laptop fallback) and phones on a hotspot can open it.
- [ ] Every explorer link in the README opens.

## Submission (Oct 8, by 11:00)

- [ ] README sections per SPEC §11, including what was built during the event and what was reused, with sources.
- [ ] `docs/SUBMISSION.md` mirrors the organizers' checklist, with mainnet links, transactions and addresses.
- [ ] Bounty numbers exported, with outside attempts and the seed set kept separate.
