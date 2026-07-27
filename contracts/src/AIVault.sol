// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract AIVault {
    address public authorizedAgent;
    address public owner;

    event TradeSignal(
        string ticker,
        string action,
        uint256 quantity,
        uint256 confidence,
        uint256 timestamp
    );

    constructor(address _authorizedAgent) {
        owner = msg.sender;
        authorizedAgent = _authorizedAgent;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    function setAuthorizedAgent(address _agent) external onlyOwner {
        authorizedAgent = _agent;
    }

    function executeTradeSignal(
        string calldata ticker,
        string calldata action,
        uint256 quantity,
        uint256 confidence,
        bytes calldata signature
    ) external {
        // Reconstruct the message hash
        bytes32 messageHash = keccak256(
            abi.encodePacked(ticker, action, quantity, confidence)
        );

        bytes32 ethSignedHash = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash)
        );

        // Recover signer
        address signer = recoverSigner(ethSignedHash, signature);
        require(signer == authorizedAgent, "Invalid signature");

        emit TradeSignal(ticker, action, quantity, confidence, block.timestamp);
    }

    function recoverSigner(
        bytes32 hash,
        bytes memory signature
    ) internal pure returns (address) {
        require(signature.length == 65, "Invalid signature length");

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }

        return ecrecover(hash, v, r, s);
    }
}
