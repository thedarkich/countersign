// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {Countersign} from "../src/Countersign.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract MockToken is ERC20 {
    bool public fail;
    bool public revertTransfer;
    constructor() ERC20("Test USDT", "tUSDT") {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }

    function failures(bool falseReturn, bool throwError) external {
        fail = falseReturn;
        revertTransfer = throwError;
    }

    function transfer(address to, uint256 amount) public override returns (bool) {
        require(!revertTransfer, "token transfer rejected");
        if (fail) return false;
        return super.transfer(to, amount);
    }
}

contract NoReturnToken {
    mapping(address => uint256) public balanceOf;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function transfer(address to, uint256 amount) external {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}

contract RejectNative {
    receive() external payable {
        revert("reject");
    }
}

contract ReentrantPayout {
    Countersign public vault;
    bool public rejected;
    bytes4 public reason;

    constructor(Countersign vault_) {
        vault = vault_;
    }

    receive() external payable {
        (bool ok, bytes memory result) =
            address(vault).call(abi.encodeCall(vault.pay, (1, address(this), 1, 1, keccak256("reentry"))));
        rejected = !ok;
        if (result.length >= 4) reason = bytes4(result);
    }
}

abstract contract VaultTests is Test {
    Countersign internal vault;
    MockToken internal mockToken;
    address internal agent = makeAddr("guarded");
    address internal other = makeAddr("other");
    address internal payout = makeAddr("vendor1");
    address internal payout2 = makeAddr("vendor2");
    bytes32 internal constant HASH = keccak256("invoice-1");
    uint64 internal constant DELAY = 120;
    uint64 internal expiry;

    event Paid(
        uint256 indexed vendorId,
        uint256 indexed poId,
        address indexed agent,
        address payTo,
        uint256 amount,
        bytes32 invoiceHash
    );
    event Blocked(
        uint256 indexed vendorId,
        uint256 indexed poId,
        address indexed agent,
        Countersign.Reason reason,
        address payTo,
        uint256 amount,
        bytes32 invoiceHash
    );

    function tokenMode() internal pure virtual returns (bool);

    function setUp() public virtual {
        vm.warp(1_800_000_000);
        if (tokenMode()) mockToken = new MockToken();
        vault = new Countersign(address(this), address(mockToken), DELAY, 150);
        expiry = uint64(block.timestamp + 365 days);
        bytes32[5] memory ids;
        ids[0] = vault.queueAddVendor(1, payout);
        ids[1] = vault.queueAddVendor(2, payout2);
        ids[2] = vault.queueAddPO(1, 1, 100, expiry, 0);
        ids[3] = vault.queueAddPO(2, 2, 100, expiry, 7);
        ids[4] = vault.queueAddAgent(agent);
        vm.warp(block.timestamp + DELAY);
        for (uint256 i; i < ids.length; i++) {
            vault.execute(ids[i]);
        }
        if (tokenMode()) mockToken.mint(address(vault), 1000);
        else vm.deal(address(vault), 1000);
    }

    function balance(address account) internal view returns (uint256) {
        return tokenMode() ? mockToken.balanceOf(account) : account.balance;
    }

    function payment(uint256 vendor, address recipient, uint256 po, uint256 amount, bytes32 hash)
        internal
        returns (bool)
    {
        vm.prank(agent);
        return vault.pay(vendor, recipient, po, amount, hash);
    }

    function checkBlock(
        Countersign.Reason reason,
        uint256 vendor,
        address recipient,
        uint256 po,
        uint256 amount,
        bytes32 hash
    ) internal {
        uint256 vaultBefore = vault.vaultBalance();
        uint256 recipientBefore = balance(recipient);
        bool invoiceBefore = vault.invoicePaid(hash);
        vm.expectEmit(true, true, true, true, address(vault));
        emit Blocked(vendor, po, agent, reason, recipient, amount, hash);
        assertFalse(payment(vendor, recipient, po, amount, hash));
        assertEq(vault.vaultBalance(), vaultBefore);
        assertEq(balance(recipient), recipientBefore);
        assertEq(vault.invoicePaid(hash), invoiceBefore);
    }

    function testPaidTransfersToRegistryAndRecordsState() public {
        vm.expectEmit(true, true, true, true, address(vault));
        emit Paid(1, 1, agent, payout, 20, HASH);
        assertTrue(payment(1, payout, 1, 20, HASH));
        assertEq(balance(payout), 20);
        assertEq(vault.vaultBalance(), 980);
        assertEq(vault.poRemaining(1), 80);
        assertEq(vault.remainingToday(), 130);
        assertTrue(vault.invoicePaid(HASH));
    }

    function testBlockedPaused() public {
        vault.pause();
        checkBlock(Countersign.Reason.Paused, 1, payout, 1, 1, HASH);
    }

    function testBlockedZeroAmount() public {
        checkBlock(Countersign.Reason.ZeroAmount, 1, payout, 1, 0, HASH);
    }

    function testBlockedUnknownVendor() public {
        checkBlock(Countersign.Reason.UnknownVendor, 99, payout, 1, 1, HASH);
    }

    function testBlockedVendorInactive() public {
        vault.deactivateVendor(1);
        checkBlock(Countersign.Reason.VendorInactive, 1, payout, 1, 1, HASH);
    }

    function testBlockedPayoutMismatch() public {
        checkBlock(Countersign.Reason.PayoutMismatch, 1, other, 1, 1, HASH);
    }

    function testBlockedUnknownPO() public {
        checkBlock(Countersign.Reason.UnknownPO, 1, payout, 99, 1, HASH);
    }

    function testBlockedPOVendorMismatch() public {
        checkBlock(Countersign.Reason.POVendorMismatch, 1, payout, 2, 1, HASH);
    }

    function testBlockedPOExpired() public {
        vm.warp(uint256(expiry) + 1);
        checkBlock(Countersign.Reason.POExpired, 1, payout, 1, 1, HASH);
    }

    function testBlockedOverBudget() public {
        checkBlock(Countersign.Reason.OverBudget, 1, payout, 1, 101, HASH);
    }

    function testBlockedDuplicateDifferentAmount() public {
        assertTrue(payment(1, payout, 1, 10, HASH));
        checkBlock(Countersign.Reason.DuplicateInvoice, 1, payout, 1, 11, HASH);
    }

    function testBlockedOverDailyCap() public {
        assertTrue(payment(1, payout, 1, 100, HASH));
        checkBlock(Countersign.Reason.OverDailyCap, 2, payout2, 2, 51, keccak256("another"));
    }

    function testBlockedInsufficientFunds() public {
        bytes32 id = vault.queueWithdraw(1000);
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        checkBlock(Countersign.Reason.InsufficientFunds, 1, payout, 1, 1, HASH);
    }

    function testNonAgentRevertsEvenWhenPaused() public {
        vault.pause();
        vm.expectRevert(Countersign.NotAgent.selector);
        vm.prank(other);
        vault.pay(1, payout, 1, 1, HASH);
    }

    function testFirstFailureWins() public {
        vault.pause();
        checkBlock(Countersign.Reason.Paused, 99, other, 99, 0, HASH);
        bytes32 id = vault.queueUnpause();
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        checkBlock(Countersign.Reason.ZeroAmount, 99, other, 99, 0, HASH);
        checkBlock(Countersign.Reason.UnknownVendor, 99, other, 99, 1, HASH);
        vault.deactivateVendor(1);
        checkBlock(Countersign.Reason.VendorInactive, 1, other, 99, 1, HASH);
    }

    function testMaximumAmountLogsInsteadOfArithmeticRevert() public {
        assertTrue(payment(1, payout, 1, 1, HASH));
        checkBlock(Countersign.Reason.OverBudget, 1, payout, 1, type(uint256).max, keccak256("max"));
    }

    function testDailyCapCanBeLoweredBelowAlreadySpent() public {
        assertTrue(payment(1, payout, 1, 10, HASH));
        vault.lowerDailyCap(5);
        assertEq(vault.remainingToday(), 0);
        checkBlock(Countersign.Reason.OverDailyCap, 1, payout, 1, 1, keccak256("next"));
    }

    function testDailyCapResetsAtUTCBoundary() public {
        assertTrue(payment(1, payout, 1, 100, HASH));
        vm.warp((block.timestamp / 1 days + 1) * 1 days);
        assertEq(vault.remainingToday(), 150);
        assertTrue(payment(2, payout2, 2, 100, keccak256("nextday")));
        assertEq(vault.spentToday(), 100);
    }

    function testStandingPORollsWholePeriodsNotNow() public {
        (,,,,, uint64 start,,) = vault.pos(2);
        assertTrue(payment(2, payout2, 2, 100, HASH));
        vm.warp(uint256(start) + 21 days + 15);
        assertEq(vault.poRemaining(2), 100);
        assertTrue(payment(2, payout2, 2, 10, keccak256("period")));
        (,, uint256 spent,,, uint64 rolled,,) = vault.pos(2);
        assertEq(rolled, uint256(start) + 21 days);
        assertEq(spent, 10);
    }

    function testOneOffDoesNotRefill() public {
        assertTrue(payment(1, payout, 1, 100, HASH));
        vm.warp(block.timestamp + 30 days);
        assertEq(vault.poRemaining(1), 0);
        checkBlock(Countersign.Reason.OverBudget, 1, payout, 1, 1, keccak256("no-refill"));
    }

    function testDuplicateSurvivesPeriodAndDayReset() public {
        assertTrue(payment(2, payout2, 2, 10, HASH));
        vm.warp(block.timestamp + 7 days);
        checkBlock(Countersign.Reason.DuplicateInvoice, 2, payout2, 2, 11, HASH);
        assertEq(vault.spentToday(), 0);
        assertEq(vault.poRemaining(2), 100);
    }

    function testExpiryIsInclusive() public {
        vm.warp(expiry);
        assertTrue(payment(1, payout, 1, 1, HASH));
        vm.warp(uint256(expiry) + 1);
        assertEq(vault.poRemaining(1), 0);
    }

    function testInstantCloseAndRevoke() public {
        vault.closePO(1);
        assertEq(vault.poRemaining(1), 0);
        checkBlock(Countersign.Reason.UnknownPO, 1, payout, 1, 1, HASH);
        vault.revokeAgent(agent);
        vm.expectRevert(Countersign.NotAgent.selector);
        vm.prank(agent);
        vault.pay(2, payout2, 2, 1, HASH);
    }

    function testUnknownViews() public {
        assertEq(vault.poRemaining(999), 0);
        assertEq(vault.getChange(bytes32(0)).eta, 0);
    }

    function testTimelockAnyoneExecutesOnlyAfterETA() public {
        bytes32 id = vault.queueRaiseDailyCap(200);
        uint64 eta = vault.getChange(id).eta;
        vm.warp(uint256(eta) - 1);
        vm.expectRevert(abi.encodeWithSelector(Countersign.ChangeNotReady.selector, eta));
        vault.execute(id);
        vm.warp(eta);
        vm.prank(other);
        vault.execute(id);
        assertEq(vault.dailyCap(), 200);
        assertTrue(vault.getChange(id).executed);
        vm.expectRevert(Countersign.ChangeUnavailable.selector);
        vault.execute(id);
    }

    function testCancellationAndUnknownChange() public {
        bytes32 id = vault.queueRaiseDailyCap(200);
        vault.cancel(id);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(Countersign.ChangeUnavailable.selector);
        vault.execute(id);
        vm.expectRevert(Countersign.ChangeUnavailable.selector);
        vault.cancel(id);
        vm.expectRevert(Countersign.ChangeNotFound.selector);
        vault.execute(bytes32(0));
        vm.expectRevert(Countersign.ChangeNotFound.selector);
        vault.cancel(bytes32(0));
    }

    function testDuplicateQueuedChangesRevalidateAtExecution() public {
        bytes32 first = vault.queueAddVendor(3, other);
        bytes32 second = vault.queueAddVendor(3, payout);
        assertNotEq(first, second);
        vm.warp(block.timestamp + DELAY);
        vault.execute(first);
        vm.expectRevert(Countersign.VendorAlreadyExists.selector);
        vault.execute(second);
        assertFalse(vault.getChange(second).executed);
    }

    function testRaiseRevalidatedAfterAnotherRaise() public {
        bytes32 first = vault.queueRaiseDailyCap(200);
        bytes32 second = vault.queueRaiseDailyCap(300);
        vm.warp(block.timestamp + DELAY);
        vault.execute(second);
        vm.expectRevert(Countersign.InvalidValue.selector);
        vault.execute(first);
    }

    function testPOExecutionNeedsVendorAndFreshExpiry() public {
        bytes32 missing = vault.queueAddPO(3, 99, 10, expiry, 0);
        bytes32 expired = vault.queueAddPO(4, 1, 10, uint64(block.timestamp + 1), 0);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(Countersign.VendorNotFound.selector);
        vault.execute(missing);
        vm.expectRevert(Countersign.InvalidValue.selector);
        vault.execute(expired);
        assertFalse(vault.getChange(missing).executed);
    }

    function testSetPayoutReactivatesAndOldPayoutStopsWorking() public {
        vault.deactivateVendor(1);
        bytes32 id = vault.queueSetPayout(1, other);
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        (address registered, bool active,) = vault.vendors(1);
        assertEq(registered, other);
        assertTrue(active);
        checkBlock(Countersign.Reason.PayoutMismatch, 1, payout, 1, 1, HASH);
        assertTrue(payment(1, other, 1, 1, HASH));
    }

    function testUnpauseNeedsDelay() public {
        vault.pause();
        bytes32 id = vault.queueUnpause();
        assertTrue(vault.paused());
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        assertFalse(vault.paused());
    }

    function testWithdrawUsesOwnerAtExecutionAfterTwoStepTransfer() public {
        bytes32 id = vault.queueWithdraw(50);
        vault.transferOwnership(other);
        assertEq(vault.owner(), address(this));
        vm.prank(other);
        vault.acceptOwnership();
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        assertEq(balance(other), 50);
        assertEq(vault.vaultBalance(), 950);
    }

    function testWithdrawInsufficientRollsBackExecutedFlag() public {
        bytes32 id = vault.queueWithdraw(1001);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(Countersign.InsufficientVaultFunds.selector);
        vault.execute(id);
        assertFalse(vault.getChange(id).executed);
    }

    function testAllOwnerEntryPointsDenyOtherCallers() public {
        bytes[] memory calls = new bytes[](13);
        calls[0] = abi.encodeCall(vault.queueAddVendor, (3, other));
        calls[1] = abi.encodeCall(vault.queueSetPayout, (1, other));
        calls[2] = abi.encodeCall(vault.queueAddPO, (3, 1, 1, expiry, 0));
        calls[3] = abi.encodeCall(vault.queueAddAgent, (other));
        calls[4] = abi.encodeCall(vault.queueRaiseDailyCap, (200));
        calls[5] = abi.encodeCall(vault.queueUnpause, ());
        calls[6] = abi.encodeCall(vault.queueWithdraw, (1));
        calls[7] = abi.encodeCall(vault.cancel, (bytes32(0)));
        calls[8] = abi.encodeCall(vault.pause, ());
        calls[9] = abi.encodeCall(vault.deactivateVendor, (1));
        calls[10] = abi.encodeCall(vault.closePO, (1));
        calls[11] = abi.encodeCall(vault.revokeAgent, (agent));
        calls[12] = abi.encodeCall(vault.lowerDailyCap, (1));
        for (uint256 i; i < calls.length; i++) {
            vm.prank(other);
            (bool ok, bytes memory result) = address(vault).call(calls[i]);
            assertFalse(ok);
            assertEq(result, abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, other));
        }
    }

    function testBadConfigurationRejected() public {
        vm.expectRevert(Countersign.InvalidAddress.selector);
        vault.queueAddVendor(3, address(0));
        vm.expectRevert(Countersign.InvalidAddress.selector);
        vault.queueSetPayout(1, address(vault));
        vm.expectRevert(Countersign.InvalidAddress.selector);
        vault.queueAddAgent(address(0));
        vm.expectRevert(Countersign.InvalidValue.selector);
        vault.lowerDailyCap(151);
        vm.expectRevert(Countersign.InvalidValue.selector);
        vault.queueRaiseDailyCap(150);
        vm.expectRevert(Countersign.InvalidValue.selector);
        new Countersign(address(this), address(0), 0, 1);
        vm.expectRevert(Countersign.InvalidAddress.selector);
        new Countersign(address(this), other, 120, 1);
    }

    function testFuzzArbitraryRecipientCannotReceive(address recipient, uint96 amount) public {
        vm.assume(recipient != payout);
        uint256 boundedAmount = _bound(uint256(amount), 1, 100);
        checkBlock(Countersign.Reason.PayoutMismatch, 1, recipient, 1, boundedAmount, HASH);
    }

    function testFuzzValidPaymentConservesFunds(uint96 amount) public {
        uint256 value = _bound(uint256(amount), 1, 100);
        uint256 totalBefore = vault.vaultBalance() + balance(payout);
        assertTrue(payment(1, payout, 1, value, HASH));
        assertEq(vault.vaultBalance() + balance(payout), totalBefore);
        assertEq(balance(payout), value);
    }

    receive() external payable {}
}

contract NativeVaultTest is VaultTests {
    function tokenMode() internal pure override returns (bool) {
        return false;
    }

    function testRejectedNativeTransferRollsBackEverything() public {
        RejectNative reject = new RejectNative();
        bytes32 id = vault.queueSetPayout(1, address(reject));
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        vm.expectRevert(Countersign.NativeTransferFailed.selector);
        vm.prank(agent);
        vault.pay(1, address(reject), 1, 10, HASH);
        assertFalse(vault.invoicePaid(HASH));
        assertEq(vault.poRemaining(1), 100);
        assertEq(vault.spentToday(), 0);
        assertEq(vault.vaultBalance(), 1000);
    }

    function testRegisteredReentrantRecipientCannotPayTwice() public {
        ReentrantPayout recipient = new ReentrantPayout(vault);
        bytes32 id = vault.queueSetPayout(1, address(recipient));
        bytes32 agentId = vault.queueAddAgent(address(recipient));
        vm.warp(block.timestamp + DELAY);
        vault.execute(id);
        vault.execute(agentId);
        assertTrue(payment(1, address(recipient), 1, 10, HASH));
        assertTrue(recipient.rejected());
        assertEq(recipient.reason(), ReentrancyGuard.ReentrancyGuardReentrantCall.selector);
        assertEq(address(recipient).balance, 10);
        assertEq(vault.spentToday(), 10);
        assertFalse(vault.invoicePaid(keccak256("reentry")));
    }
}

contract TokenVaultTest is VaultTests {
    function tokenMode() internal pure override returns (bool) {
        return true;
    }

    function testFalseReturningTokenRollsBackEverything() public {
        mockToken.failures(true, false);
        vm.expectRevert(
            abi.encodeWithSelector(SafeERC20.SafeERC20FailedOperation.selector, address(mockToken))
        );
        vm.prank(agent);
        vault.pay(1, payout, 1, 10, HASH);
        assertFalse(vault.invoicePaid(HASH));
        assertEq(vault.poRemaining(1), 100);
        assertEq(vault.spentToday(), 0);
        assertEq(vault.vaultBalance(), 1000);
    }

    function testRevertingTokenRollsBackEverything() public {
        mockToken.failures(false, true);
        vm.expectRevert("token transfer rejected");
        vm.prank(agent);
        vault.pay(1, payout, 1, 10, HASH);
        assertFalse(vault.invoicePaid(HASH));
        assertEq(vault.poRemaining(1), 100);
        assertEq(vault.spentToday(), 0);
    }
}

contract TokenCompatibilityTest is Test {
    function testMissingReturnDataSupported() public {
        NoReturnToken token = new NoReturnToken();
        Countersign vault = new Countersign(address(this), address(token), 120, 100);
        address payout = makeAddr("recipient");
        bytes32 vendor = vault.queueAddVendor(1, payout);
        bytes32 po = vault.queueAddPO(1, 1, 100, uint64(block.timestamp + 1 days), 0);
        bytes32 agent = vault.queueAddAgent(address(this));
        vm.warp(block.timestamp + 120);
        vault.execute(vendor);
        vault.execute(po);
        vault.execute(agent);
        token.mint(address(vault), 100);
        assertTrue(vault.pay(1, payout, 1, 10, keccak256("missing-return")));
        assertEq(token.balanceOf(payout), 10);
    }
}
