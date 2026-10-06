// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @notice Bounds agent payments by owner-approved destinations and budgets.
/// @dev Rules do not prove invoice authenticity. invoiceHash is supplied by the
/// agent; a stolen key can invent hashes and spend remaining approved budgets.
contract Countersign is Ownable2Step, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    enum Kind {
        AddVendor,
        SetPayout,
        AddPO,
        AddAgent,
        RaiseDailyCap,
        Unpause,
        Withdraw
    }
    enum Reason {
        None,
        Paused,
        ZeroAmount,
        UnknownVendor,
        VendorInactive,
        PayoutMismatch,
        UnknownPO,
        POVendorMismatch,
        POExpired,
        OverBudget,
        DuplicateInvoice,
        OverDailyCap,
        InsufficientFunds
    }

    struct Vendor {
        address payout;
        bool active;
        bool exists;
    }

    struct PO {
        uint256 vendorId;
        uint256 cap;
        uint256 spent;
        uint64 expiry;
        uint32 periodDays;
        uint64 periodStart;
        bool exists;
        bool closed;
    }

    struct Change {
        Kind kind;
        bytes data;
        uint64 eta;
        bool executed;
        bool cancelled;
    }

    IERC20 public immutable token;
    uint64 public immutable delay;
    mapping(uint256 => Vendor) public vendors;
    mapping(uint256 => PO) public pos;
    mapping(address => bool) public isAgent;
    mapping(bytes32 => bool) public invoicePaid;
    mapping(bytes32 => Change) internal changes;
    bytes32[] public changeIds;
    uint256 public dailyCap;
    uint256 public spentToday;
    uint64 public currentDay;
    uint256 private changeNonce;

    error NotAgent();
    error InvalidAddress();
    error InvalidValue();
    error VendorAlreadyExists();
    error VendorNotFound();
    error POAlreadyExists();
    error PONotFound();
    error AgentAlreadyActive();
    error ChangeNotFound();
    error ChangeNotReady(uint64 eta);
    error ChangeUnavailable();
    error NativeTransferFailed();
    error InsufficientVaultFunds();

    event ChangeQueued(bytes32 indexed id, Kind kind, bytes data, uint64 eta);
    event ChangeExecuted(bytes32 indexed id, Kind kind);
    event ChangeCancelled(bytes32 indexed id);
    event VendorDeactivated(uint256 indexed vendorId);
    event POClosed(uint256 indexed poId);
    event AgentRevoked(address indexed agent);
    event DailyCapLowered(uint256 newCap);
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
        Reason reason,
        address payTo,
        uint256 amount,
        bytes32 invoiceHash
    );

    constructor(address initialOwner, address token_, uint64 delay_, uint256 initialDailyCap)
        Ownable(initialOwner)
    {
        if (delay_ == 0) revert InvalidValue();
        if (token_ != address(0) && token_.code.length == 0) revert InvalidAddress();
        token = IERC20(token_);
        delay = delay_;
        dailyCap = initialDailyCap;
        currentDay = uint64(block.timestamp / 1 days);
    }

    function queueAddVendor(uint256 vendorId, address payout) external onlyOwner returns (bytes32) {
        _validPayout(payout);
        if (vendors[vendorId].exists) revert VendorAlreadyExists();
        return _queue(Kind.AddVendor, abi.encode(vendorId, payout));
    }

    function queueSetPayout(uint256 vendorId, address newPayout) external onlyOwner returns (bytes32) {
        _validPayout(newPayout);
        if (!vendors[vendorId].exists) revert VendorNotFound();
        return _queue(Kind.SetPayout, abi.encode(vendorId, newPayout));
    }

    function queueAddPO(uint256 poId, uint256 vendorId, uint256 cap, uint64 expiry, uint32 periodDays)
        external
        onlyOwner
        returns (bytes32)
    {
        if (pos[poId].exists) revert POAlreadyExists();
        if (cap == 0 || expiry < block.timestamp) revert InvalidValue();
        // Vendor existence is checked at execution, so initial setup can queue
        // vendors and their POs together and execute them in dependency order.
        return _queue(Kind.AddPO, abi.encode(poId, vendorId, cap, expiry, periodDays));
    }

    function queueAddAgent(address agent) external onlyOwner returns (bytes32) {
        if (agent == address(0) || agent == address(this)) revert InvalidAddress();
        if (isAgent[agent]) revert AgentAlreadyActive();
        return _queue(Kind.AddAgent, abi.encode(agent));
    }

    function queueRaiseDailyCap(uint256 newCap) external onlyOwner returns (bytes32) {
        if (newCap <= dailyCap) revert InvalidValue();
        return _queue(Kind.RaiseDailyCap, abi.encode(newCap));
    }

    function queueUnpause() external onlyOwner returns (bytes32) {
        _requirePaused();
        return _queue(Kind.Unpause, "");
    }

    function queueWithdraw(uint256 amount) external onlyOwner returns (bytes32) {
        if (amount == 0) revert InvalidValue();
        return _queue(Kind.Withdraw, abi.encode(amount));
    }

    function _queue(Kind kind, bytes memory data) internal returns (bytes32 id) {
        uint256 eta = block.timestamp + delay;
        if (eta > type(uint64).max) revert InvalidValue();
        id = keccak256(abi.encode(kind, data, ++changeNonce));
        changes[id] = Change(kind, data, uint64(eta), false, false);
        changeIds.push(id);
        emit ChangeQueued(id, kind, data, uint64(eta));
    }

    function execute(bytes32 id) external nonReentrant {
        Change storage change = changes[id];
        _available(change);
        if (block.timestamp < change.eta) revert ChangeNotReady(change.eta);
        change.executed = true;
        Kind kind = change.kind;
        bytes memory data = change.data;
        if (kind == Kind.AddVendor) {
            (uint256 vendorId, address payout) = abi.decode(data, (uint256, address));
            if (vendors[vendorId].exists) revert VendorAlreadyExists();
            _validPayout(payout);
            vendors[vendorId] = Vendor(payout, true, true);
        } else if (kind == Kind.SetPayout) {
            (uint256 vendorId, address payout) = abi.decode(data, (uint256, address));
            if (!vendors[vendorId].exists) revert VendorNotFound();
            _validPayout(payout);
            vendors[vendorId].payout = payout;
            vendors[vendorId].active = true;
        } else if (kind == Kind.AddPO) {
            (uint256 poId, uint256 vendorId, uint256 cap, uint64 expiry, uint32 periodDays) =
                abi.decode(data, (uint256, uint256, uint256, uint64, uint32));
            if (!vendors[vendorId].exists) revert VendorNotFound();
            if (pos[poId].exists) revert POAlreadyExists();
            if (cap == 0 || expiry < block.timestamp) revert InvalidValue();
            pos[poId] = PO(vendorId, cap, 0, expiry, periodDays, uint64(block.timestamp), true, false);
        } else if (kind == Kind.AddAgent) {
            address agent = abi.decode(data, (address));
            if (isAgent[agent]) revert AgentAlreadyActive();
            isAgent[agent] = true;
        } else if (kind == Kind.RaiseDailyCap) {
            uint256 newCap = abi.decode(data, (uint256));
            if (newCap <= dailyCap) revert InvalidValue();
            dailyCap = newCap;
        } else if (kind == Kind.Unpause) {
            _unpause();
        } else {
            uint256 amount = abi.decode(data, (uint256));
            if (vaultBalance() < amount) revert InsufficientVaultFunds();
            // Resolve the owner at execution, never at queue time.
            address recipient = owner();
            if (recipient == address(0)) revert InvalidAddress();
            _transfer(recipient, amount);
        }
        emit ChangeExecuted(id, kind);
    }

    function cancel(bytes32 id) external onlyOwner {
        Change storage change = changes[id];
        _available(change);
        change.cancelled = true;
        emit ChangeCancelled(id);
    }

    function _available(Change storage change) internal view {
        if (change.eta == 0) revert ChangeNotFound();
        if (change.executed || change.cancelled) revert ChangeUnavailable();
    }

    function pause() external onlyOwner {
        _pause();
    }

    function deactivateVendor(uint256 vendorId) external onlyOwner {
        if (!vendors[vendorId].exists) revert VendorNotFound();
        vendors[vendorId].active = false;
        emit VendorDeactivated(vendorId);
    }

    function closePO(uint256 poId) external onlyOwner {
        if (!pos[poId].exists) revert PONotFound();
        pos[poId].closed = true;
        emit POClosed(poId);
    }

    function revokeAgent(address agent) external onlyOwner {
        isAgent[agent] = false;
        emit AgentRevoked(agent);
    }

    function lowerDailyCap(uint256 newCap) external onlyOwner {
        if (newCap >= dailyCap) revert InvalidValue();
        dailyCap = newCap;
        emit DailyCapLowered(newCap);
    }

    function pay(uint256 vendorId, address payTo, uint256 poId, uint256 amount, bytes32 invoiceHash)
        external
        nonReentrant
        returns (bool paid)
    {
        if (!isAgent[msg.sender]) revert NotAgent();
        uint64 today = uint64(block.timestamp / 1 days);
        if (today > currentDay) {
            currentDay = today;
            spentToday = 0;
        }
        PO storage po = pos[poId];
        _rollPeriod(po);
        Reason reason = _reason(vendorId, payTo, po, amount, invoiceHash);
        if (reason != Reason.None) {
            emit Blocked(vendorId, poId, msg.sender, reason, payTo, amount, invoiceHash);
            return false;
        }
        address recipient = vendors[vendorId].payout;
        po.spent += amount;
        spentToday += amount;
        invoicePaid[invoiceHash] = true;
        _transfer(recipient, amount);
        emit Paid(vendorId, poId, msg.sender, recipient, amount, invoiceHash);
        return true;
    }

    function _reason(uint256 vendorId, address payTo, PO storage po, uint256 amount, bytes32 invoiceHash)
        internal
        view
        returns (Reason)
    {
        if (paused()) return Reason.Paused;
        if (amount == 0) return Reason.ZeroAmount;
        Vendor storage vendor = vendors[vendorId];
        if (!vendor.exists) return Reason.UnknownVendor;
        if (!vendor.active) return Reason.VendorInactive;
        if (payTo != vendor.payout) return Reason.PayoutMismatch;
        if (!po.exists || po.closed) return Reason.UnknownPO;
        if (po.vendorId != vendorId) return Reason.POVendorMismatch;
        if (block.timestamp > po.expiry) return Reason.POExpired;
        // Subtraction avoids arithmetic reverts for malicious uint256 amounts.
        if (amount > po.cap || po.spent > po.cap - amount) return Reason.OverBudget;
        if (invoicePaid[invoiceHash]) return Reason.DuplicateInvoice;
        if (amount > dailyCap || spentToday > dailyCap - amount) return Reason.OverDailyCap;
        if (vaultBalance() < amount) return Reason.InsufficientFunds;
        return Reason.None;
    }

    function _rollPeriod(PO storage po) internal {
        if (!po.exists || po.periodDays == 0) return;
        uint256 period = uint256(po.periodDays) * 1 days;
        uint256 elapsed = block.timestamp - po.periodStart;
        if (elapsed >= period) {
            po.periodStart = uint64(uint256(po.periodStart) + (elapsed / period) * period);
            po.spent = 0;
        }
    }

    function _transfer(address recipient, uint256 amount) internal {
        if (address(token) == address(0)) {
            (bool success,) = payable(recipient).call{value: amount}("");
            if (!success) revert NativeTransferFailed();
        } else {
            token.safeTransfer(recipient, amount);
        }
    }

    function _validPayout(address payout) internal view {
        if (payout == address(0) || payout == address(this)) revert InvalidAddress();
    }

    function changeCount() external view returns (uint256) {
        return changeIds.length;
    }

    function getChange(bytes32 id) external view returns (Change memory) {
        return changes[id];
    }

    function poRemaining(uint256 poId) external view returns (uint256) {
        PO storage po = pos[poId];
        if (!po.exists || po.closed || block.timestamp > po.expiry) return 0;
        if (po.periodDays > 0 && block.timestamp - po.periodStart >= uint256(po.periodDays) * 1 days) {
            return po.cap;
        }
        return po.cap - po.spent;
    }

    function remainingToday() external view returns (uint256) {
        if (block.timestamp / 1 days > currentDay) return dailyCap;
        return spentToday >= dailyCap ? 0 : dailyCap - spentToday;
    }

    function vaultBalance() public view returns (uint256) {
        return address(token) == address(0) ? address(this).balance : token.balanceOf(address(this));
    }

    receive() external payable {}
}
