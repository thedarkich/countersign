// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ScriptConfig} from "./ScriptConfig.sol";
import {Countersign} from "../src/Countersign.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

contract Deploy is ScriptConfig {
    function run() external returns (Countersign vault) {
        string memory suffix = networkSuffix();
        address payToken = vm.envAddress(string.concat("PAY_TOKEN", suffix));
        if (payToken != address(0)) {
            require(payToken.code.length > 0, "token missing");
            require(IERC20Metadata(payToken).decimals() <= 77, "unsupported token precision");
            require(bytes(IERC20Metadata(payToken).symbol()).length > 0, "token symbol missing");
        }
        address owner =
            block.chainid == 968 ? vm.addr(vm.envUint("TESTNET_OWNER_PK")) : vm.envAddress("OWNER_ADDRESS");
        uint256 deployer = vm.envUint("DEPLOYER_PK");
        require(vm.addr(deployer) != owner, "deployer must be gas-only");
        uint256 wait = vm.envUint("TIMELOCK_DELAY_SECONDS");
        require(wait > 0 && wait <= type(uint64).max, "invalid delay");
        uint256 cap = vm.envUint("INITIAL_DAILY_CAP");
        vm.startBroadcast(deployer);
        vault = new Countersign(owner, payToken, uint64(wait), cap);
        vm.stopBroadcast();
    }
}
