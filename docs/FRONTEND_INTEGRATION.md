# Teammate frontend integration — 7 October 2026

The user requested the frontend from https://github.com/yihao0220/countersign while preserving our changes. Presentation was imported from commit `898f9787965ee669fa68bef5ef56bf2812b3a4f5` (Refine landing page to match EconomyOS layout), then adapted to the existing backend. This is a selective frontend integration, not a merge of the teammate's backend or contract.

## Provenance and scope

Reused/adapted frontend files: `src/index.css`, `src/site.css`, `src/landing.css`, `src/main.tsx`, `src/components/{Header,SiteChrome,Icon,Seal,Toggles}.tsx`, `src/pages/Landing.tsx`, `tailwind.config.js`, and bundled Manrope font/license files. The teammate's visual design replaces the previous sidebar treatment. Existing license/provenance records remain; the Manrope OFL notice ships with the font. Added locked Lucide React and Geist Mono packages. Other dependency versions are unchanged.

Backend code, contracts, ABI, deployment metadata, registry, private environments and recorded history are retained. Do not copy the upstream local backend/auth service or its alternate contract ABI into this release.

## Adaptation to the deployed system

- Root is the new bilingual landing page. Hash routes for Inbox, Controls, Ledger and Bounty remain. Fonts/assets are served locally, with system Chinese fonts.
- `/login` validates the existing team bearer token against the API, then opens Inbox or Controls; `/signup` redirects there. There is no customer account/password service. Sign-out removes the token and cached team data. Owner changes still require the connected owner wallet.
- Retained authenticated blob loading for private invoice previews, device authorization, existing wallet connectors, chain 677/968 configuration, legacy writes and our actual ABI. Owner authorization is rechecked at submission; queued execution uses the server's ready flag rather than the browser clock.
- Ledger consumes `/api/reputation`, with types and mock behavior added together. Controls displays the same per-address status. The UI shows source/scenario/model/guard evidence, history coverage and stale gaps; no global trust score or fraud verdict is invented. Known fake invoices paid to registered vendors are separate from outside-registry outflow.
- Bounty checks readiness and disables submission when AI, transactions or bounty admission is closed. It remains readable. Live evaluation stays empty until actual results exist. The two agent roles remain fixed; chat and self-service provisioning are not introduced.

## Validation

TypeScript, production build and mock build pass. Ruff and all 205 backend tests (174 unit/API + 31 isolated Anvil integration tests) pass, with backend code unchanged.

Browser checks use the actual HTTP application with injected synthetic model/chain adapters and an isolated test database: invalid/valid team token; both-agent invoice comparison; paid/blocked reason display; authenticated preview image; owner controls disabled without a wallet; sign-out; public submission; reputation evidence including a known fake invoice paid within policy; Chinese/English and light/dark views. No paid model calls or public-chain writes occur in these checks. Mobile and projector layouts are checked in the in-app browser; physical mobile-data/WeChat acceptance remains a separate launch gate.

Deployment evidence and rollback release are recorded in DEPLOYMENT.md after HTTPS verification. Current public processing remains disabled unless separately authorized and configured.
