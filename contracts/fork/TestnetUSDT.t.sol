// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {Countersign} from "../src/Countersign.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

/// @dev Runs only with FOUNDRY_PROFILE=fork. All writes are local fork state.
contract TestnetUSDTForkTest is Test {
    function testRealTestnetTokenPaidFlow() public {
        vm.createSelectFork("https://rpc.bohr.life");
        assertEq(block.chainid, 968);
        IERC20Metadata token = IERC20Metadata(0x75edC9335175Fc0552D51D48439F229c10420fe3);
        uint8 decimals = token.decimals();
        assertEq(decimals, 6);
        assertGt(bytes(token.symbol()).length, 0);
        address holder = 0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272;
        uint256 funding = 10 ** decimals;
        assertGe(token.balanceOf(holder), funding, "fork funding fixture lacks tUSDT");
        Countersign vault = new Countersign(address(this), address(token), 120, funding);
        address vendor = makeAddr("fork-vendor");
        bytes32 v = vault.queueAddVendor(1, vendor);
        bytes32 p = vault.queueAddPO(1, 1, funding, uint64(block.timestamp + 1 days), 0);
        bytes32 a = vault.queueAddAgent(address(this));
        vm.warp(block.timestamp + 120);
        vault.execute(v); vault.execute(p); vault.execute(a);
        vm.prank(holder);
        assertTrue(token.transfer(address(vault), funding));
        assertTrue(vault.pay(1, vendor, 1, funding / 10, keccak256("local-fork-invoice")));
        assertEq(token.balanceOf(vendor), funding / 10);
        assertEq(vault.vaultBalance(), funding - funding / 10);
    }
}
