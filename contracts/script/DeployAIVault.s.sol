// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {AIVault} from "../src/AIVault.sol";
import {HelperConfig} from "./HelperConfig.s.sol";

contract DeployAIVault is Script {
    function run() external returns (AIVault vault, HelperConfig helperConfig) {
        helperConfig = new HelperConfig();
        HelperConfig.NetworkConfig memory config = helperConfig
            .activeNetworkConfig();

        console.log("Deploying AIVault on chain:", block.chainid);
        console.log("Authorized agent:", config.authorizedAgent);

        vm.startBroadcast();
        vault = new AIVault(config.authorizedAgent);
        vm.stopBroadcast();

        console.log("AIVault deployed at:", address(vault));
    }
}
