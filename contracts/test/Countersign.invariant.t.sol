// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {Countersign} from "../src/Countersign.sol";
import {MockToken} from "./Countersign.t.sol";

contract PaymentHandler is Test {
    Countersign public vault;
    MockToken public token;
    address public agent1;
    address public agent2;
    address public vendor1;
    address public vendor2;
    address public outsider;
    uint256 public totalPaid;
    uint256 public successfulCalls;
    uint256 public blockedCalls;
    uint256 public unauthorizedCalls;
    uint256 public unauthorizedValue;
    uint256 private sequence;

    constructor(
        Countersign vault_,
        MockToken token_,
        address a1,
        address a2,
        address v1,
        address v2,
        address stranger
    ) {
        vault = vault_;
        token = token_;
        agent1 = a1;
        agent2 = a2;
        vendor1 = v1;
        vendor2 = v2;
        outsider = stranger;
    }

    function balance(address account) internal view returns (uint256) {
        return address(token) == address(0) ? account.balance : token.balanceOf(account);
    }

    function validPayment(uint256 vendorSeed, uint256 amountSeed) public {
        uint256 vendor = _bound(vendorSeed, 1, 2);
        uint256 amount = _bound(amountSeed, 1, 100);
        _attempt(agent1, vendor, vendor == 1 ? vendor1 : vendor2, vendor, amount, bytes32(++sequence + 1000));
    }

    function randomPayment(
        uint256 actorSeed,
        uint256 vendorSeed,
        uint256 recipientSeed,
        uint256 poSeed,
        uint256 amountSeed,
        uint256 invoiceSeed
    ) public {
        uint256 actor = _bound(actorSeed, 0, 2);
        address sender = actor == 0 ? agent1 : actor == 1 ? agent2 : outsider;
        uint256 recipient = _bound(recipientSeed, 0, 2);
        address payTo = recipient == 0 ? vendor1 : recipient == 1 ? vendor2 : outsider;
        uint256 amount = amountSeed % 8 == 0 ? type(uint256).max : _bound(amountSeed, 0, 201);
        _attempt(
            sender,
            _bound(vendorSeed, 0, 3),
            payTo,
            _bound(poSeed, 0, 3),
            amount,
            bytes32(_bound(invoiceSeed, 1, 30))
        );
    }

    function advanceTime(uint256 secondsSeed) public {
        vm.warp(block.timestamp + _bound(secondsSeed, 0, 30 days));
    }

    function _attempt(
        address sender,
        uint256 vendor,
        address recipient,
        uint256 po,
        uint256 amount,
        bytes32 hash
    ) internal {
        uint256 beforeForeign = balance(outsider);
        uint256 beforeVault = vault.vaultBalance();
        uint256 beforeRecipient = balance(recipient);
        vm.prank(sender);
        (bool ok, bytes memory result) =
            address(vault).call(abi.encodeCall(vault.pay, (vendor, recipient, po, amount, hash)));
        if (sender == outsider) {
            assertFalse(ok, "unregistered sender succeeded");
            assertEq(result, abi.encodeWithSelector(Countersign.NotAgent.selector));
            unauthorizedCalls++;
        } else {
            assertTrue(ok, "registered agent policy input reverted");
            if (abi.decode(result, (bool))) {
                totalPaid += amount;
                successfulCalls++;
                assertEq(beforeVault - vault.vaultBalance(), amount);
                assertEq(balance(recipient) - beforeRecipient, amount);
                assertTrue(vault.invoicePaid(hash));
            } else {
                blockedCalls++;
                assertEq(vault.vaultBalance(), beforeVault);
                assertEq(balance(recipient), beforeRecipient);
            }
        }
        unauthorizedValue += balance(outsider) - beforeForeign;
    }
}

abstract contract InvariantBase is StdInvariant, Test {
    Countersign internal vault;
    MockToken internal token;
    PaymentHandler internal handler;
    address internal vendor1 = makeAddr("vendor-one");
    address internal vendor2 = makeAddr("vendor-two");
    address internal outsider = makeAddr("unregistered-recipient");
    uint256 internal constant FUNDING = 1_000_000;

    function useToken() internal pure virtual returns (bool);

    function setUp() public {
        vm.warp(1_800_000_000);
        if (useToken()) token = new MockToken();
        vault = new Countersign(address(this), address(token), 120, 150);
        address a1 = makeAddr("agent-one");
        address a2 = makeAddr("agent-two");
        bytes32[6] memory changes;
        changes[0] = vault.queueAddVendor(1, vendor1);
        changes[1] = vault.queueAddVendor(2, vendor2);
        changes[2] = vault.queueAddPO(1, 1, 100, type(uint64).max, 0);
        changes[3] = vault.queueAddPO(2, 2, 100, type(uint64).max, 7);
        changes[4] = vault.queueAddAgent(a1);
        changes[5] = vault.queueAddAgent(a2);
        vm.warp(block.timestamp + 120);
        for (uint256 i; i < changes.length; i++) {
            vault.execute(changes[i]);
        }
        if (useToken()) token.mint(address(vault), FUNDING);
        else vm.deal(address(vault), FUNDING);
        handler = new PaymentHandler(vault, token, a1, a2, vendor1, vendor2, outsider);
        bytes4[] memory selectors = new bytes4[](3);
        selectors[0] = handler.validPayment.selector;
        selectors[1] = handler.randomPayment.selector;
        selectors[2] = handler.advanceTime.selector;
        targetSelector(FuzzSelector({addr: address(handler), selectors: selectors}));
        targetContract(address(handler));
    }

    function invariantNoFundsReachUnregisteredAddress() public view {
        assertEq(handler.unauthorizedValue(), 0);
    }

    function invariantConservationOfFunding() public view {
        assertEq(vault.vaultBalance() + handler.totalPaid(), FUNDING);
        uint256 vendorBalances = useToken()
            ? token.balanceOf(vendor1) + token.balanceOf(vendor2)
            : vendor1.balance + vendor2.balance;
        assertEq(vendorBalances, handler.totalPaid());
    }

    function invariantBudgetsAndDailyCapHold() public view {
        (, uint256 cap1, uint256 spent1,,,,,) = vault.pos(1);
        (, uint256 cap2, uint256 spent2,,,,,) = vault.pos(2);
        assertLe(spent1, cap1);
        assertLe(spent2, cap2);
        assertLe(vault.spentToday(), vault.dailyCap());
    }

    function afterInvariant() public view {
        assertGt(handler.successfulCalls(), 0, "campaign never paid");
        assertGt(handler.blockedCalls(), 0, "campaign never exercised policy blocks");
    }
}

contract NativeInvariantTest is InvariantBase {
    function useToken() internal pure override returns (bool) {
        return false;
    }
}

contract TokenInvariantTest is InvariantBase {
    function useToken() internal pure override returns (bool) {
        return true;
    }
}
