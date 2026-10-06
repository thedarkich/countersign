# Skills in this folder

Codex loads every folder here that has a `SKILL.md` (repo-level skills live in `.agents/skills`). Type `/skills` in Codex to see them, or mention one with `$name`.

## Written for this project

| Skill | Use it for |
|---|---|
| `countersign-chain-ops` | Deploying, verifying, setting up and checking the vault on BOT Chain testnet and mainnet |
| `countersign-api-match` | Keeping backend responses identical to `frontend/src/api/types.ts` |
| `countersign-demo-check` | The readiness checklist before the bounty launch, rehearsals, the freeze and judging |

## Copied from other projects

Each folder keeps its upstream licence file. Only one change was made: in `playwright/SKILL.md` the script path points at this repo instead of `~/.codex/skills`.

| Skill | Source | Licence | Use it for |
|---|---|---|---|
| `botchain-network`, `botchain-rpc`, `botchain-deploy`, `botchain-paymaster`, `botchain-bridge`, `botchain-dex`, `botchain-ecosystem` | [the3rdweblabs/botchain-skills](https://github.com/the3rdweblabs/botchain-skills) | MIT | Chain IDs, RPC quirks, deploy and verify, gas sponsorship, bridging USDT, buying BOT for gas |
| `secure-workflow-guide`, `token-integration-analyzer` | [trailofbits/skills](https://github.com/trailofbits/skills) (building-secure-contracts) | CC BY-SA 4.0 | Security review of `Countersign.sol` before mainnet; checking the USDT integration |
| `property-based-testing` | [trailofbits/skills](https://github.com/trailofbits/skills) | CC BY-SA 4.0 | Foundry fuzz and invariant tests, Hypothesis tests in the backend |
| `modern-python` | [trailofbits/skills](https://github.com/trailofbits/skills) | CC BY-SA 4.0 | uv, ruff and project layout for the backend |
| `playwright` | [openai/skills](https://github.com/openai/skills) (curated) | Apache 2.0 | Driving a real browser to test the four screens |
| `security-best-practices` | [openai/skills](https://github.com/openai/skills) (curated) | Apache 2.0 | Security review of the FastAPI backend (uploads, auth, rate limits) |

Skipped on purpose: BOT Chain's node and staking skills (validator operations, not our problem) and any UI design skill (the frontend is finished; don't restyle it).
