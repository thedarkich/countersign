# frontend/: instructions for Codex

The existing UI runs on a mock API (`npm run dev -- --mode mock`) that simulates the whole pipeline, so every screen can be rehearsed without the backend. The human approved a SpendMate-based frontend redesign after current setup is complete. Read `README.md` in this folder and the latest decisions in `../docs/PROGRESS.md` first.

- **The human has requested a more user-friendly frontend using SpendMate as the design/reuse base.** That supersedes the earlier no-restyle restriction. Start after current Phase 0 setup, within the permitted coding window. Preserve the four core workflows and functional requirements while adapting layouts/components. Retain MIT notices and disclose copied code. General chat capabilities require their own defined scope; the redesign alone does not expand wallet authority.
- **The human also approved public payment-agent reputation.** Implement SPEC §3.11 in Ledger and beside agent keys in Controls during Phase 4. A suspicious-proposal flag needs attributable evidence; refusing an attack is not agent misconduct, and policy blocks/errors alone do not prove fraud. Preserve public/private data boundaries and source/network/version labels. This is planned scope, not a feature in the existing mock. No new screen or automatic spending authority is required.
- `src/api/types.ts` is the contract with the backend. The backend matches it, not the other way round. If a shape truly has to change, change `types.ts`, `client.ts` and `mock.ts` together, then run `npm run typecheck && npm run build:mock`. Use `$countersign-api-match`.
- Every user-facing string has a Chinese and an English version: in `src/i18n/strings.ts`, or inline with `tr(en, zh)` on the team pages. Write both, and keep them short and plain.
- Colours come from the CSS variables in `src/index.css`, so light and dark themes both work. Use the Tailwind names (`bg-field`, `text-ink2`, `border-rule`, `text-cinnabar`, `text-jade`, `bg-sheet`), never raw hex or `bg-white`. QR codes and invoice previews stay on real white on purpose.
- No CDNs, no Google Fonts, no external requests except `/api` and the wallet's RPC. Phones in mainland China, often inside WeChat, must load everything from our own server.
- Routes are hash routes (`/#/bounty`). Keep them; WeChat and the backend rely on that.
- After `forge build` in `../contracts`, run `npm run abi` to replace the hand-written ABI.
- Test in a real browser with `$playwright` at 390 × 844 (bounty, inside the phone viewport) and at the projector's resolution (`#/ledger?stage=1`).
