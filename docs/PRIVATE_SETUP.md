> Completed on 2026-10-06: the human ran the hidden-input helper and it verified all four wallet identities. The deployer and testnet owner subsequently signed the live testnet deployment/setup/funding; both agent keys signed the contract proof. Do not repeat key export. The instructions below are retained for recovery only. Mainnet owner signing remains in the human wallet.

# Private signing-key helper

The wallet extension blocks browser automation. Codex can save and validate exports, but cannot read them from MetaMask. In your own Ubuntu terminal, run:

```bash
cd ~/countersign
backend/.venv/bin/python scripts/configure_wallets.py
```

Paste each named account’s exported private key into its hidden prompt. The helper checks all four public addresses before atomically updating the ignored .env with mode 600. The installed backend environment already provides its dependencies. The helper makes no network requests. Do not use chat for this. Do not export the mainnet owner. Cancel with Ctrl+C to save nothing.

# Remaining private wallet setup

On 2026-10-06 the human authorized Codex to finish setup directly. Codex saved the public settings, populated the authorized TokenRouter credential when no local credential was available, generated missing app credentials privately, and verified both selected Qwen models. Local configuration remains mode 0600 and Git-ignored; its contents were not displayed. HTTPS also passed at `https://139-180-194-19.sslip.io/`.

The runtime check could not derive any of the four automation-wallet identities because their signing credentials were unavailable. Public addresses do not provide signing access. Browser automation of MetaMask extension pages was previously blocked by the browser tool, so those keys could not be exported automatically. This guide now records only the remaining handoff and the public reference values; do not repeat completed configuration.

Enter the four individual wallet keys privately in `/home/darkhan/countersign/.env` inside Ubuntu. Do not paste that file, private keys, API keys or recovery phrases into chat or screenshots. The file already exists; do not overwrite it by copying the template again.

## 1. Open the local editor

Run in **Windows PowerShell on your laptop**, not in the VPS shell:

```powershell
wsl -d Ubuntu-24.04 -u darkhan --exec nano /home/darkhan/countersign/.env
```

Edit existing matching lines. Add a missing field once; avoid duplicate definitions.

## 2. Public settings already completed (reference only)

These settings were saved and validated by the setup helper; no manual entry is required:

```dotenv
NETWORK=testnet
BOUNTY_NETWORK=testnet
GAS_MODE=self
OWNER_ADDRESS=0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4
AGENT_GUARDED_ADDRESS=0x10840Aea6D6f835560f43656768a0d5B2A4ef063
AGENT_NAIVE_ADDRESS=0x8CF8109e5817fACB3235c01E93E233BF478c0659
ATTACKER_ADDRESS=0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b
VENDOR1_PAYOUT=0x419D0c4F429981b45548724404E5a2CeFcB303d0
VENDOR2_PAYOUT=0x68024ee76537AA843aaf06509bCc4f742554539d
VENDOR3_PAYOUT=0x4BF6056A6369e1176A0bD7cc7CAC0C859Dc31600
TOKENROUTER_BASE_URL=https://api.tokenrouter.com/v1
TOKENROUTER_TEXT_MODEL=qwen/qwen3.8-flash
TOKENROUTER_FAST_MODEL=qwen/qwen3.8-flash
TOKENROUTER_VISION_MODEL=qwen/qwen3.8-flash
TOKENROUTER_STRONG_MODEL=qwen/qwen3.8-max
TOKENROUTER_FALLBACK_TEXT_MODEL=deepseek/deepseek-v4.1-flash
TOKENROUTER_FALLBACK_VISION_MODEL=
LLM_HOURLY_CALL_CAP=20
DOMAIN=139-180-194-19.sslip.io
PUBLIC_BASE_URL=https://139-180-194-19.sslip.io
```

`OWNER_ADDRESS` above is the finance lead's mainnet public address. The testnet deployment uses the separate owner derived from `TESTNET_OWNER_PK`, as required by SPEC. Keep the RPC/token settings already supplied by `.env.example`. Contract-address fields remain blank until deployment.

## 3. Fill only these four automation-wallet keys

Use the individual Ethereum account private key, never the wallet recovery phrase or MetaMask password. Match the account's public address before copying its key.

| Existing field in `.env` | MetaMask account | Expected public address |
|---|---|---|
| `DEPLOYER_PK` | Countersign Deployer | `0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023` |
| `AGENT_GUARDED_PK` | Countersign Guarded Agent | `0x10840Aea6D6f835560f43656768a0d5B2A4ef063` |
| `AGENT_NAIVE_PK` | Countersign Naive Agent | `0x8CF8109e5817fACB3235c01E93E233BF478c0659` |
| `TESTNET_OWNER_PK` | Countersign Test Owner | `0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272` |

In MetaMask Extension, open the account selector, use the account's three-dot menu, then **Account details → Private key**. Authenticate privately and use the hold-to-reveal control. Copy into the matching field in your local editor, after `=`. Use the Ethereum key with a `0x` prefix. Close the key display afterwards. [Official MetaMask instructions](https://support.metamask.io/configure/accounts/how-to-export-an-accounts-private-key/).

The mainnet owner (`Account 1`, ending `e0c4`) stays in MetaMask or an encrypted local keystore. Its private key must not enter this file or the VPS. The attacker and vendor private keys are not needed for the core invoice demo; leave optional `VENDOR1_PK`–`VENDOR3_PK` blank for now.

## 4. AI access is working; credential rotation and fallback remain

The latest user-supplied replacement TokenRouter key is saved locally. Tiny text probes passed for Qwen Max, Qwen Flash and DeepSeek v4.1 Flash. The requested experimental DeepSeek vision route returned HTTP 401 and is disabled; one authenticated model-list check confirmed its ID is listed, but did not establish execution access. No paid retry was made. The user reports about $2 in the account and authorizes small tests only. Qwen Flash is now the routine choice and Max is reserved for selective comparisons. The backend now enforces a process-local hourly cap of 20; this is not a provider-side dollar spending cap. Paid requests default to disabled. No account-level revocation of older keys was performed. Exact evidence and estimated cost are recorded in PHASE0_REPORT.md.

DeepSeek v4.1 Flash is already available through the same TokenRouter key; another account is not required for the authorized tests. A direct DeepSeek account would be an optional independent gateway-outage fallback. Leave its separate `DEEPSEEK_API_KEY` empty until separately provided; do not copy the TokenRouter key into direct-provider fields.

Application-specific `ADMIN_TOKEN` and `IP_HASH_SALT` have been generated privately where missing and passed the runtime length check. They are not wallet keys. HTTPS/domain connectivity is verified; routing to the real application and a final phone test follow deployment.

## 5. Save and report readiness

In nano, press **Ctrl+O**, **Enter**, then **Ctrl+X**. Reply only "four wallet keys saved" when complete. Do not attach the file or show its values. Codex can then validate the four public identities without displaying keys.

Future runtime verification may derive and compare public addresses and run bounded API probes, without displaying secret values. Codex must never open, print, grep or summarize `.env` or keystore contents. No deployment or payment is authorized merely by saving configuration.

## Deferred or external items

- Ubuntu Codex CLI is installed. If you want to use it directly, open Ubuntu, run `cd ~/countersign` then `codex`, and complete your own sign-in and project-trust prompts. After that, check `/mcp` and `/skills` in that session. A standalone Context7 server probe already passed both library search and documentation retrieval; this desktop chat does not expose it as a native tool. [Official CLI setup](https://learn.chatgpt.com/docs/codex/cli) and [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).
- GitHub creation and remote setup are deferred at the human's request; local work continues.
- Mainnet BOT funding and organizer answers on public bounty permission, mainnet bounty permission, gas allocation and sponsorship remain pending.
- The SpendMate-based frontend redesign is approved for after current setup; this guide does not change product code.
