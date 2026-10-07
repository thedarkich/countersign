// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ScriptConfig} from "./ScriptConfig.sol";
import {Countersign} from "../src/Countersign.sol";

/// @dev Forwards native BOT from the gas-only deployer: gas to the vault owner and the two agent keys, and,
/// for a native-BOT vault only, optional payment funding to the vault itself. Recipients come from the deployed
/// vault and the configured agent addresses; every amount is capped so a typo cannot drain the deployer.
contract FundGas is ScriptConfig {
    uint256 internal constant MAX_GAS_PER_RECIPIENT = 0.5 ether;
    uint256 internal constant MAX_VAULT_FUNDING = 20 ether;

    function run() external {
        Countersign vault = configuredVault();
        address[3] memory to =
            [vault.owner(), vm.envAddress("AGENT_GUARDED_ADDRESS"), vm.envAddress("AGENT_NAIVE_ADDRESS")];
        uint256 agentGas = vm.envUint("GAS_AGENT_WEI");
        uint256[3] memory amount = [vm.envUint("GAS_OWNER_WEI"), agentGas, agentGas];
        uint256 vaultFunding = vm.envOr("VAULT_FUND_WEI", uint256(0));
        uint256 deployer = vm.envUint("DEPLOYER_PK");
        require(to[1] != to[2], "agents must be distinct");
        for (uint256 i; i < 3; i++) {
            require(to[i] != vm.addr(deployer), "recipient is the deployer");
            require(amount[i] <= MAX_GAS_PER_RECIPIENT, "gas amount above cap");
        }
        require(vaultFunding <= MAX_VAULT_FUNDING, "vault funding above cap");
        require(
            vaultFunding == 0 || address(vault.token()) == address(0), "token vault: fund it with the token"
        );
        vm.startBroadcast(deployer);
        for (uint256 i; i < 3; i++) {
            if (amount[i] == 0) continue;
            (bool ok,) = to[i].call{value: amount[i]}("");
            require(ok, "gas transfer failed");
        }
        if (vaultFunding > 0) {
            (bool ok,) = address(vault).call{value: vaultFunding}("");
            require(ok, "vault funding failed");
        }
        vm.stopBroadcast();
    }
}
