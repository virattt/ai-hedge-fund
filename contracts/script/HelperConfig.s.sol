// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";

contract HelperConfig is Script {
    uint256 public constant BASE_MAINNET_CHAIN_ID = 8453;
    uint256 public constant BASE_SEPOLIA_CHAIN_ID = 84532;
    uint256 public constant ANVIL_CHAIN_ID = 31337;

    // Default Anvil funded account #0 used as placeholder agent in local tests
    address public constant ANVIL_DEFAULT_AGENT =
        0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266;

    struct NetworkConfig {
        address authorizedAgent;
    }

    NetworkConfig private _activeNetworkConfig;

    constructor() {
        if (block.chainid == BASE_MAINNET_CHAIN_ID) {
            _activeNetworkConfig = getBaseMainnetConfig();
        } else if (block.chainid == BASE_SEPOLIA_CHAIN_ID) {
            _activeNetworkConfig = getBaseSepoliaConfig();
        } else {
            _activeNetworkConfig = getAnvilConfig();
        }
    }

    function activeNetworkConfig() external view returns (NetworkConfig memory) {
        return _activeNetworkConfig;
    }

    /// @notice Returns config for Base Mainnet.
    ///         Set AUTHORIZED_AGENT in your .env before deploying to mainnet.
    function getBaseMainnetConfig() public view returns (NetworkConfig memory) {
        return NetworkConfig({
            authorizedAgent: vm.envAddress("AUTHORIZED_AGENT")
        });
    }

    /// @notice Returns config for Base Sepolia testnet.
    ///         Set AUTHORIZED_AGENT in your .env before deploying to testnet.
    function getBaseSepoliaConfig() public view returns (NetworkConfig memory) {
        return NetworkConfig({
            authorizedAgent: vm.envAddress("AUTHORIZED_AGENT")
        });
    }

    /// @notice Returns config for local Anvil fork — uses default funded account.
    function getAnvilConfig() public pure returns (NetworkConfig memory) {
        return NetworkConfig({authorizedAgent: ANVIL_DEFAULT_AGENT});
    }
}
