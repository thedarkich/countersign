// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {Countersign} from "../src/Countersign.sol";
import {FundTestnet, ProveTestnet} from "../script/TestnetProof.s.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract ProofToken is ERC20 {
    constructor(address owner) ERC20("Test token", "TEST") {
        _mint(owner, 1000 * 10 ** 6);
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }
}

contract TestnetProofHarness is Test {
    function rehearseNativeProofAndFunding() public {
        _rehearse(false);
    }

    function rehearseTokenProofAndFunding() public {
        _rehearse(true);
    }

    function _rehearse(bool erc20) internal {
        vm.chainId(968);
        address owner = vm.addr(101);
        address guarded = vm.addr(102);
        address naive = vm.addr(103);
        address payout = address(1001);
        address token = erc20 ? address(new ProofToken(owner)) : address(0);
        uint256 unit = erc20 ? 10 ** 6 : 1 ether;
        Countersign vault = new Countersign(owner, token, 1, 15 * unit);
        vm.startPrank(owner);
        bytes32 a = vault.queueAddVendor(1, payout);
        bytes32 b = vault.queueAddPO(1, 1, 10 * unit, uint64(block.timestamp + 86400), 0);
        bytes32 c = vault.queueAddAgent(guarded);
        bytes32 d = vault.queueAddAgent(naive);
        vm.stopPrank();
        vm.warp(block.timestamp + 1);
        vault.execute(a);
        vault.execute(b);
        vault.execute(c);
        vault.execute(d);
        vm.setEnv("NETWORK", "testnet");
        vm.setEnv("CONTRACT_ADDRESS_TESTNET", vm.toString(address(vault)));
        vm.setEnv("TESTNET_OWNER_PK", "101");
        vm.setEnv("AGENT_GUARDED_PK", "102");
        vm.setEnv("AGENT_NAIVE_PK", "103");
        vm.setEnv("AGENT_GUARDED_ADDRESS", vm.toString(guarded));
        vm.setEnv("AGENT_NAIVE_ADDRESS", vm.toString(naive));
        vm.setEnv("ATTACKER_ADDRESS", vm.toString(address(1002)));
        vm.setEnv("EVIDENCE_INVOICE_NUMBER", "SYNTHETICPROOF1");
        vm.deal(owner, 30 ether);
        new FundTestnet().run();
        new FundTestnet().run(); // A repeated funding request does not transfer twice.
        assertEq(vault.vaultBalance(), 20 * unit);
        new ProveTestnet().run();
        assertEq(vault.vaultBalance(), 20 * unit - unit / 10);
        assertEq(vault.poRemaining(1), 10 * unit - unit / 10);
        assertTrue(vault.invoicePaid(keccak256(abi.encode(uint256(1), "SYNTHETICPROOF1"))));
        if (erc20) assertEq(ERC20(token).balanceOf(address(1002)), 0);
        else assertEq(address(1002).balance, 0);
    }

    function assertMainnetRefused() public {
        vm.chainId(677);
        FundTestnet fund = new FundTestnet();
        ProveTestnet proof = new ProveTestnet();
        vm.expectRevert("testnet only");
        fund.run();
        vm.expectRevert("testnet only");
        proof.run();
    }
}
