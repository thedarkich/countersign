// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {SetupValues} from "../script/SetupValues.sol";
import {Setup} from "../script/Setup.s.sol";

contract SetupValuesHarness {
    function amount(string memory value, uint8 decimals) external pure returns (uint256) {
        return SetupValues.baseUnits(value, decimals);
    }

    function expiry(string memory value) external pure returns (uint64) {
        return SetupValues.endOfChinaDay(value);
    }
}

contract SetupValuesTest is Test {
    SetupValuesHarness internal helper = new SetupValuesHarness();

    function testExactAmountConversions() public view {
        assertEq(helper.amount("15", 6), 15_000_000);
        assertEq(helper.amount("0.000001", 6), 1);
        assertEq(helper.amount("1.5", 18), 1.5 ether);
        assertEq(helper.amount("10", 0), 10);
    }

    function testExcessPrecisionAndMalformedAmountsFail() public {
        vm.expectRevert("amount exceeds token precision");
        helper.amount("0.0000001", 6);
        vm.expectRevert("invalid amount");
        helper.amount("-1", 6);
        vm.expectRevert("invalid decimal");
        helper.amount("1.", 6);
    }

    function testChinaDateBoundaryAndLeapYears() public view {
        assertEq(helper.expiry("1970-01-01"), 57599);
        assertEq(helper.expiry("2026-10-31"), 1793462399);
        assertEq(helper.expiry("2026-12-31"), 1798732799);
        assertEq(helper.expiry("2024-03-01") - helper.expiry("2024-02-28"), 2 days);
        assertEq(helper.expiry("2100-03-01") - helper.expiry("2100-02-28"), 1 days);
    }

    function testInvalidDatesFail() public {
        vm.expectRevert("invalid date");
        helper.expiry("2026-02-29");
        vm.expectRevert("invalid date");
        helper.expiry("2026-13-01");
    }

    function testRealFixtureJSONDecoding() public {
        Setup setup = new Setup();
        uint256[] memory vendors = setup.vendorIds();
        Setup.POConfig[] memory pos = setup.purchaseOrders(6);
        assertEq(vendors.length, 3);
        assertEq(vendors[0], 1);
        assertEq(pos.length, 3);
        assertEq(pos[1].cap, 5_000_000);
        assertEq(pos[1].id, 2);
        assertEq(pos[1].periodDays, 30);
        assertEq(pos[1].vendorId, 2);
    }
}
