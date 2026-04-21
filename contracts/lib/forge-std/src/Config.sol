// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity ^0.8.13;

import {console} from "./console.sol";
import {StdConfig} from "./StdConfig.sol";
import {CommonBase} from "./Base.sol";

/// @notice Boilerplate to streamline the setup of multi-chain environments.
abstract contract Config is CommonBase {
    // -- STORAGE (CONFIG + CHAINS + FORKS) ------------------------------------

    /// @dev Contract instance holding the data from the TOML config file.
    StdConfig internal config;

    /// @dev Array of chain IDs for which forks have been created.
    uint256[] internal chainIds;

    /// @dev A mapping from a chain ID to its initialized fork ID.
    mapping(uint256 => uint256) internal forkOf;

    // -- HELPER FUNCTIONS -----------------------------------------------------

    /// @notice  Loads configuration from a file.
    ///
    /// @dev     This function instantiates a `Config` contract, caching all its config variables.
    ///
    /// @param   filePath: the path to the TOML configuration file.
    /// @param   writeToFile: whether updates are written back to the TOML file.
    function _loadConfig(string memory filePath, bool writeToFile) internal {
        console.log("----------");
        console.log(string.concat("Loading config from '", filePath, "'"));
        config = new StdConfig(filePath, writeToFile);
        vm.makePersistent(address(config));
        console.log("Config successfully loaded");
        console.log("----------");
    }

    /// @notice  Loads configuration from a file and creates forks for each specified chain.
    ///
    /// @dev     This function instantiates a `Config` contract, caching all its config variables,
    ///          reads the configured chain ids, and iterates through them to create a fork for each one.
    ///          It also creates a map `forkOf[chainId] -> forkId` to easily switch between forks.
    ///
    /// @param   filePath: the path to the TOML configuration file.
    /// @param   writeToFile: whether updates are written back to the TOML file.
    function _loadConfigAndForks(string memory filePath, bool writeToFile) internal {
        _loadConfig(filePath, writeToFile);

        console.log("Setting up forks for the configured chains...");
        uint256[] memory chains = config.getChainIds();
        for (uint256 i = 0; i < chains.length; i++) {
            uint256 chainId = chains[i];
            uint256 forkId = vm.createFork(config.getRpcUrl(chainId));
            forkOf[chainId] = forkId;
            chainIds.push(chainId);
        }
        console.log("Forks successfully created");
        console.log("----------");
    }
}
