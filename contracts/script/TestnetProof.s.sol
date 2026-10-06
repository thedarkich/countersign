// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ScriptConfig} from "./ScriptConfig.sol";
import {Countersign} from "../src/Countersign.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

abstract contract TestnetOnly is ScriptConfig {
    function checkedVault() internal view returns (Countersign vault, uint8 decimals) {
        require(block.chainid == 968, "testnet only");
        vault = configuredVault();
        decimals =
            address(vault.token()) == address(0) ? 18 : IERC20Metadata(address(vault.token())).decimals();
        require(decimals > 0 && decimals <= 18, "unsupported proof precision");
    }
}

/// @notice Top up the test vault to 20 test tokens, never a mainnet asset.
contract FundTestnet is TestnetOnly {
    function run() external {
        (Countersign vault, uint8 decimals) = checkedVault();
        uint256 target = 20 * 10 ** uint256(decimals);
        uint256 balance = vault.vaultBalance();
        if (balance >= target) return;
        startOwner(vault);
        if (address(vault.token()) == address(0)) {
            (bool sent,) = address(vault).call{value: target - balance}("");
            require(sent, "test funding failed");
        } else {
            require(vault.token().transfer(address(vault), target - balance), "test funding failed");
        }
        vm.stopBroadcast();
    }
}

/// @notice Direct contract evidence. This deliberately makes no AI quality claim.
contract ProveTestnet is TestnetOnly {
    function run() external {
        (Countersign vault, uint8 decimals) = checkedVault();
        uint256 amount = 10 ** uint256(decimals - 1); // 0.1 test token.
        bytes32 invoice = keccak256(abi.encode(uint256(1), vm.envString("EVIDENCE_INVOICE_NUMBER")));
        require(!vault.invoicePaid(invoice), "proof invoice already paid");
        (address payout, bool active, bool exists) = vault.vendors(1);
        require(active && exists, "vendor 1 not ready");
        address attacker = vm.envAddress("ATTACKER_ADDRESS");
        require(attacker != address(0) && attacker != payout, "invalid proof attacker");
        uint256 guarded = vm.envUint("AGENT_GUARDED_PK");
        uint256 naive = vm.envUint("AGENT_NAIVE_PK");
        require(vm.addr(guarded) == vm.envAddress("AGENT_GUARDED_ADDRESS"), "guarded identity mismatch");
        require(vm.addr(naive) == vm.envAddress("AGENT_NAIVE_ADDRESS"), "naive identity mismatch");
        vm.startBroadcast(guarded);
        require(vault.pay(1, payout, 1, amount, invoice), "clean payment failed");
        require(
            !vault.pay(
                1, payout, 1, vault.poRemaining(1) + amount + 1, keccak256(abi.encode(invoice, "over-budget"))
            ),
            "budget bypass"
        );
        require(!vault.pay(1, payout, 1, amount * 2, invoice), "changed-amount duplicate bypass");
        vm.stopBroadcast();
        vm.startBroadcast(naive);
        require(!vault.pay(1, attacker, 1, amount, keccak256(abi.encode(invoice, "payout"))), "payout bypass");
        vm.stopBroadcast();
    }
}
