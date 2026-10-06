// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;
import {TestnetProofHarness} from "./TestnetProof.t.sol";
import {Test} from "forge-std/Test.sol";
import {Deploy} from "../script/Deploy.s.sol";
import {Setup} from "../script/Setup.s.sol";
import {Execute} from "../script/Execute.s.sol";
import {Countersign} from "../src/Countersign.sol";

contract ScriptsTest is Test {
    function testLocalDeploySetupExecuteFlow() public {
        vm.chainId(968);
        vm.warp(1_791_000_000);
        // Ephemeral test-only identities; no project wallet credentials loaded.
        vm.setEnv("NETWORK", "testnet");
        vm.setEnv("DEPLOYER_PK", "123456");
        vm.setEnv("TESTNET_OWNER_PK", "654321");
        vm.setEnv("PAY_TOKEN_TESTNET", vm.toString(address(0)));
        vm.setEnv("TIMELOCK_DELAY_SECONDS", "120");
        vm.setEnv("INITIAL_DAILY_CAP", "15000000000000000000");
        for (uint256 i = 1; i <= 3; i++) {
            vm.setEnv(
                string.concat("VENDOR", vm.toString(i), "_PAYOUT"), vm.toString(address(uint160(1000 + i)))
            );
        }
        address guarded = makeAddr("script-guarded");
        address naive = makeAddr("script-naive");
        vm.setEnv("AGENT_GUARDED_ADDRESS", vm.toString(guarded));
        vm.setEnv("AGENT_NAIVE_ADDRESS", vm.toString(naive));
        Countersign vault = new Deploy().run();
        vm.setEnv("CONTRACT_ADDRESS_TESTNET", vm.toString(address(vault)));
        assertEq(vault.owner(), vm.addr(654321));
        new Setup().run();
        assertEq(vault.changeCount(), 8);
        assertFalse(vault.isAgent(guarded));
        vm.warp(block.timestamp + 120);
        new Execute().run();
        assertTrue(vault.isAgent(guarded));
        assertTrue(vault.isAgent(naive));
        assertEq(vault.poRemaining(1), 10 ether);
        assertEq(vault.poRemaining(2), 5 ether);
        assertEq(vault.poRemaining(3), 3 ether);
        vm.deal(address(vault), 1 ether);
        vm.prank(guarded);
        assertTrue(vault.pay(1, address(1001), 1, 0.1 ether, keccak256("script-invoice")));
        // vm.setEnv is process-wide: all script cases that change wallet/vault
        // values run within one test to avoid parallel environment races.
        TestnetProofHarness proof = new TestnetProofHarness();
        proof.rehearseNativeProofAndFunding();
        proof.rehearseTokenProofAndFunding();
        proof.assertMainnetRefused();
    }

    function testWrongRPCChainFailsBeforeDeployment() public {
        vm.chainId(1);
        vm.setEnv("NETWORK", "testnet");
        Deploy deploy = new Deploy();
        vm.expectRevert("RPC chain does not match NETWORK");
        deploy.run();
    }
}
