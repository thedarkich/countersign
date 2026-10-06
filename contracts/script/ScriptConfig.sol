// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Script} from "forge-std/Script.sol";
import {Countersign} from "../src/Countersign.sol";

abstract contract ScriptConfig is Script {
    function networkSuffix() internal view returns (string memory) {
        string memory configured = vm.envString("NETWORK");
        bool mainnet = keccak256(bytes(configured)) == keccak256("mainnet");
        require(mainnet || keccak256(bytes(configured)) == keccak256("testnet"), "invalid NETWORK");
        require(block.chainid == (mainnet ? 677 : 968), "RPC chain does not match NETWORK");
        return mainnet ? "_MAINNET" : "_TESTNET";
    }

    function configuredVault() internal view returns (Countersign) {
        address addr = vm.envAddress(string.concat("CONTRACT_ADDRESS", networkSuffix()));
        require(addr.code.length > 0, "vault not deployed");
        return Countersign(payable(addr));
    }

    function startOwner(Countersign vault) internal {
        if (block.chainid == 968) {
            uint256 key = vm.envUint("TESTNET_OWNER_PK");
            require(vm.addr(key) == vault.owner(), "test owner mismatch");
            vm.startBroadcast(key);
        } else {
            // Resolved by forge --account owner on the human's laptop.
            require(vm.envAddress("OWNER_ADDRESS") == vault.owner(), "mainnet owner mismatch");
            vm.startBroadcast(vault.owner());
        }
    }
}
