# Setup: read this first (for you, not for Codex)

This pack has everything Codex needs to build Countersign without asking you questions.

| File | Who reads it | What it is |
|---|---|---|
| `AGENTS.md` | Codex (loaded automatically) | Rules, stack, commands, which skill to use when, decision defaults |
| `frontend/AGENTS.md` | Codex, when it works in `frontend/` | The UI is finished: wire it up, don't restyle it |
| `docs/PRODUCT.md` | Codex and the team | Why we're building it, the demo script, judge Q&A |
| `docs/SPEC.md` | Codex | The exact build spec, phase by phase |
| `docs/PROGRESS.md` | Codex keeps it updated | Status log, addresses, evidence transactions |
| `.agents/skills/` | Codex | 16 skills: 3 written for this project, 13 copied from BOT Chain, Trail of Bits and OpenAI. See `THIRD_PARTY.md` there |
| `.codex/config.toml` | Codex | Sandbox, network access and the Context7 docs server for this repo |
| `frontend/` | Codex and the team | The finished UI on a mock API (`npm run dev -- --mode mock`) |
| `.env.example` | you | Every setting; copy it to `.env` and fill it in |
| `SETUP.md` | you | This file |

## 1. Before 20:00 today (no feature code yet)

### Laptop (Windows)

1. In PowerShell as admin, run `wsl --install -d Ubuntu-24.04`, then reboot. Do all work inside Ubuntu, including Codex.
2. Inside Ubuntu:

   ```bash
   # Node 20
   curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   source ~/.bashrc && nvm install 20
   # uv (Python)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Foundry
   curl -L https://foundry.paradigm.xyz | bash && source ~/.bashrc && foundryup
   # PDF fonts for Chinese invoices
   sudo apt update && sudo apt install -y fonts-noto-cjk
   # Slither, for the contract security review skill
   uv tool install slither-analyzer
   ```

3. If downloads are slow:
   - `npm config set registry https://registry.npmmirror.com`
   - `export UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/`

You don't need Docker on the laptop. It runs on the server only.

### Codex

```bash
npm install -g @openai/codex
codex            # sign in with your ChatGPT account (or an API key) when it asks
```

- Codex has to reach OpenAI. Mainland networks usually block it, so test it **on the venue Wi-Fi** as soon as you arrive, not at 20:00. Have a plan B (a hotspot, or a teammate who can connect).
- The first time you run `codex` inside the repo it asks whether to trust the folder. Say yes, otherwise it ignores `.codex/config.toml`.
- Inside Codex, check:
  - `/skills` lists the 16 skills from `.agents/skills/`.
  - `/mcp` shows `context7`.
- Pick the strongest coding model your plan offers, with high reasoning effort, for the contract and the pipeline (`/model` inside Codex).

### Accounts

- **Alibaba Cloud Model Studio:** activate it, create an API key, and check that a Qwen-VL model and a Qwen text model are enabled.
- **DeepSeek platform:** create an API key and top up a small amount.
- **VPS** (your Vultr server in Tokyo, Ubuntu 22.04, 2 vCPU):
  - open ports 80 and 443 in its firewall
  - install Docker
  - open `http://<IP>` from a mainland phone on mobile data, and also through a QR code inside WeChat. If it doesn't load, ask Vultr for a new IP before you spend time on anything else

### Wallets

Create these with `cast wallet new` and save the keys somewhere offline:
- deployer
- agent-guarded
- agent-naive
- attacker (for the poisoned invoices)
- three vendor payout wallets

For the **owner**, use the finance lead's MetaMask account. Also import it into an encrypted Foundry keystore on that laptop: `cast wallet import owner --interactive`. It never goes into `.env`.

Codex has no setting that blocks it from reading `.env`. `AGENTS.md` tells it never to open the file, and the only keys in it are gas wallets and API keys. Keep it that way: the owner key never touches the repo.

**Testnet funds:** claim tBOT and tUSDT at https://faucet.botchain.ai/basic. It needs a captcha. Claim for the deployer, both agents, and a throwaway testnet owner.

**Mainnet funds** (ask BOT Chain staff, or swap on BDEX):

| Wallet | Amount |
|---|---|
| Deployer | ~1 BOT |
| Owner | ~1 BOT |
| Each agent | ~3 BOT for gas (0 if BOT Chain sponsors their gas) |
| Vault | a few USDT for the demo and the clean batch |

## 2. Create the repo

```bash
# unzip the pack; the countersign/ folder is the repo
cd countersign
git init
cp .env.example .env    # fill it in; never commit it
cd frontend && npm install && npm run dev -- --mode mock   # check the UI opens, then Ctrl+C
```

Don't commit code before 20:00. Committing `AGENTS.md`, `docs/`, `.agents/`, `.codex/` and `SETUP.md` is fine.

## 3. What to paste into Codex

Start a **fresh Codex session for each phase**. `AGENTS.md` and `docs/PROGRESS.md` carry the state between sessions, so nothing is lost, and Codex works better with a clean context.

**Now (Phase 0, before 20:00):**

```
Read AGENTS.md, docs/PRODUCT.md, docs/SPEC.md and frontend/README.md fully. It's before 20:00, so do Phase 0 only:
check the toolchain, run every connectivity check in SPEC §1 Phase 0, and write docs/PHASE0_REPORT.md.
Do not write feature code. Tell me anything I must fix before 20:00.
```

**At 20:00 (Phase 1, the contract):**

```
It's 20:00, the hackathon has started. Do Phase 1 from docs/SPEC.md: the contract and its tests per §2,
then deploy to testnet with $countersign-chain-ops. Review it with $secure-workflow-guide before mainnet.
Run the acceptance checks, update docs/PROGRESS.md, commit small and often.
Only ask me about the items under "Ask the human only about" in AGENTS.md.
```

**Each later phase** (new session each time):

```
Read AGENTS.md and docs/PROGRESS.md, then do Phase <N> from docs/SPEC.md.
Run its acceptance checks, update docs/PROGRESS.md, commit small and often.
```

**If teammates run Codex in parallel** (each in their own clone, pushing to the same GitHub repo):

```
You own only contracts/. Follow docs/SPEC.md §2 and use $countersign-chain-ops. Commit and push when tests pass.
```

```
You own only backend/. Follow docs/SPEC.md §3–§5. Match frontend/src/api/types.ts exactly; use $countersign-api-match.
Until the ABI exists in contracts/out, use the interface in SPEC §2.
```

```
You own only frontend/. It's already built; read frontend/AGENTS.md. Switch screens from mock to live as backend
endpoints appear, fix mismatches, and add the Playwright tests in SPEC §10 using $playwright.
```

**Before the bounty launch, every rehearsal, the 21:30 freeze, and judging:**

```
Run $countersign-demo-check and give me the table. Don't fix anything yet.
```

**Oct 8, 07:00:**

```
Run Phase 5 (learning loop) from docs/SPEC.md §7 exactly. Don't tune on the held-out set. Then show me the results.
```

## 4. Things only you can do

- At check-in, ask the organizers: is the public bounty allowed, and can it be posted in the participant group?
- Ask BOT Chain's tech contact (the handbook says each team gets one) these three, and paste the answers into `docs/PROGRESS.md`:
  1. Can our two agent keys get gas sponsored on mainnet through your paymaster (or NodeReal MegaFuel), with a policy that only sponsors calls to our vault contract? Which endpoint do we use?
  2. May our public bounty send real mainnet transactions? The vault only ever pays our own vendor addresses, and the prizes aren't crypto.
  3. How much mainnet gas can we get, and how do we claim it?
- Decide what the two prizes actually are (not crypto).
- Claim the testnet faucet (captcha).
- Paste keys into `.env` on your laptop and on the VPS.
- Run anything that signs with the mainnet owner key yourself: Setup on mainnet (`--account owner`) and owner actions in Controls with MetaMask. Codex gives you the exact command.
- Test the bounty QR code inside WeChat on a real phone.
- Record the backup demo video on the evening of Oct 7.
- Rehearse the 3-minute demo and the first three Q&A answers in `docs/PRODUCT.md`.

## 5. Optional extras

Everything needed is already in `.agents/skills/`. If you want more:
- OpenAI's curated skills: type `$skill-installer <name>` inside Codex (for example `$skill-installer security-threat-model`).
- The full Trail of Bits collection: `codex plugin marketplace add trailofbits/skills`, then `codex plugin list`.
