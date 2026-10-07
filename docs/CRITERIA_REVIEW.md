# Hackathon criteria and launch review — 7 October 2026

**Countersign is not yet ready to claim BOT mainnet acceptance.** The website and verifiable vault evidence currently use testnet 968. A mainnet wallet address, gas application or testnet deployment does not satisfy the handbook's valid-mainnet-deployment definition.

Source: the participant handbook supplied in this chat, titled “汉客松 S1 & ETH Wuhan 2026｜选手手册”, last updated 5 October 2026, especially §§1, 5.1.2, 5.2–5.3 and 6. This review follows that supplied version; subsequent organizer announcements may change details.

## Requirement comparison

| Requirement | Evidence / status | Remaining action |
|---|---|---|
| 1–5 people, on-site participation (§1) | Team collaboration exists; formal registration/attendance cannot be verified from this repository | Confirm registered team name, members/roles and attendance |
| Existing projects permitted, with prior work and reused sources disclosed (§1) | Baseline hashes, frontend integration provenance and actual Git timestamps exist | Include a clear prior-work/event-work statement in submission; include teammate/frontend and Scam Sniffer sources |
| Official window: 6 Oct 20:00–8 Oct 12:00, China time | Local instructions permitted development from 6 Oct 17:19; this is not evidence of an organizer rule waiver | Preserve timestamps; classify work before 20:00 as prior work unless organizers explicitly confirm otherwise |
| Runnable interactive product (§5.2) | Public HTTPS UI, ledger, reputation and wallet screening; authenticated invoice/control APIs; one real AI-to-testnet payment | Public preview has AI/payment/bounty processing disabled. Rehearse the actual core workflow for judges under an authorized operating budget |
| Project introduction: team, users, problem, functions and event work (§5.2) | PRODUCT/SPEC and progress history cover the product | Assemble a concise final entry with confirmed member names/roles and actual event additions |
| Repository, dependencies, startup/use instructions and attribution (§5.2) | Private GitHub repo with backend/frontend/deployment docs and preserved source notices | Ensure judges can access the code through organizer-approved access; a private link alone is insufficient for an uninvited judge. Do not make it public without the team's decision |
| Video **or** runnable link demonstrating core flow (§5.2) | HTTPS runnable link exists; read-only evidence is available | A short backup video is advisable, though handbook wording permits a runnable link. Show the real workflow, not only the landing page |
| BOT mainnet explorer links, tx records and applicable contract/app address (§§5.1.2, 5.2) | **Not met.** Mainnet chain ID confirmed as 677; no configured mainnet vault; four project wallets checked at 0 BOT | Obtain mainnet gas, deploy, have human owner configure/fund, and record actual verified mainnet actions |
| Mainnet organizer/BOT joint verification (§5.2) | No accepted mainnet evidence yet | Submit links/addresses/transactions and respond to verification requests |
| Deadline: 8 Oct 12:00 China time (§5.3) | Docs target 11:00 submission; product freeze 7 Oct 21:30 | Get the submission portal from the group and submit complete materials before noon |
| Mainnet collaboration target (§5.1.2) | 20–25 distinct projects / at least 20 is the organizers' aggregate target | It is not our individual score or a requirement to deploy 20 contracts |
| Post-event catch-up until 3 Nov (§5.1.2) | Organizer deployment-count catch-up only | It does not extend the 8 Oct competition submission deadline |

## Five scoring dimensions — each 20%

These are evidence assessments, not predicted scores or an organizer acceptance decision.

| Dimension | Countersign's evidence | Weakness to address in the demo |
|---|---|---|
| Technical completion | Verified testnet vault; real Paid/Blocked receipts; exact amounts; restart reconciliation; private team API; local-chain regression tests; public source-attributed wallet screening | Mainnet missing, full stage attack repeatability and batch/evaluation results incomplete; preview processing closed |
| Innovation | Separates AI proposals from bounded on-chain authority; adversarial comparison; visible time-lock/revocation and attributed proposal history | Explain why it is more than an AI wallet UI or a reused blacklist; show the safety boundary under an actual attack |
| Scenario value | Finance/payments teams want automation without granting an agent unrestricted treasury authority | Do not claim genuine invoice verification or zero fraud loss. Fake invoices and vendor collusion remain possible within approved destinations/budgets |
| Track fit | AI extraction/review plus real vault enforcement and cybersecurity evidence fit AI × Blockchain | BOT collaboration requires real mainnet evidence. Optional Public Good claims need their own evidence below |
| Presentation | Bilingual app, side-by-side agent comparison, receipts and documented limitations | Rehearse within round-one six minutes including Q&A; final round four-minute demo plus three-minute Q&A if selected. Keep backup evidence usable if RPC/AI fails |

## Optional Public Good track

The handbook's first problem concerns agent service reliability/acceptance and public, reusable evidence, with Ethereum identity/reputation/verification possibilities. Our BOT vault agent history is relevant supporting work, but it is not by itself an Ethereum service-acceptance integration. The second problem concerns AI-supported investigation of abnormal Ethereum activity; a third-party wallet list alone does not demonstrate that workflow either.

Do not claim this optional lane is complete. The planned separate Sepolia/receipt export (90-minute cap) and genuinely accessible reusable material would need implementation and verification, or omit that claim and focus on the main AI × Blockchain/BOT demonstration. ERC-8004 is an option rather than a mandatory feature for the core product.

## Mainnet accounts and gas application

Our existing EVM accounts can be used on BOT mainnet; balances and contract deployments are separate from testnet. No new account is required. These are public addresses only:

| Role | Address |
|---|---|
| Human mainnet owner | `0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4` |
| Deployer / requested gas receiving address | `0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023` |
| Guarded agent | `0x10840Aea6D6f835560f43656768a0d5B2A4ef063` |
| Naive demo agent | `0x8CF8109e5817fACB3235c01E93E233BF478c0659` |

All four returned 0 BOT in this review's mainnet read-only check. No mainnet transaction was sent. The gas request form shown by the user asks for a demo URL, testnet contract/transaction, one gas receiving address and applicant contact:

- Demo: https://139-180-194-19.sslip.io/#/
- Testnet vault: https://scan.bohr.life/address/0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B
- Testnet real AI payment: https://scan.bohr.life/tx/0x69ab3f76a936ba4543fdd0f7f9dec6825580500b1f6ba4d66b1917ee8372f357
- Gas recipient: deployer address above. Applicant should provide their own registered name/role and Telegram/WeChat ID.

Suggested organizer message:

> 你好，我们是 Countersign 团队，正在做 AI 付款安全项目。测试网合约已部署并验证，已有真实付款和规则拦截记录。我们准备在 BOT Chain 主网（677）部署并完成现场演示，请问主网 Gas 的申请方式、建议额度和技术联系人是什么？Gas 用于合约部署、所有者配置及两个 Agent 的少量演示交易。收款地址：0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023。另外，现场公开提交攻击发票的互动演示是否获准？如获准，应使用主网还是测试网？

The human owner signs mainnet setup in their own wallet. Its private key must never be placed in this repo or on the server. Gas sponsorship is still unconfirmed; do not claim sponsored gas. Mainnet funding does not by itself authorize unlimited AI spend or public bounty traffic.

## Remaining critical path

1. Organizer gas application → confirmed mainnet funding. Review the actual amount before choosing tiny demo payment budgets. Use native BOT if mainnet USDT is unavailable, as the existing plan specifies.
2. Deploy the tested contract to 677; verify owner/token/delay and source. Human owner sets vendors/budgets/agents and funds the demo vault. Record mainnet deployment, Paid, policy Blocked and queued/executed change receipts.
3. Configure team screens/stage demo to mainnet, retain an explicitly labelled testnet bounty unless mainnet bounty permission is confirmed. Recheck all network/explorer labels.
4. Complete a bounded real-model stage rehearsal. The clean batch, attack seed/evaluation and public AI operation require a larger authorized allowance than the current tests-only balance. Do not fabricate guard-v2 results; retain v1 unless the stated held-out rule is met.
5. Resolve the inherited frontend dependency findings; test the actual deployed app on a mainland phone and inside WeChat. Earlier server-connectivity tests are not full app acceptance.
6. Finish judge-accessible code/run instructions, source/license disclosures, team details, mainnet evidence and backup demo; submit by 8 Oct 12:00 China time.

Scam Sniffer coverage does not remove any of these gates. Its free database is delayed seven days, provides no BOT-specific incident attribution, and cannot prove an invoice genuine. See [wallet screening behavior and provenance](WALLET_SCREENING.md) and [backend launch status](BACKEND_STATUS.md).
