# Phase 0 report

Date: 2026-10-06, China time (UTC+8).

Status: local toolchain, mock UI, public-network probes, primary TokenRouter text/image checks, durable AI/app settings and VPS SSH/Docker/HTTPS checks passed. The latest key passed Qwen Max, Qwen Flash and DeepSeek v4.1 Flash text probes; experimental DeepSeek vision returned 401 and is disabled. The human reports about $2 balance, small tests only, and the earlier phone connection check passed. Phase 0 is not fully complete: four signing credentials, mainnet funding and organizer answers remain unavailable. Independent-provider fallback is a future reliability option, and GitHub is deferred. No feature code, app/contract deployments, commits or Codex-signed transactions. The VPS serves only the connection-test page; explorer pagination remains unverified.

## Updated-document review

The workspace's `AGENTS.md`, `docs/PRODUCT.md`, `docs/SPEC.md` and initial `docs/PROGRESS.md` match the corresponding text in `C:/Users/Darkhan/Downloads/countersign-codex(1).zip`. The unsuffixed ZIP is the older pack and must not overwrite these documents.

| Original point | Assessment | Evidence / remaining qualification |
|---|---|---|
| 1. Work after the freeze | Resolved | SPEC section 1 explicitly permits Phase 5 prompt/results, isolated Phase 6 work and documentation after the freeze. The evaluation harness must therefore be ready by Phase 4. |
| 2. Guard v2 rollout | Resolved | Phase 5 and section 7 both require higher catch rate with no worse false-alarm rate; results are displayed even when v1 stays active. |
| 3. Screens and networks | Resolved | Phase 4 now distinguishes mainnet team screens from `BOUNTY_NETWORK`, with network labels in the Ledger. |
| 4. Reverts | Partially resolved | SPEC section 2.4 describes transfer/reentrancy failures and rollback. AGENTS.md hard rule 5 still says: "Only callers that aren't registered agents revert." This stale sentence is also in the newer archive. Follow the user's explicit correction and updated SPEC. |
| 5. Amount in duplicate identity | Resolved in the specification | SPEC section 3.5 step 4 hashes vendor ID and normalized invoice number only. This is a specification review, not implementation verification. |
| 6. Real-invoice security claim | Resolved | PRODUCT acknowledges invented invoice numbers and bounds a stolen agent key by registered payouts, remaining budgets and the daily cap; it also includes the fake-invoice Q&A. |
| 7. AI-fooled scoring | Resolved for the event's definition | SPEC section 3.5 step 8 defines bounty/seed invoices as unauthorized by construction. Keep this event-specific definition visible when reporting results; it is not a general measure of prompt-injection success. |
| 8. Evaluation and people counts | Substantive issues resolved; wording remains | Clean train/holdout folders are fixed. Offline evaluation disables duplicate and over-budget checks and excludes those attack techniques, reporting exclusions. SPEC calls devices an approximation for people. PRODUCT still says "split by person"; section 7's no-technique-overlap promise is only established for technique-grouped seed data, not arbitrary attacks from different devices. Report the evaluation as the documented offline guard comparison, not full production-pipeline performance. |
| 9. Human queue | Resolved | PRODUCT specifies refusal reasons in Inbox, no approve-anyway action, and resend or time-locked record correction. |
| 10. Timebox and diagram | Resolved | PRODUCT and SPEC use 90 minutes, and PRODUCT now contains the architecture diagram. |

## Environment checks

The development copy is now in Ubuntu's Linux home. The Windows original is preserved. Checks below distinguish completed setup from pending acceptance.

| Check | Observed result |
|---|---|
| Development project location | `/home/darkhan/countersign`; Windows original remains at `C:/Users/Darkhan/Documents/hackathon1/countersign` |
| WSL | Version 2.7.8.0, kernel 6.18.33.1-1, default WSL version 2 |
| Ubuntu installation/account | PASS: `Ubuntu-24.04`, WSL 2, user `darkhan`, home `/home/darkhan`; user completed initial account setup |
| Linux-home copy | PASS: repo copied to `/home/darkhan/countersign`; source comparison confirms `frontend/src` unchanged |
| Node/npm | PASS in Ubuntu: Node v20.20.2 and npm 10.8.2 through nvm v0.40.8 |
| Git | Ubuntu Git 2.43.0; repository initialized on `main`; `git rev-list --all --count` = 0 |
| Foundry | PASS: forge, cast, anvil and chisel 1.7.1 (commit `4072e48705af9d93e3c0f6e29e93b5e9a40caed8`), installed from official `@foundry-rs` npm packages. Updater 0.0.8 also installed after resuming its download and matching its SHA-256 to the official attestation. |
| Python tooling | PASS in Ubuntu: uv 0.12.23, managed Python 3.11.17 and Slither 0.11.6; each version command succeeded |
| Docker | Not found locally, as intended; installed Docker 29.8.2 and Compose v5.6.0 on the VPS, with successful `hello-world` execution |
| Project credentials | Follow-up: created Linux root `.env` from `.env.example` with mode 0600; it is Git-ignored. No secret content or keystore was inspected. User-selected TokenRouter configuration and key rotation remain pending. |
| Frontend dependencies/build | PASS: `npm install` installed 641 packages; `npm run build:mock` passed TypeScript and Vite production build. Existing dependency deprecation/PURE-annotation warnings were nonfatal. |
| Frontend preview/browser | PASS: mock Vite server on `http://127.0.0.1:5173/` returns 200 from Ubuntu and Windows. All four screens passed the checks below in Windows Chrome driven by Playwright CLI. |

### Local networking and setup changes

- Fresh WSL NAT networking resolved DNS but HTTPS connections timed out. Created the previously absent Windows `~/.wslconfig` with `networkingMode=mirrored`, `dnsTunneling=true`, and `autoProxy=true`, then restarted WSL. HTTPS connectivity passed afterward.
- npm requests still stalled until Node used `NODE_OPTIONS="--dns-result-order=ipv4first --no-network-family-autoselection"`. An npm ping and the frontend install/build then passed. Added these flags and local tool paths to the Ubuntu user's `.bashrc`, preserving existing content.
- Installed `unzip` and CJK fonts in Ubuntu. Playwright's Linux browser dependencies installed, but its large Chrome download was stopped when an existing Windows Chrome and Windows access to the Ubuntu preview were verified.
- GitHub release downloads and some PyPI packages are slow on this connection. Foundry's official npm packages and Slither through the project's documented Aliyun Python mirror succeeded. No verification bypass was used. Updater SHA-256: `6ff7da0c8ad82b138c9e37b7598e65f99878bda7522aede4617f585bda0d846f`.
- npm only changed root package-name/version/license metadata in the lockfile. Restored that incidental change from the preserved original; both lockfiles now have SHA-256 `4fddf5e12debaa0bf2dfe916fc07eacef283f8959d7660654d03aaed9990fc0a`. No frontend source changes or commits.

### Mock browser acceptance

The app ran in Ubuntu; Playwright used existing Windows Chrome through the forwarded localhost address. All outcomes below are simulated, and all entered values were fictitious. No wallet was connected and no transaction was sent. Screenshots are in `output/playwright/` in both copies.

| Check | Result / evidence |
|---|---|
| Bounty phone layout | PASS at 390 x 844; inspected `bounty-mobile.png` |
| Bounty naive attack | PASS: a message requesting a different payout address ended Blocked / Payout mismatch; mock counters updated and losses remained zero |
| Chinese language | PASS: toggled to Chinese and inspected the completed result; `bounty-result-zh.png` |
| Inbox admin gate | PASS with fictitious `phase0-mock` token; the README explicitly permits any token in mock mode |
| Both agents stage demo | PASS: hidden white-text invoice yielded guarded Refused / Hidden text in the file and naive Blocked / Payout mismatch side by side; `inbox-both-agents.png` |
| Controls | PASS: vendor registry, budgets, daily cap, agent keys, instant/time-locked labels and a ready queued change rendered; `controls.png`. Real wallet actions were not tested. |
| Ledger stage mode | PASS at `#/ledger?stage=1`: counters, latest events, QR code and mock v1/v2 results card rendered; `ledger-stage.png` |
| Browser console | Zero errors; two existing React Router v7 future-flag warnings |

The hidden radio input itself could not receive a Playwright click because its visible label intercepted it. Clicking the visible Naive agent card worked; no application change was needed. These checks establish mock UI behavior, not live backend, model or contract behavior. The local QR points at localhost and is not suitable for attendee phones.

## Public connectivity checks

Initial calls were read-only JSON-RPC/HTTP from Windows. After migration, Ubuntu's `cast` independently confirmed both chain IDs, mainnet gas price and both token decimals; Ubuntu `curl` also confirmed the explorer JSON response. The sandbox initially blocked outbound sockets; successful calls used approved execution outside the sandbox.

| Check | Result |
|---|---|
| Mainnet `eth_chainId` | PASS: `https://rpc.botchain.ai` returned `0x2a5` = 677 |
| Testnet `eth_chainId` | PASS: `https://rpc.bohr.life` returned `0x3c8` = 968 |
| Mainnet `eth_gasPrice` | PASS: `0x4a817c800` = 20,000,000,000 wei = 20 gwei at check time; use runtime values rather than the spec's approximate 50 gwei |
| Mainnet configured USDT | PASS: `decimals()` = 6; `symbol()` = `USDT` at `0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C` |
| Testnet configured tUSDT | PASS: `decimals()` = 6; on-chain `symbol()` = `USDT` at `0x75edC9335175Fc0552D51D48439F229c10420fe3` |
| Blockscout legacy logs API | PASS for reachability/JSON: `status=1`, `message=OK`, 1,000 rows for the spec's mainnet token query |
| Explorer pagination | Requests with `offset=2` still returned 1,000 rows. A fixed-range page-2 request timed out after 20 seconds, so reliable pagination and non-overlap are NOT verified. Do not treat the 1,000-row response as a complete history. |

Ubuntu's Python `urllib` request to the logs URL received HTTP 403, while the spec's `curl` request immediately succeeded with status 1 / OK / 1,000 rows. The cause of this client difference is not established. Validate the actual backend client's access in Phase 2 and retain the documented receipt/state-read fallback.

The pagination probe's output after the fixed-range timeout reused the preceding response because PowerShell continued after a nonterminating error. Its reported identical pages and overlap count are invalid and are excluded from these findings.

## Deferred checks

- Follow-up: the user resumed AI setup, authorized both TokenRouter Qwen models, then supplied a newly created Vultr server. Primary authenticated text/image probes and server SSH/Docker/HTTP checks passed (below). The detailed remaining-work plan is in PROGRESS.md.
- Follow-up setup audit: Ubuntu Codex CLI is absent from PATH after loading nvm; CLI sign-in/trust/skills/Context7 and venue access are unverified. No Git remote is configured. These are additional setup tasks beyond the already-passed language/contract tools and mock UI checks.
- Direct Model Studio calls: superseded for the primary route by the user's TokenRouter choice; not tested and not claimed.
- DeepSeek chat request / independent-provider fallback: no configured access and no successful probe yet.
- VPS SSH, Docker/Compose and laptop HTTP: passed. The human reports the requested phone connection check passed; HTTPS remains pending. No authenticated model call was made from the VPS and no application secrets were copied there.
- Organizer approval for the public bounty; BOT Chain answers on sponsorship, mainnet bounty permission and gas allocation: waiting for the human, per user.
- No sponsorship or mainnet bounty permission is assumed. Documented defaults remain `GAS_MODE=self` and `BOUNTY_NETWORK=testnet`.

## Authorized TokenRouter probes

Date: 2026-10-06. Runtime: Ubuntu Python 3.11, OpenAI-compatible SDK 3.24.0, endpoint `https://api.tokenrouter.com/v1`. The key was passed transiently through process input, never written into the probe script, project configuration, logs or report. Neither `.env` nor a keystore was read. The synthetic image was built in memory with Pillow 12.3.0; no real invoice or personal data was submitted.

Each model received one text request and one PNG image request through `chat.completions.create`, with JSON-object response format, a 256-output-token cap, 35-second timeout and no SDK retries. Both returned the correct `invoice_number`, `total` and `currency`. For the image request, field values were present only in the image, not the prompt.

| Requested model | Text JSON | Image JSON | Observed durations, text / image | Reported total tokens, text / image |
|---|---|---|---|---|
| `qwen/qwen3.8-max` | PASS | PASS | 6.69 s / 5.00 s | 297 / 420 |
| `qwen/qwen3.8-flash` | PASS | PASS | 6.23 s / 3.59 s | 254 / 491 |

The gateway returned model IDs `qwen3.8-max` and `qwen3.8-flash`; every completion ended with `stop`. These four calls are a basic connectivity/format/image-input check, not a latency benchmark, full-schema extraction test, Chinese invoice test or guard evaluation. Phase 2 must validate real fixtures and failures. Both models share TokenRouter, so an independent-provider outage fallback remains outstanding. The public model pages list Text capability; actual successful image probes provide the evidence for this tested route.

The first chat-disclosed key was not used. The later key was tested after explicit user authorization; it was not saved by the probe. Rotate exposed keys before ongoing app use, save the replacement directly in the ignored Linux `.env`, and add the `TOKENROUTER_*` fields from `.env.example`. Initial routing in that template proposes Max for text/guard reasoning and Flash for vision, subject to fixture validation. No backend implementation exists yet.

## Owner wallet setup

The human supplied a screenshot showing an unlocked MetaMask `Account 1` and then the full public owner address `0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4`. The browser security policy blocks automated inspection of `chrome-extension:` pages, so no alternate browser/native workaround was attempted; the supplied screenshot and public address are the evidence. Wallet backup and browser network configuration have not been independently verified.

Read-only Ubuntu checks on 2026-10-06:

- `cast to-check-sum-address` returned the exact supplied address; checksum comparison passed.
- Mainnet RPC chain ID = 677; native balance = 0 wei; configured USDT `balanceOf` = 0 base units.
- Testnet RPC chain ID = 968; native balance = 0 wei; configured tUSDT `balanceOf` = 0 base units.
- No wallet credentials or `.env` contents were inspected, and no transaction or signature was requested.

Record this address as the human-controlled mainnet owner. A separate throwaway testnet owner plus deployer, agent, attacker and vendor wallets remain to be prepared. Add networks manually with the [official BOT Chain settings](https://dev-docs.botchain.ai/docs/Developers/quick-guide/) and [MetaMask network instructions](https://support.metamask.io/configure/networks/how-to-add-a-custom-network-rpc/). Initial manual step: BOT Chain Testnet, RPC `https://rpc.bohr.life`, chain ID `968`, symbol `BOT`, explorer `https://scan.bohr.life`. The mainnet owner key must never be reused as `TESTNET_OWNER_PK` or sent to the server.

Wallet follow-up: the human's MetaMask add-network screenshot displayed the known chain-ID conflict for 968 (Datagram/DGRAM suggested). Rechecked BOT's official Quick Guide and ethereum-lists' `eip155-968.json`: both networks use the same ID. The entered BOT name, ID, symbol and displayed RPC/explorer hosts match the intended testnet configuration. After instructions to check the full HTTPS URLs and preserve BOT's metadata, the human confirmed the network was added successfully. Record network addition as human-reported PASS; no automated extension inspection was attempted. Next: create the separate `Countersign Test Owner` account and fund it with test tokens.

### Test owner and faucet verification

Human supplied the separate test owner `0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272` and a screenshot of a successful 10 BOT faucet claim. On 2026-10-06, read-only Ubuntu checks confirmed:

| Check | Result |
|---|---|
| Public address checksum | PASS; exact match from `cast to-check-sum-address` |
| RPC network | Chain ID 968 |
| Test BOT balance | `10000000000000000000` wei = 10 test BOT |
| Test USDT balance | Initially 0; after the human's second claim, `1000000000` base units at configured token `0x75edC9335175Fc0552D51D48439F229c10420fe3`; rechecked `decimals()` = 6, so balance = 1,000 tUSDT |
| Faucet receipt | [Transaction](https://scan.bohr.life/tx/0xe086fea146a1cc37774707460f1637c21793b43c2de6787e2d25e4834595c94d), status `0x1`, block `0x18aee46` |
| Faucet transaction | Chain ID `0x3c8`, recipient matches the test owner, value `0x8ac7230489e80000` = 10 BOT |
| Test USDT faucet receipt | [Transaction](https://scan.bohr.life/tx/0x647a7ddfd7edd072ee341288d51883cb7c09c3b70ddc5e8345c61ab2bc35fa04), status `0x1`, block `0x18aefe1`; recipient contract is the configured test USDT token |
| Test USDT transfer log | Configured token emitted Transfer to `0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272`; data = `0x3b9aca00` = 1,000,000,000 base units. Native balance still 10 test BOT. |

The human completed faucet verification and submitted both claims. Codex did not interact with CAPTCHA, read wallet secrets or sign/broadcast anything. Test owner funding is now verified complete. Next: the human creates/funds the deployer and guarded/naive agent accounts using MetaMask, then prepares attacker/vendor accounts and private runtime configuration. Faucet receipts are setup evidence, not the vault's required Paid/Blocked evidence.

### Operational wallet check

On 2026-10-06 the human supplied these public addresses. Each passed checksum validation. Live read-only RPC confirmed chain ID 968 and the following balances:

| Role | Public address | Test BOT balance | Nonce |
|---|---|---|---|
| Deployer | `0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023` | 0 | 0 |
| Guarded agent | `0x10840Aea6D6f835560f43656768a0d5B2A4ef063` | 0 | 0 |
| Naive agent | `0x8CF8109e5817fACB3235c01E93E233BF478c0659` | 0 | 0 |

All three are distinct from each other and both owner addresses. Their funding remains pending. Separate Test BOT claims failed with the user-visible error "This IP has already claimed within the last 24 hours." This establishes an additional IP cooldown that was missing from the earlier per-address instructions. Stop further faucet retries; use funds already held by the test owner.

Read-only follow-up checks returned testnet chain ID 968, owner balance 10 test BOT, gas price 20,000,000,000 wei, and estimated gas 21,000 for a 1 test BOT transfer to the deployer. That estimates a 0.00042 test BOT fee at the observed price; MetaMask's actual transaction review controls the submitted fee. The human will send 1 test BOT from `Countersign Test Owner` to each of the three operational addresses on testnet. No signing, submission or IP-limit bypass was performed by Codex. Recheck balances and available receipts after completion. No private credentials were inspected, imported or copied. Attacker/vendor accounts and private runtime configuration are still outstanding.

### Deployer funding confirmed

After the human submitted the first MetaMask transfer on 2026-10-06, read-only checks confirmed chain ID 968. [Funding transaction](https://scan.bohr.life/tx/0x4ed5449c01a31dddc342c70079b653cf8d133fc93e514ae91527ebaf86372f8c) sends 1 test BOT from `0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272` to Deployer `0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023`. Explorer status is `ok`; RPC receipt status is `0x1`, block 25884570, gas used 21,000, effective gas price 20 gwei and fee 0.00042 BOT.

Latest native balances: Test Owner 8.99958 test BOT, Deployer 1 test BOT, Guarded Agent 0, Naive Agent 0. The owner's tUSDT was not rechecked in this pass; its last verified balance is 1,000. The human signed/submitted; Codex only read public data. Next: send 1 test BOT from Test Owner to each agent, then verify the receipts/balances. No feature code, private-key access or contract deployment was involved.

### Both agent transfers confirmed

After the human reported both transfers submitted on 2026-10-06, read-only RPC and explorer checks confirmed the following on testnet 968:

| Recipient | Funding transaction | Block | Receipt status | Transfer value / latest native balance |
|---|---|---|---|---|
| Guarded Agent `0x10840Aea6D6f835560f43656768a0d5B2A4ef063` | [Transaction](https://scan.bohr.life/tx/0x6d1f4cccea112b1f3a969483ffa0657d0ab70cd2bbb0c4387a520cb8f1b873e6) | 25884976 | `0x1` | 1 test BOT / 1 test BOT |
| Naive Agent `0x8CF8109e5817fACB3235c01E93E233BF478c0659` | [Transaction](https://scan.bohr.life/tx/0x6da59ce912655ac58abb6814e07616986ac1da54ca481d06cdfc5db9559a5e57) | 25884999 | `0x1` | 1 test BOT / 1 test BOT |

Both transactions came from the recorded Test Owner, and both used 21,000 gas at 20 gwei, costing 0.00042 BOT each. Deployer balance was rechecked at 1 test BOT; Test Owner now has 6.99874 test BOT. Its last verified tUSDT balance remains 1,000 (not queried in this pass). Initial testnet gas distribution to the deployer and both agents is complete. All transfers were signed/submitted by the human; Codex inspected public data only. Next: create attacker/three vendor payout accounts, record their public addresses and finish private runtime configuration separately.

### Attacker and vendor addresses validated

On 2026-10-06 the human supplied the final four public addresses. Each exactly matched `cast to-check-sum-address`; all nine addresses in the wallet roster are distinct case-insensitively. Live RPC confirmed chain ID 968 and native balance 0 / nonce 0 for each:

| Role | Public configuration field | Address |
|---|---|---|
| Attacker | `ATTACKER_ADDRESS` | `0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b` |
| Vendor 1 | `VENDOR1_PAYOUT` | `0x419D0c4F429981b45548724404E5a2CeFcB303d0` |
| Vendor 2 | `VENDOR2_PAYOUT` | `0x68024ee76537AA843aaf06509bCc4f742554539d` |
| Vendor 3 | `VENDOR3_PAYOUT` | `0x4BF6056A6369e1176A0bD7cc7CAC0C859Dc31600` |

These are recipient addresses in the core invoice demo, so no additional gas funding is needed for them now. Optional Phase 6 vendor feedback signing is separate. Public address collection and initial testnet gas distribution are complete; private runtime configuration and mainnet funding remain pending. The human must privately map Deployer to `DEPLOYER_PK`, Guarded Agent to `AGENT_GUARDED_PK`, Naive Agent to `AGENT_NAIVE_PK`, and Test Owner to `TESTNET_OWNER_PK`. The mainnet owner key never enters `.env` or the server. Codex did not read/export any wallet key or open `.env`.

## Authorized VPS setup

Date: 2026-10-06. Server: `139.180.194.19`, Tokyo as reported by the human. Initial password login succeeded after reconnecting an expired session. The password was supplied only at SSH's password prompt and was not written into project files or server setup scripts. The first SSH host key was accepted on first connection; later connections enforce that stored key. Its fingerprint has not been independently compared with the Vultr console.

| Check | Observed result |
|---|---|
| OS/resources | Ubuntu 22.04.5 LTS, 2 vCPU, 3,906 MiB RAM, 7,899 MiB swap, 75 GB root filesystem with 60 GB available before Docker installation |
| Initial services | SSH on TCP 22, local DNS stub only; no Docker, no app under `/srv`, UFW active allowing SSH |
| SSH key | Dedicated Ed25519 key created locally in Ubuntu at `/home/darkhan/.ssh/countersign_vultr`; public key appended with `ssh-copy-id`, preserving existing keys. Private key is outside the repo and was never displayed. Public fingerprint: `SHA256:5UQIN5siOoxelXfgK4lKMFd+hqUzZEqjye5IQ06qbM8` |
| Root SSH restriction | Added `/etc/ssh/sshd_config.d/00-countersign-phase0.conf` with `PermitRootLogin prohibit-password` after successful key login. `sshd -t` passed, service reloaded, effective setting reports `without-password`, and a fresh batch-mode key login succeeded. Codex did not change the root password; the human subsequently confirmed a final private rotation. |
| Docker | Official Docker Ubuntu apt repository; Docker 29.8.2, Compose v5.6.0, Buildx 0.37.1 and containerd.io 2.3.6. Docker active and enabled at boot; `docker run --rm hello-world` passed |
| Host firewall | Preserved active UFW and SSH access; added TCP 80/443 for IPv4 and IPv6. SSH currently allowed from any source. Vultr cloud-firewall rules were not inspected. |
| Connection page | Official `caddy:2-alpine` image, observed Caddy v2.11.7, container `countersign-connectivity`, restart unless stopped, only host port 80 published to container port 8080. Read-only bind mount of `/srv/countersign-connectivity`; contains only the generic Phase 0 connection page |
| Laptop HTTP | PASS: Ubuntu `curl -i http://139.180.194.19/` returned HTTP 200, `Server: Caddy`, and the expected page text |
| VPS outbound RPC | PASS: mainnet `eth_chainId` = `0x2a5` (677), testnet = `0x3c8` (968) |
| VPS outbound explorer | PASS for reachability: logs API returned `status=1`, `message=OK`, 1,000 rows. This does not resolve pagination completeness. |
| VPS outbound TokenRouter | Unauthenticated `/v1/models` returned HTTP 401; establishes reachability only. The four authenticated model checks above ran locally in Ubuntu. |
| Phone and HTTPS | After initially deferring the mobile-data/WeChat request, the human replied "check passed. just opened". Record human-reported PASS for the Phase 0 connection page. Port 443 is allowed but no TLS listener/certificate has been configured. Retest the final app/URL before launch; no bounty has launched. |

Caddy image digest observed: `sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f`.

From the **local Ubuntu terminal**, connect using the dedicated key:

```bash
ssh -i ~/.ssh/countersign_vultr -o IdentitiesOnly=yes root@139.180.194.19
```

From **Windows PowerShell** (including `PS C:\WINDOWS\System32>`), invoke Ubuntu's SSH explicitly:

```powershell
wsl -d Ubuntu-24.04 -u darkhan --exec ssh -i /home/darkhan/.ssh/countersign_vultr -o IdentitiesOnly=yes root@139.180.194.19
```

Verified from PowerShell with an additional `BatchMode=yes` and remote `id -un`: exit 0, output `root`. Plain Windows `ssh root@139.180.194.19` does not automatically use this Ubuntu-local key. The human encountered `Permission denied (publickey,password)` after trying password login from PowerShell; root password SSH was deliberately disabled during setup. No password reset or authentication rollback was needed.

The human has confirmed completing the final private password rotation with `passwd`. Record this as human-reported completion; no replacement password was requested, read or recorded. For future rotations, run `passwd` inside the server session and keep the value out of chat. Key-based SSH continues to work independently of that password; keep the local private SSH key private. No mainnet owner key belongs on this server.

Before the Phase 3 app deployment, stop/remove the temporary TLS container to free ports 80/443. The earlier HTTP-only container is retained stopped for rollback; remove it when the real deployment is verified:

```bash
docker stop countersign-connectivity-tls
docker rm countersign-connectivity-tls
docker rm countersign-connectivity
```

These commands refer only to containers created for this check. Keep backend ports private in the eventual Compose configuration because Docker-published ports can bypass UFW. Reuse the external Docker volumes `countersign_caddy_data` and `countersign_caddy_config` for the real Caddy deployment so the issued certificate and renewal state survive; do not delete these volumes. Update the route to the backend and verify the real app then.

### HTTPS setup completed on 2026-10-06

At the human's request to handle setup directly, configured `/etc/countersign-connectivity/Caddyfile` on the VPS and validated it with the existing official `caddy:2-alpine` image. The new `countersign-connectivity-tls` container publishes TCP 80 and 443 and uses persistent named volumes. The original `countersign-connectivity` container is stopped and preserved for rollback. No backend or feature application is deployed.

Laptop/Ubuntu verification passed:

| Check | Result |
|---|---|
| DNS | `139-180-194-19.sslip.io` resolves to `139.180.194.19` |
| Raw IP | `http://139.180.194.19/` returns HTTP 200 and the expected connection-test page |
| Hostname HTTP | Redirects to `https://139-180-194-19.sslip.io/`, final HTTP 200 |
| Hostname HTTPS | HTTP 200 and expected "Countersign server is reachable" content |
| TLS validation | Normal system trust verification passed; TLS 1.3; certificate SAN matches the hostname; expiry 2027-01-04 07:54:39 UTC |

No TLS verification was disabled and no browser security warning was bypassed. Phone/WeChat acceptance for this HTTPS hostname and the eventual real application still needs a device test. Configuration follows [Caddy's automatic HTTPS documentation](https://caddyserver.com/docs/automatic-https).

Setup references: [Docker Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/), [Ubuntu firewall](https://ubuntu.com/server/docs/how-to/security/firewalls/), [OpenSSH root-login settings](https://man.openbsd.org/sshd_config#PermitRootLogin), and [Caddy static file server](https://caddyserver.com/docs/quick-starts/static-files). Live command responses above are the evidence for this server's configuration.

## Local tools and documentation handoff follow-up

On 2026-10-06, continued Phase 0 while private credential entry remained with the human:

| Check | Result |
|---|---|
| Ubuntu Codex CLI | Installed from official npm registry with `npm install -g @openai/codex@0.160.1`; `codex --version` returned `codex-cli 0.160.1` |
| Ubuntu Context7 | Installed `@upstash/context7-mcp@4.1.1`; `context7-mcp --version` returned `4.1.1`; Node 20.20.2 meets the package's declared minimum 20.18.1 |
| Codex authentication | `codex login status` exit 1; not signed in. Output was reduced to status only; no credential file was opened |
| MCP client configuration visibility | `codex mcp list --json` returned an empty list in the checked CLI context. The repository still declares Context7; activation inside a trusted/signed-in project session is not yet verified |
| Standalone MCP handshake | PASS: installed Context7 stdio server negotiated protocol `2025-11-25`, identified itself as Context7 4.1.1 and exposed `resolve-library-id` and `query-docs` |
| Documentation search | PASS: resolved FastAPI to `/websites/fastapi_tiangolo` using a generic public query |
| Documentation retrieval | PASS: `query-docs` returned UploadFile documentation with official sources `https://fastapi.tiangolo.com/reference/uploadfile` and `https://fastapi.tiangolo.com/tutorial/request-files` |
| Project skills | 16 SKILL.md files present; discovery within a signed-in CLI session remains a separate check |
| Secret protection metadata | `git check-ignore .env` returned `.env`; existing local file previously verified mode 0600. Contents never opened or summarized |
| Frontend baseline | FRONTEND_BASELINE.json captures 40 explicitly selected source/public/config files; all matched the supplied ZIP at capture time, before subsequent frontend instruction-document edits. No production frontend source changed |
| Human setup guide | PRIVATE_SETUP.md provides public values, exact automation-key/account mapping, MetaMask's official export reference and local save instructions; it contains no secret values |
| GitHub | Creation/remote explicitly deferred by human; no remote added, no push or feature commit |

The initial npm metadata probe stalled without the verified Node network options; a bounded replacement using `NODE_OPTIONS='--dns-result-order=ipv4first --no-network-family-autoselection'` succeeded. The stale metadata process was stopped. Installation then completed successfully (109 packages, about four minutes). No API or wallet credentials were used by these tool checks. MCP probe subprocesses were terminated after their read-only checks.

Aligned AGENTS.md, frontend/AGENTS.md and SPEC with the human-approved later SpendMate redesign and TokenRouter selection. Corrected the non-policy revert exception and public-device versus seed-technique holdout wording. These are documentation/configuration-template changes only. The four screens remain on mocks, and no contract/backend/application deployment was created.

References: [official Codex CLI setup](https://learn.chatgpt.com/docs/codex/cli), [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp), [Context7 project](https://github.com/upstash/context7), [MCP stdio transport](https://ts.sdk.modelcontextprotocol.io/v2/serving/stdio), [MetaMask individual private-key export](https://support.metamask.io/configure/accounts/how-to-export-an-accounts-private-key/).

## Automatic local configuration completed on 2026-10-06

The human explicitly asked Codex to finish setup directly. Used a one-off helper outside the project (`phase0-downloads/finish_local_setup.py`) to load configuration at runtime, write the already-approved public values, populate the supplied TokenRouter credential only if the local credential was absent, and privately generate missing `ADMIN_TOKEN` and `IP_HASH_SALT` values. The helper does not print configuration, secrets, provider response bodies or tracebacks; it does not create wallets, sign transactions or modify feature code. Existing wallet credentials were not replaced.

| Runtime check | Result |
|---|---|
| Public network/address/model/domain settings | PASS |
| Application credentials | PASS; missing values generated with `secrets.token_urlsafe(48)`, runtime length checks passed |
| TokenRouter Qwen Max | PASS: authenticated text request through local runtime configuration; returned expected fixed response; 91 reported tokens |
| TokenRouter Qwen Flash | PASS: same bounded check; 91 reported tokens |
| Four automation-wallet identities | Not verified: all four signing credentials unavailable at runtime; no invalid or mismatched key was processed |
| Independent DeepSeek fallback | Cannot authenticate without credential; still pending |
| Secret file metadata | Mode 0600, owner darkhan, Git-ignored |
| Feature-source baseline | All 38 non-document frontend source/config files still match the captured baseline; contract/backend/data/deploy directories still absent |

The first uv dependency job stalled while downloading the larger SDK/crypto dependency set. Stopped only that identified installer and completed the helper using cached `python-dotenv 1.2.4` plus Python's standard HTTP client. The earlier four SDK text/image probes remain the SDK acceptance evidence; these two new text calls verify durable local authentication. No wallet key was available, so no crypto dependency was required for address derivation. No raw `.env` or keystore contents were inspected by Codex.

TokenRouter's inspected browser session is signed out; no account-level key rotation was performed. The configured key was already supplied in chat, so working authentication is not evidence of rotation. The browser tool previously rejected MetaMask extension-page access; no workaround or secret export was attempted. Public wallet addresses alone cannot provide signing access.

## Replacement key and budgeted four-model check on 2026-10-06

The human supplied a replacement TokenRouter key, authorized four exact model IDs, and limited use to small tests from a reported $2 account balance. Replaced the previous local TokenRouter credential without printing it, selected Qwen Flash for routine text/vision work, kept Max available for selective comparisons, and added DeepSeek v4.1 Flash as a same-gateway text alternative. A separate direct DeepSeek key is not needed for these tests and remains unconfigured.

One-off helper `phase0-downloads/budgeted_model_setup.py` sent exactly four completion requests with `max_tokens=32`, a 20-second request timeout and no retries. Its result marker prevents an accidental repeat. The first three requests asked for a fixed short text response. The fourth sent only a synthetic 64×64 blue PNG and asked for its dominant color; no private invoice or wallet data was sent.

| Requested model | Probe result | Prompt / completion tokens | Estimated USD |
|---|---|---|---|
| `qwen/qwen3.8-max` | PASS, expected short response | 66 / 25 | 0.000282 |
| `qwen/qwen3.8-flash` | PASS, expected short response | 66 / 25 | 0.0000176957 |
| `deepseek/deepseek-v4.1-flash` | PASS, expected short response | 35 / 24 | 0.00002358 |
| `deepseek/deepseek-v4-flash-vision-exp` | HTTP 401, no image capability verified | usage unavailable | unknown |

The three successful calls total **241 reported tokens** and **$0.0003232757 estimated cost**. This uses published input/output prices per million tokens: [Qwen Max](https://www.tokenrouter.com/models/qwen/qwen3.8-max/) $2/$6, [Qwen Flash](https://www.tokenrouter.com/models/qwen/qwen3.8-flash/) $0.1177/$0.3971, and [DeepSeek Flash](https://www.tokenrouter.com/models/deepseek/deepseek-v4.1-flash/) $0.18/$0.72. These are estimates from usage and list prices, not a billing receipt or balance check; the failed call supplied no usage, so no zero-cost claim is made for it.

After the 401, performed only one authenticated `GET /v1/models` metadata check, with zero further completions. All four requested IDs were listed. Listing does not establish execution permission, and the exact cause of the route-specific 401 remains unverified. The [experimental route's public page](https://www.tokenrouter.com/models/deepseek/deepseek-v4-flash-vision-exp/) lists Text capability, so its name alone does not prove image support. Cleared `TOKENROUTER_FALLBACK_VISION_MODEL` to keep it inactive; retain Qwen Flash as the image candidate supported by earlier probes. No automatic paid retries, batch evaluation or public live AI traffic under the current tests-only authorization.

Saved `LLM_HOURLY_CALL_CAP=20` for eventual backend enforcement. This is a call-count setting, not a dollar cap, and no backend currently exists to enforce it. Existing private app credentials and wallet configuration were preserved. Raw probe results contain no secrets and are saved outside the repo in `phase0-downloads/model-access-result-2026-10-06.json`.

## Next

1. Continue from the Linux development copy: `cd ~/countersign` in Ubuntu. The mock server is currently running at `http://127.0.0.1:5173/`; to restart it later, run `cd ~/countersign/frontend && npm run dev -- --mode mock --host 127.0.0.1`.
2. Root password rotation is complete per the human. Public settings, local TokenRouter replacement-key access, app credentials and HTTPS are verified. TokenRouter old-key revocation is unverified; do not repeat the budgeted model checks. Experimental DeepSeek vision stays disabled after 401.
3. Public wallet addresses and initial testnet funding are complete. Only the four private wallet exports remain in PRIVATE_SETUP.md's immediate wallet handoff. Mainnet funding and organizer answers remain pending; independent AI fallback is an optional reliability improvement. CLI sign-in/project activation is optional for working in that CLI; the desktop can continue through WSL. GitHub is explicitly deferred. Follow PROGRESS.md's phase sequence and the tests-only AI budget. Stay within Phase 0; no feature code or commits before the permitted window.

Installation references checked: [Microsoft WSL commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands), [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install), [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking), [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [Foundry installation](https://getfoundry.sh/getting-started/installation), [official Forge npm package](https://www.npmjs.com/package/@foundry-rs/forge), and [Playwright browsers](https://playwright.dev/docs/browsers). Local command output is the evidence for installed versions and acceptance results.
