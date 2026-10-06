# Frontend redesign — 2026-10-06

## Reference and provenance

The human explicitly requested the SpendMate direction using the [ETHGlobal showcase](https://ethglobal.com/showcase/spendmate-wmewx), three supplied screenshots and `high.mp4`. The locally supplied 141-second video was visually inspected at the agent-creation, agent-chat and transfer-request stages (approximately 21, 64 and 106 seconds). This does not verify the competitor's deployed safety behavior. The earlier source review remains in PROGRESS.md.

Borrowed presentation ideas: persistent sidebar, neutral dark surfaces, compact summary cards, wallet identity beside agent status, policy/budget visibility, searchable invoice activity and expandable evidence. Implemented directly in the existing Vite/React frontend. No SpendMate source, screenshot, video or branding is shipped; the temporary local video-review copy was removed. No new frontend dependencies. Countersign retains its bilingual outcome seals and four routes.

| Supplied file | SHA-256 |
|---|---|
| high.mp4 | DEDD22E500BAF7E150BAACF69D73C6E3A0678DC6D0D6FE610D3FFAAB230CE99B |
| default.jpg | FC9E02A1D7BC22BEBEA855336C57D45517A5F290D9AA6D0EDA343ED98D7A1D96 |
| default (1).jpg | DF975D4324ADD3565BA5DDB6F0CABB370A5DC6364E916252B7BC1CFECC38E463 |
| default (2).jpg | 9A8E5607BEC4BDF301B62EA3AC48B4EF99782DD3F610EB6B354526D3B87058A9 |

## Delivered behavior

- Ledger: four primary metrics with remaining counters retained, guarded/naive activity cards, wallet/evidence disclosure, QR and evaluation cards, existing receipt filters and projector view.
- Controls: vault summary, dedicated agent wallet cards, immediate revoke/pause controls, vendors, budget bars and delayed changes. Owner signing and API shapes are unchanged.
- Inbox: outcome counts for the current source filter, invoice/vendor/agent search, scenario cards and existing guarded/naive comparison and inspection drawer.
- Bounty: stacked form labels, clear optional payout address, agent selection, upload/message tabs and existing five-step outcomes. Public/team routes remain separated by the existing admin gate. Mock mode explains that any text opens the simulated team view.
- Responsive sidebar/mobile tabs; remembered light/dark and English/Chinese preferences; route changes return to the top. A matching local SVG favicon replaces the older standalone mark.
- Copy now states that naive agents propose payments, refusals stay in the Inbox, participant counts are approximate, and fake invoices can still pay real vendors within budgets.

Agent activity is a limited view of the latest 100 returned ledger events, filtered to the configured network. Only PayoutMismatch contributes to the redirection counter. No global trust score, permanent reputation verdict, model provenance or claim of independently verified invoices is introduced. Full evidence-backed reputation under SPEC §3.11, including chain/vault/agent identity and server-side history, remains backend work.

## Verification

- TypeScript typecheck, live production build and mock production build passed. Build logs are under `output/frontend-redesign/`; dependency annotation warnings remain non-fatal.
- Browser checks: 1440px desktop, 390×844 phone, English/Chinese, light/dark, no page-level horizontal overflow in the checked views. Wide Controls tables scroll within their panels.
- Hidden-white-text comparison: guarded refusal and naive PayoutMismatch block; invoice search narrows the visible rows.
- Bounty required-input validation and text submission: mock naive address-change attempt reached Blocked/PayoutMismatch with the five-step result.
- Mock pause changed Controls to Paused and exposed the delayed resume action. No wallet was connected or used.
- Ledger stage view at 1440×900 displays all counters, recent events and the large QR; mock disclosure is retained in stage mode.
- Checked browser logs show no app errors. Existing React Router migration notices and wallet-extension warnings were observed.
- Mock production preview is local-only at `http://127.0.0.1:4173/#/ledger`; the existing dev server remains at port 5173. Screenshots are in `output/frontend-redesign/` (ignored).

The ignore pattern `lib/` had excluded the supplied frontend helper source from Git. It is now `/lib/`, retaining root dependency exclusion while tracking `frontend/src/lib/`. The untouched helpers match the supplied baseline hashes; `theme.ts` only changes browser-bar palette values.

No paid model calls, chain transactions or VPS deployment were performed for this redesign. API wiring, complete public reputation, physical-phone/WeChat acceptance and public launch remain outstanding. General-purpose agent chat and automatic wallet creation remain deferred as recorded in the approved scope.
