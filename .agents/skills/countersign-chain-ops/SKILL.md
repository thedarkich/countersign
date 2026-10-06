---
name: countersign-chain-ops
description: Use when deploying, verifying, setting up, funding or checking the Countersign vault contract on BOT Chain testnet (968) or mainnet (677), queueing or executing time-locked changes from Foundry scripts, or recording contract addresses and evidence transactions. Not for writing or reviewing the Solidity itself.
---

# Countersign chain operations

The contract is specified in `docs/SPEC.md` §2. This skill is the order of operations and the traps. Network facts are in the `botchain-network`, `botchain-rpc` and `botchain-deploy` skills.

## Rules that never bend

- **Legacy transactions only.** Every `forge script --broadcast` and `cast send` gets `--legacy`. Never set `maxFeePerGas` or `maxPriorityFeePerGas`.
- **No `eth_getLogs` on the mainnet RPC.** Don't use `cast logs` against `https://rpc.botchain.ai`. Read receipts (`cast receipt <hash>`) or the Blockscout API (`https://scan.botchain.ai/api?module=logs&action=getLogs&...`).
- **Keys.** Deployer and agent keys come from `.env` through environment variables. Never print them, never put them on a command line that ends up in a log, never open `.env` to read them. The mainnet owner signs with `--account owner` (an encrypted Foundry keystore on the finance lead's laptop) or with MetaMask on the Controls page. The mainnet owner key is never in `.env`, never in the repo and never on the server.
- **Testnet first.** Mainnet only after `forge test` is green and the full testnet run below passed.

## Testnet run

```bash
cd contracts
forge build && forge test -vvv
source ../.env   # in the shell only; don't cat it
forge script script/Deploy.s.sol  --rpc-url $BOTCHAIN_TESTNET_RPC --broadcast --legacy
# put the address in .env as CONTRACT_ADDRESS_TESTNET, then:
forge script script/Setup.s.sol   --rpc-url $BOTCHAIN_TESTNET_RPC --broadcast --legacy --private-key $TESTNET_OWNER_PK
# wait TIMELOCK_DELAY_SECONDS (120 s in the demo), then:
forge script script/Execute.s.sol --rpc-url $BOTCHAIN_TESTNET_RPC --broadcast --legacy
```

Fund the vault with tUSDT (`cast send $PAY_TOKEN_TESTNET "transfer(address,uint256)" $CONTRACT_ADDRESS_TESTNET <amount> --legacy ...`), then send from an agent key one paying `pay()` and one `pay()` each for `PayoutMismatch`, `OverBudget` and `DuplicateInvoice`.

## Mainnet run

Same three scripts with `--rpc-url $BOTCHAIN_MAINNET_RPC`. Differences:
- Setup runs on the finance lead's laptop with `--account owner`. Ask the human to run it; give them the exact command.
- Verify right after deploying:
  ```bash
  forge verify-contract <ADDR> src/Countersign.sol:Countersign --chain 677 \
    --verifier blockscout --verifier-url https://scan.botchain.ai/api/
  ```
  If verification fails, carry on and retry later.

## Checks after any change

```bash
cast call $ADDR "paused()(bool)"             --rpc-url $RPC
cast call $ADDR "dailyCap()(uint256)"        --rpc-url $RPC
cast call $ADDR "remainingToday()(uint256)"  --rpc-url $RPC
cast call $ADDR "vaultBalance()(uint256)"    --rpc-url $RPC
cast call $ADDR "vendors(uint256)(address,bool,bool)" 1 --rpc-url $RPC
cast call $ADDR "changeCount()(uint256)"     --rpc-url $RPC
```

Amounts are base units. USDT has 6 decimals; read `decimals()` instead of assuming.

## Record everything

After each deploy or evidence transaction, add a row to `docs/PROGRESS.md` (Deployed contracts, Evidence transactions) with the explorer link: `https://scan.botchain.ai/tx/<hash>` for mainnet, `https://scan.bohr.life/tx/<hash>` for testnet. The BOT Chain track needs mainnet addresses, explorer links and transaction records in the submission. Testnet doesn't count.

## When something goes wrong

- `nonce too low`: another process used the key. Re-read the nonce with `cast nonce <addr> --block pending` and retry once.
- `insufficient funds for gas`: the key needs BOT. Tell the human which address and how much (around 1 BOT covers dozens of txs at ~50 gwei).
- `execute` reverts: the eta hasn't passed, or a precondition changed (the vendor already exists, the PO's vendor is missing). Check with `getChange(id)`.
- Paid invoice numbers can never be paid again. Before a mainnet rehearsal, regenerate the clean invoices with a new `--run-id` (SPEC §5).
