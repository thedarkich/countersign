# BOT mainnet rollout runbook

**Status: not executed.** No mainnet vault exists. On 7 October 2026 the owner, deployer and both agents held 0 BOT on chain 677; the organizer gas application was submitted and is awaiting funding.

**Rehearsed:** `scripts/rehearse_mainnet_fork.py native` and `… usdt` both passed on 7 October 2026 against a local Anvil fork of BOT mainnet (block ≈25,838,000). They run the real `Deploy`, `FundGas`, `Setup` and `Execute` scripts with the public owner, agent and vendor addresses, then Paid, PayoutMismatch, OverBudget, duplicate-with-changed-amount, pause → `Blocked(Paused)`, time-locked unpause and agent revocation. Anvil's public development key stands in for the deployer; nothing is broadcast to a real network and no private key is loaded. Re-run it right before the real rollout:

```bash
cd ~/countersign && source ~/.nvm/nvm.sh && python3 scripts/rehearse_mainnet_fork.py usdt
```

What the rehearsal does not cover: signing with the real keys (the owner step used an unlocked fork account in place of `--account owner`), explorer source verification, and the backend indexing a real mainnet vault.

## Decide first

| Decision | Options |
|---|---|
| Pay token (immutable per vault) | **USDT** `0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C`: checked on chain as "Tether USD", 6 decimals; the owner must obtain some (for example via BDEX) and send it to the vault. **Native BOT** `0x0000000000000000000000000000000000000000`: the vault can be funded from the gas grant with `FundGas`. |
| `INITIAL_DAILY_CAP` (base units) | 15 USDT = `15000000`; 15 BOT = `15000000000000000000`. Never reuse the testnet value with native BOT: it would be a near-zero cap and block every payment. |
| `TIMELOCK_DELAY_SECONDS` | `120`, a demo-length delay. A production deployment would use hours. |
| Budgets | `data/pos.json` caps (10, 5, 3) are token units of the chosen token. Fund the vault for the demo payments you plan, not the full budgets. |

## Gas

Measured on the fork at the live mainnet price of 20 gwei (legacy):

| Signer | Transactions | Cost |
|---|---|---|
| Deployer | deploy, `FundGas`, 8 + 1 executes | ≈0.064 BOT |
| Owner | 8 setup changes, pause, unpause request, revoke | ≈0.034 BOT |
| Each agent payment | `pay()` | ≈0.0013 BOT |

The deployer address `0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023` should receive at least 0.3 BOT. `FundGas` then forwards 0.1 BOT to the owner and 0.02 BOT to each agent (about 15 payments each), plus the vault funding for a native-BOT vault. Check the price again before starting: `cast gas-price --rpc-url https://rpc.botchain.ai`.

## Steps

Run from Ubuntu in `~/countersign/contracts` after `source ~/.nvm/nvm.sh`. Private values (`DEPLOYER_PK`, vendor payouts, agent addresses, `OWNER_ADDRESS`) load from `../.env` at runtime and are never printed. The public overrides written before each command take precedence because of `--no-override`.

**Forge can exit with status 0 after a reverted script. After every step, confirm the output has no `Error: script failed` line.**

1. **Preflight (read-only).** The chain is 677, the deployer is funded, and the rehearsal passes.

   ```bash
   cast chain-id --rpc-url https://rpc.botchain.ai
   cast balance 0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023 --ether --rpc-url https://rpc.botchain.ai
   ```

2. **Deploy (deployer key).** Substitute the chosen token and cap.

   ```bash
   NETWORK=mainnet PAY_TOKEN_MAINNET=<token> INITIAL_DAILY_CAP=<base units> TIMELOCK_DELAY_SECONDS=120 \
     ../backend/.venv/bin/python -m dotenv -f ../.env run --no-override -- \
     forge script script/Deploy.s.sol:Deploy --rpc-url https://rpc.botchain.ai --broadcast --legacy --slow
   ```

   The vault address, transaction and block are in `broadcast/Deploy.s.sol/677/run-latest.json`. Confirm `owner()` is `0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4`, and check `token()`, `delay()` and `dailyCap()` with `cast call`.

3. **Verify the source** on the explorer.

   ```bash
   forge verify-contract <vault> src/Countersign.sol:Countersign --chain 677 --verifier blockscout \
     --verifier-url https://scan.botchain.ai/api/ \
     --constructor-args $(cast abi-encode "constructor(address,address,uint64,uint256)" \
       0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4 <token> 120 <base units>)
   ```

4. **Forward gas (deployer key).** Add `VAULT_FUND_WEI=<wei>` only for a native-BOT vault. The script refuses BOT funding for a token vault, more than 0.5 BOT of gas per recipient, and more than 20 BOT of vault funding.

   ```bash
   NETWORK=mainnet CONTRACT_ADDRESS_MAINNET=<vault> GAS_OWNER_WEI=100000000000000000 GAS_AGENT_WEI=20000000000000000 \
     ../backend/.venv/bin/python -m dotenv -f ../.env run --no-override -- \
     forge script script/FundGas.s.sol:FundGas --rpc-url https://rpc.botchain.ai --broadcast --legacy --slow
   ```

5. **Owner setup (the human signs eight delayed changes).** Choose one option.

   - **A. Encrypted Foundry keystore on this laptop.** This is the path the rehearsal followed. The human imports the MetaMask key once; it is stored encrypted under `~/.foundry/keystores`.

     ```bash
     cast wallet import owner --interactive
     ```

     ```bash
     NETWORK=mainnet CONTRACT_ADDRESS_MAINNET=<vault> ../backend/.venv/bin/python -m dotenv -f ../.env run --no-override -- \
       forge script script/Setup.s.sol:Setup --rpc-url https://rpc.botchain.ai --broadcast --legacy --slow \
       --account owner --sender 0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4
     ```

   - **B. Controls page with MetaMask.** The key never leaves MetaMask, at the cost of eight confirmations. Do step 7 first so the page targets mainnet. Queue the vendors before their budgets:

     | Change | Values |
     |---|---|
     | Add vendor 1 / 2 / 3 | `0x419D0c4F429981b45548724404E5a2CeFcB303d0` / `0x68024ee76537AA843aaf06509bCc4f742554539d` / `0x4BF6056A6369e1176A0bD7cc7CAC0C859Dc31600` |
     | Add budget 1 | vendor 1, cap 10, expires 2026-10-31, refill 0 |
     | Add budget 2 | vendor 2, cap 5, expires 2026-12-31, refill 30 |
     | Add budget 3 | vendor 3, cap 3, expires 2026-12-31, refill 7 |
     | Add agent ×2 | guarded `0x10840Aea6D6f835560f43656768a0d5B2A4ef063`, naive `0x8CF8109e5817fACB3235c01E93E233BF478c0659` |

6. **Execute, at least 120 s later (permissionless; deployer gas).** Then confirm `isAgent` is true for both agents and that `poRemaining(1..3)` matches the budgets.

   ```bash
   NETWORK=mainnet CONTRACT_ADDRESS_MAINNET=<vault> ../backend/.venv/bin/python -m dotenv -f ../.env run --no-override -- \
     forge script script/Execute.s.sol:Execute --rpc-url https://rpc.botchain.ai --broadcast --legacy --slow
   ```

   **Fund the vault.** For USDT, the owner sends USDT to the vault address from MetaMask on BOT Chain mainnet. For native BOT, use step 4. Confirm `vaultBalance()`.

7. **Point the server at mainnet.** Edit the private `deploy/runtime.env` of the live release by hand, without printing it:
   - Set `NETWORK=mainnet`, `CONTRACT_ADDRESS_MAINNET=<vault>` and `INDEXER_START_BLOCK_MAINNET=<deploy block>`.
   - Keep `BOUNTY_NETWORK=testnet` and every testnet value.

   Then restart the API with that release's `IMAGE_TAG` and `COUNTERSIGN_DATA_DIR=/opt/countersign/shared/data` (`docker compose -f deploy/docker-compose.yml up -d api`). Check that:
   - `/api/config` reports chain 677 with the vault and token;
   - `/api/registry` lists 3 vendors, 3 budgets and 2 agents;
   - the ledger shows the setup changes.

8. **Payment evidence (needs a separate decision).** Steps 5 and 6 record time-lock evidence (`ChangeQueued` and `ChangeExecuted`) automatically. Mainnet `Paid` and `Blocked` receipts need agent-signed `pay()` calls. In the product that means installing the two agent keys privately on the server and setting `TRANSACTIONS_ENABLED=true`. The AI path also needs `LLM_ENABLED`, which spends TokenRouter budget. Record the vault, transactions and evidence in `docs/deployments/mainnet.json`, matching `testnet.json`.

## Trust model

- **Owner:** a single human-held EOA in MetaMask, not a multisig. This is accepted for the hackathon. The owner can queue permission expansions (each waits for the time lock) and take protective actions instantly. A stolen owner key could re-point vendor payouts after the delay, so the owner must watch the pending-changes queue. A production deployment would use a Safe multisig and a longer delay.
- **Deployer:** gas-only. `Deploy` refuses owner = deployer, and `FundGas` pays only the vault's owner, the configured agents or the vault, all within caps.
- **Agents:** hold only gas. They can pay registered vendors at registered addresses within budgets and the daily cap. A stolen agent key can still spend those budgets on real vendors with invented invoice numbers; revoking it takes effect immediately.
- **Withdrawals:** only by `queueWithdraw` (time-locked) to the owner.
- **Upgrades:** the contract cannot be upgraded. If something goes wrong: pause and revoke (instant), withdraw (time-locked), and point the server back to `NETWORK=testnet`.
- **Not established:** invoice authenticity. A fabricated invoice can still pay a registered vendor within its limits.
