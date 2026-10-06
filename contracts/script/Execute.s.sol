// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ScriptConfig} from "./ScriptConfig.sol";
import {Countersign} from "../src/Countersign.sol";

contract Execute is ScriptConfig {
    function run() external {
        Countersign vault = configuredVault();
        uint256 count = vault.changeCount();
        // Permissionless execution uses the deployer's gas-only key.
        vm.startBroadcast(vm.envUint("DEPLOYER_PK"));
        for (uint256 i; i < count; i++) {
            bytes32 id = vault.changeIds(i);
            Countersign.Change memory change = vault.getChange(id);
            if (!change.executed && !change.cancelled && block.timestamp >= change.eta) {
                // Revert on a stale precondition; do not silently claim setup succeeded.
                vault.execute(id);
            }
        }
        vm.stopBroadcast();
    }
}
