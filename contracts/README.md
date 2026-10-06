# Countersign vault

Solidity 0.8.24 / Paris EVM / optimized build, with OpenZeppelin 5.0.2 and forge-std 1.9.7. Native BOT or one immutable ERC-20 asset per deployment.

## Local checks

From Ubuntu, `~/countersign/contracts`:

```bash
forge build
forge test -vv
FOUNDRY_PROFILE=fork forge test -vv
```

The fork profile reads BOT testnet, impersonates a funded fixture account only inside the local VM, and never broadcasts. The normal suite needs no RPC or private keys.

If dependencies are absent:

```bash
forge install --root . --no-git --shallow OpenZeppelin/openzeppelin-contracts@v5.0.2
forge install --root . --no-git --shallow foundry-rs/forge-std@v1.9.7
```

The initial install used official release packages after a full Git clone stalled. Exact archives and checksums are in `dependencies.json`; dependency code is ignored in Git and its upstream licenses remain in the installed directories.

## Scripts

- `Deploy.s.sol`: validates NETWORK against the RPC chain ID, token metadata and separate owner/deployer identities. Reads private values only at runtime.
- `Setup.s.sol`: reads the vendor/PO fixtures; converts decimal amounts exactly; interprets expiry dates as 23:59:59 China time. Queues all three vendors first, then their POs, then the two agents.
- `Execute.s.sol`: uses the deployer's gas-only key to execute mature changes in queue order. Stale preconditions are errors, not silently skipped successes.

Every BOT Chain broadcast requires `--legacy`. Supply the project environment privately to the process; never put keys in command-line arguments or logs. Testnet owner signing uses the configured throwaway key. On mainnet, the human runs Setup with `--account owner` on their own laptop; no mainnet owner key enters the project/server.

BOT Chain testnet deployment: [0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B](https://scan.bohr.life/address/0x89Ea32CCB3c951ad48a56Dd3A156aeF616bD7C1B). Source verification passed. Public receipts and initial proof are recorded in `../docs/deployments/testnet.json`. Mainnet funding/deployment remain, so Phase 1 is not yet complete.

## Testnet operations

The project configuration is outside `contracts/`; pass it directly to the runtime without printing it or placing keys in arguments:

```bash
../backend/.venv/bin/python -m dotenv -f ../.env run --no-override -- \
  forge script script/Execute.s.sol:Execute --rpc-url https://rpc.bohr.life --broadcast --legacy --slow
```

`TestnetProof.s.sol:FundTestnet` tops the vault up to 20 test tokens. `ProveTestnet` sends a 0.1-token payment and three blocked attempts (payout mismatch, over-budget, duplicate with a changed amount); it requires a fresh, normalized `EVIDENCE_INVOICE_NUMBER`. Both scripts refuse mainnet. These are direct contract checks and do not claim that an AI was fooled. The initial proof ID is `CSLIVE20261006A`; never reuse it to pay again. `scripts/record_testnet_proof.py` verifies this initial checkpoint and indexes its public receipts without loading keys; its exact balance assertions apply before further payments.

Foundry's `vm.setEnv` is process-wide. Wallet/vault-changing rehearsals are grouped in one script-flow test to avoid parallel test contamination. No contract logic changed for this deployment.

## Scope and safety

Rules block by emitting `Blocked` and returning false; unregistered callers, reentrancy and failed transfers can revert. A reverted transfer cannot mark an invoice paid. Arithmetic comparisons handle malicious maximum-size amounts without policy reverts. A hash is agent-supplied: new fake invoice numbers can consume real-vendor budgets. Neither the contract nor its tests prove invoice authenticity.

The owner controls delayed policy changes and instant restrictions. A previously queued permission expansion remains pending after a safety action until cancelled. The same owner must monitor/cancel it. Ownable2Step transfers ownership through explicit acceptance; inherited renunciation can remove administration permanently and is not exposed by the UI.

Only the selected, reviewed BOT tokens are intended for ERC-20 use. Fee-on-transfer, rebasing and arbitrary malicious tokens are unsupported. Read `../docs/security/CONTRACT_REVIEW.md`.
