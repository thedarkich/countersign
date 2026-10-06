// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ScriptConfig} from "./ScriptConfig.sol";
import {SetupValues} from "./SetupValues.sol";
import {Countersign} from "../src/Countersign.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

contract Setup is ScriptConfig {
    struct POConfig {
        uint256 id;
        uint256 vendorId;
        uint256 cap;
        uint64 expiry;
        uint32 periodDays;
    }

    function vendorIds() public view returns (uint256[] memory) {
        return abi.decode(vm.parseJson(vm.readFile("../data/vendors.json"), "$[*].id"), (uint256[]));
    }

    function purchaseOrders(uint8 decimals) public view returns (POConfig[] memory result) {
        string memory json = vm.readFile("../data/pos.json");
        uint256[] memory ids = abi.decode(vm.parseJson(json, "$[*].po_id"), (uint256[]));
        result = new POConfig[](ids.length);
        for (uint256 i; i < ids.length; i++) {
            string memory path = string.concat("$[", vm.toString(i), "].");
            uint256 period = vm.parseJsonUint(json, string.concat(path, "period_days"));
            require(period <= type(uint32).max, "period too long");
            result[i] = POConfig({
                id: ids[i],
                vendorId: vm.parseJsonUint(json, string.concat(path, "vendor_id")),
                cap: SetupValues.baseUnits(vm.parseJsonString(json, string.concat(path, "cap")), decimals),
                expiry: SetupValues.endOfChinaDay(vm.parseJsonString(json, string.concat(path, "expiry"))),
                periodDays: uint32(period)
            });
        }
    }

    function run() external {
        Countersign vault = configuredVault();
        uint8 decimals =
            address(vault.token()) == address(0) ? 18 : IERC20Metadata(address(vault.token())).decimals();
        uint256[] memory vendors = vendorIds();
        POConfig[] memory pos = purchaseOrders(decimals);
        address guarded = vm.envAddress("AGENT_GUARDED_ADDRESS");
        address naive = vm.envAddress("AGENT_NAIVE_ADDRESS");
        require(guarded != naive, "agents must be distinct");
        address[] memory payouts = new address[](vendors.length);
        for (uint256 i; i < vendors.length; i++) {
            payouts[i] = vm.envAddress(string.concat("VENDOR", vm.toString(vendors[i]), "_PAYOUT"));
        }
        startOwner(vault);
        for (uint256 i; i < vendors.length; i++) {
            vault.queueAddVendor(vendors[i], payouts[i]);
        }
        for (uint256 i; i < pos.length; i++) {
            vault.queueAddPO(pos[i].id, pos[i].vendorId, pos[i].cap, pos[i].expiry, pos[i].periodDays);
        }
        vault.queueAddAgent(guarded);
        vault.queueAddAgent(naive);
        vm.stopBroadcast();
    }
}
