// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {AIVault} from "../src/AIVault.sol";
import {DeployAIVault} from "../script/DeployAIVault.s.sol";

contract AIVaultTest is Test {
    // Mirror the event so vm.expectEmit can match it
    event TradeSignal(
        string ticker,
        string action,
        uint256 quantity,
        uint256 confidence,
        uint256 timestamp
    );

    AIVault vault;

    uint256 constant AGENT_PRIVATE_KEY = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;
    address agent;
    address owner;
    address stranger = makeAddr("stranger");

    // ── helpers ──────────────────────────────────────────────────────────────

    function _sign(
        string memory ticker,
        string memory action,
        uint256 quantity,
        uint256 confidence
    ) internal view returns (bytes memory) {
        bytes32 msgHash = keccak256(
            abi.encodePacked(ticker, action, quantity, confidence)
        );
        bytes32 ethSignedHash = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", msgHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(
            AGENT_PRIVATE_KEY,
            ethSignedHash
        );
        return abi.encodePacked(r, s, v);
    }

    // ── setup ─────────────────────────────────────────────────────────────────

    function setUp() public {
        agent = vm.addr(AGENT_PRIVATE_KEY);
        owner = address(this);
        vault = new AIVault(agent);
    }

    // ── constructor ───────────────────────────────────────────────────────────

    function test_Constructor_SetsOwnerAndAgent() public view {
        assertEq(vault.owner(), owner);
        assertEq(vault.authorizedAgent(), agent);
    }

    // ── setAuthorizedAgent ────────────────────────────────────────────────────

    function test_SetAuthorizedAgent_OwnerCanUpdate() public {
        address newAgent = makeAddr("newAgent");
        vault.setAuthorizedAgent(newAgent);
        assertEq(vault.authorizedAgent(), newAgent);
    }

    function test_SetAuthorizedAgent_RevertsForNonOwner() public {
        vm.prank(stranger);
        vm.expectRevert("Not owner");
        vault.setAuthorizedAgent(stranger);
    }

    // ── executeTradeSignal ────────────────────────────────────────────────────

    function test_ExecuteTradeSignal_BuyEmitsEvent() public {
        string memory ticker = "AAPL";
        string memory action = "buy";
        uint256 quantity = 10;
        uint256 confidence = 85;

        bytes memory sig = _sign(ticker, action, quantity, confidence);

        vm.expectEmit(false, false, false, true);
        emit TradeSignal(ticker, action, quantity, confidence, block.timestamp);

        vault.executeTradeSignal(ticker, action, quantity, confidence, sig);
    }

    function test_ExecuteTradeSignal_SellEmitsEvent() public {
        string memory ticker = "TSLA";
        string memory action = "sell";
        uint256 quantity = 5;
        uint256 confidence = 72;

        bytes memory sig = _sign(ticker, action, quantity, confidence);

        vm.expectEmit(false, false, false, true);
        emit TradeSignal(ticker, action, quantity, confidence, block.timestamp);

        vault.executeTradeSignal(ticker, action, quantity, confidence, sig);
    }

    function test_ExecuteTradeSignal_RevertsOnWrongSigner() public {
        bytes memory sig = _sign("AAPL", "buy", 10, 85);

        // Replace authorized agent with a different address
        vault.setAuthorizedAgent(stranger);

        vm.expectRevert("Invalid signature");
        vault.executeTradeSignal("AAPL", "buy", 10, 85, sig);
    }

    function test_ExecuteTradeSignal_RevertsOnTamperedPayload() public {
        bytes memory sig = _sign("AAPL", "buy", 10, 85);

        // quantity differs from what was signed
        vm.expectRevert("Invalid signature");
        vault.executeTradeSignal("AAPL", "buy", 999, 85, sig);
    }

    function test_ExecuteTradeSignal_RevertsOnInvalidSigLength() public {
        bytes memory badSig = new bytes(64); // should be 65

        vm.expectRevert("Invalid signature length");
        vault.executeTradeSignal("AAPL", "buy", 10, 85, badSig);
    }

    // ── fuzz ─────────────────────────────────────────────────────────────────

    function testFuzz_ExecuteTradeSignal_ValidSig(
        string calldata ticker,
        uint256 quantity,
        uint256 confidence
    ) public {
        // Use "buy" as fixed action — payload hash covers all fields
        string memory action = "buy";
        bytes memory sig = _sign(ticker, action, quantity, confidence);

        vm.expectEmit(false, false, false, false);
        emit TradeSignal(ticker, action, quantity, confidence, block.timestamp);

        vault.executeTradeSignal(ticker, action, quantity, confidence, sig);
    }
}
