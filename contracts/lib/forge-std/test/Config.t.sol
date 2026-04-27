// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity ^0.8.13;

import {Test} from "../src/Test.sol";
import {Config} from "../src/Config.sol";
import {StdConfig} from "../src/StdConfig.sol";

contract ConfigTest is Test, Config {
    function setUp() public {
        vm.setEnv("MAINNET_RPC", "https://ethereum.reth.rs/rpc");
        vm.setEnv("WETH_MAINNET", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2");
        vm.setEnv("OPTIMISM_RPC", "https://mainnet.optimism.io");
        vm.setEnv("WETH_OPTIMISM", "0x4200000000000000000000000000000000000006");
    }

    function test_loadConfig() public {
        // Deploy the config contract with the test fixture.
        _loadConfig("./test/fixtures/config.toml", false);

        // -- MAINNET --------------------------------------------------------------

        // Read and assert RPC URL for Mainnet (chain ID 1)
        assertEq(config.getRpcUrl(1), "https://ethereum.reth.rs/rpc");

        // Read and assert boolean values
        assertTrue(config.get(1, "is_live").toBool());
        bool[] memory bool_array = config.get(1, "bool_array").toBoolArray();
        assertTrue(bool_array[0]);
        assertFalse(bool_array[1]);

        // Read and assert address values
        assertEq(config.get(1, "weth").toAddress(), 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
        address[] memory address_array = config.get(1, "deps").toAddressArray();
        assertEq(address_array[0], 0x0000000000000000000000000000000000000000);
        assertEq(address_array[1], 0x1111111111111111111111111111111111111111);

        // Read and assert bytes32 values
        assertEq(config.get(1, "word").toBytes32(), bytes32(uint256(1234)));
        bytes32[] memory bytes32_array = config.get(1, "word_array").toBytes32Array();
        assertEq(bytes32_array[0], bytes32(uint256(5678)));
        assertEq(bytes32_array[1], bytes32(uint256(9999)));

        // Read and assert uint values
        assertEq(config.get(1, "number").toUint256(), 1234);
        uint256[] memory uint_array = config.get(1, "number_array").toUint256Array();
        assertEq(uint_array[0], 5678);
        assertEq(uint_array[1], 9999);

        // Read and assert int values
        assertEq(config.get(1, "signed_number").toInt256(), -1234);
        int256[] memory int_array = config.get(1, "signed_number_array").toInt256Array();
        assertEq(int_array[0], -5678);
        assertEq(int_array[1], 9999);

        // Read and assert bytes values
        assertEq(config.get(1, "b").toBytes(), hex"abcd");
        bytes[] memory bytes_array = config.get(1, "b_array").toBytesArray();
        assertEq(bytes_array[0], hex"dead");
        assertEq(bytes_array[1], hex"beef");

        // Read and assert string values
        assertEq(config.get(1, "str").toString(), "foo");
        string[] memory string_array = config.get(1, "str_array").toStringArray();
        assertEq(string_array[0], "bar");
        assertEq(string_array[1], "baz");

        // -- OPTIMISM ------------------------------------------------------------

        // Read and assert RPC URL for Optimism (chain ID 10)
        assertEq(config.getRpcUrl(10), "https://mainnet.optimism.io");

        // Read and assert boolean values
        assertFalse(config.get(10, "is_live").toBool());
        bool_array = config.get(10, "bool_array").toBoolArray();
        assertFalse(bool_array[0]);
        assertTrue(bool_array[1]);

        // Read and assert address values
        assertEq(config.get(10, "weth").toAddress(), 0x4200000000000000000000000000000000000006);
        address_array = config.get(10, "deps").toAddressArray();
        assertEq(address_array[0], 0x2222222222222222222222222222222222222222);
        assertEq(address_array[1], 0x3333333333333333333333333333333333333333);

        // Read and assert bytes32 values
        assertEq(config.get(10, "word").toBytes32(), bytes32(uint256(9999)));
        bytes32_array = config.get(10, "word_array").toBytes32Array();
        assertEq(bytes32_array[0], bytes32(uint256(1234)));
        assertEq(bytes32_array[1], bytes32(uint256(5678)));

        // Read and assert uint values
        assertEq(config.get(10, "number").toUint256(), 9999);
        uint_array = config.get(10, "number_array").toUint256Array();
        assertEq(uint_array[0], 1234);
        assertEq(uint_array[1], 5678);

        // Read and assert int values
        assertEq(config.get(10, "signed_number").toInt256(), 9999);
        int_array = config.get(10, "signed_number_array").toInt256Array();
        assertEq(int_array[0], -1234);
        assertEq(int_array[1], -5678);

        // Read and assert bytes values
        assertEq(config.get(10, "b").toBytes(), hex"dcba");
        bytes_array = config.get(10, "b_array").toBytesArray();
        assertEq(bytes_array[0], hex"c0ffee");
        assertEq(bytes_array[1], hex"babe");

        // Read and assert string values
        assertEq(config.get(10, "str").toString(), "alice");
        string_array = config.get(10, "str_array").toStringArray();
        assertEq(string_array[0], "bob");
        assertEq(string_array[1], "charlie");
    }

    function test_loadConfigAndForks() public {
        _loadConfigAndForks("./test/fixtures/config.toml", false);

        // assert that the map of chain id and fork ids is created and that the chain ids actually match
        assertEq(forkOf[1], 0);
        vm.selectFork(forkOf[1]);
        assertEq(vm.getChainId(), 1);

        assertEq(forkOf[10], 1);
        vm.selectFork(forkOf[10]);
        assertEq(vm.getChainId(), 10);
    }

    function test_configExists() public {
        _loadConfig("./test/fixtures/config.toml", false);

        string[] memory keys = new string[](7);
        keys[0] = "is_live";
        keys[1] = "weth";
        keys[2] = "word";
        keys[3] = "number";
        keys[4] = "signed_number";
        keys[5] = "b";
        keys[6] = "str";

        // Read and assert RPC URL for Mainnet (chain ID 1)
        assertEq(config.getRpcUrl(1), "https://ethereum.reth.rs/rpc");

        for (uint256 i = 0; i < keys.length; ++i) {
            assertTrue(config.exists(1, keys[i]));
            assertFalse(config.exists(1, string.concat(keys[i], "_")));
        }

        // Assert RPC URL for Optimism (chain ID 10)
        assertEq(config.getRpcUrl(10), "https://mainnet.optimism.io");

        for (uint256 i = 0; i < keys.length; ++i) {
            assertTrue(config.exists(10, keys[i]));
            assertFalse(config.exists(10, string.concat(keys[i], "_")));
        }
    }

    function test_writeConfig() public {
        // Create a temporary copy of the config file to avoid modifying the original.
        string memory originalConfig = "./test/fixtures/config.toml";
        string memory testConfig = "./test/fixtures/config.t.toml";
        vm.copyFile(originalConfig, testConfig);

        // Deploy the config contract with the temporary fixture.
        _loadConfig(testConfig, false);

        // Enable writing to file bypassing the context check.
        vm.store(address(config), bytes32(uint256(5)), bytes32(uint256(1)));

        {
            // Update a single boolean value and verify the change.
            config.set(1, "is_live", false);

            assertFalse(config.get(1, "is_live").toBool());

            string memory content = vm.readFile(testConfig);
            assertFalse(vm.parseTomlBool(content, "$.mainnet.bool.is_live"));

            // Update a single address value and verify the change.
            address new_addr = 0xDeaDbeefdEAdbeefdEadbEEFdeadbeEFdEaDbeeF;
            config.set(1, "weth", new_addr);

            assertEq(config.get(1, "weth").toAddress(), new_addr);

            content = vm.readFile(testConfig);
            assertEq(vm.parseTomlAddress(content, "$.mainnet.address.weth"), new_addr);

            // Update a uint array and verify the change.
            uint256[] memory new_numbers = new uint256[](3);
            new_numbers[0] = 1;
            new_numbers[1] = 2;
            new_numbers[2] = 3;
            config.set(10, "number_array", new_numbers);

            uint256[] memory updated_numbers_mem = config.get(10, "number_array").toUint256Array();
            assertEq(updated_numbers_mem.length, 3);
            assertEq(updated_numbers_mem[0], 1);
            assertEq(updated_numbers_mem[1], 2);
            assertEq(updated_numbers_mem[2], 3);

            content = vm.readFile(testConfig);
            uint256[] memory updated_numbers_disk = vm.parseTomlUintArray(content, "$.optimism.uint.number_array");
            assertEq(updated_numbers_disk.length, 3);
            assertEq(updated_numbers_disk[0], 1);
            assertEq(updated_numbers_disk[1], 2);
            assertEq(updated_numbers_disk[2], 3);

            // Update a string array and verify the change.
            string[] memory new_strings = new string[](2);
            new_strings[0] = "hello";
            new_strings[1] = "world";
            config.set(1, "str_array", new_strings);

            string[] memory updated_strings_mem = config.get(1, "str_array").toStringArray();
            assertEq(updated_strings_mem.length, 2);
            assertEq(updated_strings_mem[0], "hello");
            assertEq(updated_strings_mem[1], "world");

            content = vm.readFile(testConfig);
            string[] memory updated_strings_disk = vm.parseTomlStringArray(content, "$.mainnet.string.str_array");
            assertEq(updated_strings_disk.length, 2);
            assertEq(updated_strings_disk[0], "hello");
            assertEq(updated_strings_disk[1], "world");

            // Create a new uint variable and verify the change.
            config.set(1, "new_uint", uint256(42));

            assertEq(config.get(1, "new_uint").toUint256(), 42);

            content = vm.readFile(testConfig);
            assertEq(vm.parseTomlUint(content, "$.mainnet.uint.new_uint"), 42);

            // Create a new int variable and verify the change.
            config.set(1, "new_int", int256(-42));

            assertEq(config.get(1, "new_int").toInt256(), -42);

            content = vm.readFile(testConfig);
            assertEq(vm.parseTomlInt(content, "$.mainnet.int.new_int"), -42);

            // Create a new int array and verify the change.
            int256[] memory new_ints = new int256[](2);
            new_ints[0] = -100;
            new_ints[1] = 200;
            config.set(10, "new_ints", new_ints);

            int256[] memory updated_ints_mem = config.get(10, "new_ints").toInt256Array();
            assertEq(updated_ints_mem.length, 2);
            assertEq(updated_ints_mem[0], -100);
            assertEq(updated_ints_mem[1], 200);

            content = vm.readFile(testConfig);
            int256[] memory updated_ints_disk = vm.parseTomlIntArray(content, "$.optimism.int.new_ints");
            assertEq(updated_ints_disk.length, 2);
            assertEq(updated_ints_disk[0], -100);
            assertEq(updated_ints_disk[1], 200);

            // Create a new bytes32 array and verify the change.
            bytes32[] memory new_words = new bytes32[](2);
            new_words[0] = bytes32(uint256(0xDEAD));
            new_words[1] = bytes32(uint256(0xBEEF));
            config.set(10, "new_words", new_words);

            bytes32[] memory updated_words_mem = config.get(10, "new_words").toBytes32Array();
            assertEq(updated_words_mem.length, 2);
            assertEq(updated_words_mem[0], new_words[0]);
            assertEq(updated_words_mem[1], new_words[1]);

            content = vm.readFile(testConfig);
            bytes32[] memory updated_words_disk = vm.parseTomlBytes32Array(content, "$.optimism.bytes32.new_words");
            assertEq(updated_words_disk.length, 2);
            assertEq(vm.toString(updated_words_disk[0]), vm.toString(new_words[0]));
            assertEq(vm.toString(updated_words_disk[1]), vm.toString(new_words[1]));
        }

        // Clean up the temporary file.
        vm.removeFile(testConfig);
    }

    function test_writeUpdatesBackToFile() public {
        // Create a temporary copy of the config file to avoid modifying the original.
        string memory originalConfig = "./test/fixtures/config.toml";
        string memory testConfig = "./test/fixtures/write_config.t.toml";
        vm.copyFile(originalConfig, testConfig);

        // Deploy the config contract with `writeToFile = false` (disabled).
        _loadConfig(testConfig, false);

        // Update a single boolean value and verify the file is NOT changed.
        config.set(1, "is_live", false);
        string memory content = vm.readFile(testConfig);
        assertTrue(vm.parseTomlBool(content, "$.mainnet.bool.is_live"), "File should not be updated yet");

        // Enable writing to file bypassing the context check.
        vm.store(address(config), bytes32(uint256(5)), bytes32(uint256(1)));

        // Update the value again and verify the file IS changed.
        config.set(1, "is_live", false);
        content = vm.readFile(testConfig);
        assertFalse(vm.parseTomlBool(content, "$.mainnet.bool.is_live"), "File should be updated now");

        // Disable writing to file.
        config.writeUpdatesBackToFile(false);

        // Update the value again and verify the file is NOT changed.
        config.set(1, "is_live", true);
        content = vm.readFile(testConfig);
        assertFalse(vm.parseTomlBool(content, "$.mainnet.bool.is_live"), "File should not be updated again");

        // Clean up the temporary file.
        vm.removeFile(testConfig);
    }

    function testRevert_WriteToFileInForbiddenCtxt() public {
        // Cannot initialize enabling writing to file unless we are in SCRIPT mode.
        vm.expectRevert(StdConfig.WriteToFileInForbiddenCtxt.selector);
        _loadConfig("./test/fixtures/config.toml", true);

        // Initialize with `writeToFile = false`.
        _loadConfig("./test/fixtures/config.toml", false);

        // Cannot enable writing to file unless we are in SCRIPT mode.
        vm.expectRevert(StdConfig.WriteToFileInForbiddenCtxt.selector);
        config.writeUpdatesBackToFile(true);
    }

    function testRevert_InvalidChainKey() public {
        // Create a fixture with an invalid chain key
        string memory invalidChainConfig = "./test/fixtures/config_invalid_chain.toml";
        vm.writeFile(
            invalidChainConfig,
            string.concat(
                "[mainnet]\n",
                "endpoint_url = \"https://ethereum.reth.rs/rpc\"\n",
                "\n",
                "[mainnet.uint]\n",
                "valid_number = 123\n",
                "\n",
                "# Invalid chain key (not a number and not a valid alias)\n",
                "[invalid_chain]\n",
                "endpoint_url = \"https://invalid.com\"\n",
                "\n",
                "[invalid_chain_9999.uint]\n",
                "some_value = 456\n"
            )
        );

        vm.expectRevert(abi.encodeWithSelector(StdConfig.InvalidChainKey.selector, "invalid_chain"));
        new StdConfig(invalidChainConfig, false);
        vm.removeFile(invalidChainConfig);
    }

    function testRevert_ChainNotInitialized() public {
        _loadConfig("./test/fixtures/config.toml", false);

        // Enable writing to file bypassing the context check.
        vm.store(address(config), bytes32(uint256(5)), bytes32(uint256(1)));

        // Try to write a value for a non-existent chain ID
        vm.expectRevert(abi.encodeWithSelector(StdConfig.ChainNotInitialized.selector, uint256(999999)));
        config.set(999999, "some_key", uint256(123));
    }

    function testRevert_UnableToParseVariable() public {
        // Create a temporary fixture with an unparsable variable
        string memory badParseConfig = "./test/fixtures/config_bad_parse.toml";
        vm.writeFile(
            badParseConfig,
            string.concat(
                "[mainnet]\n",
                "endpoint_url = \"https://ethereum.reth.rs/rpc\"\n",
                "\n",
                "[mainnet.uint]\n",
                "bad_value = \"not_a_number\"\n"
            )
        );

        vm.expectRevert(abi.encodeWithSelector(StdConfig.UnableToParseVariable.selector, "bad_value"));
        new StdConfig(badParseConfig, false);
        vm.removeFile(badParseConfig);
    }
}
