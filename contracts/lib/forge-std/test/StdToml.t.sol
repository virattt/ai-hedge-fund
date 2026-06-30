// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {Test, stdToml} from "../src/Test.sol";

contract StdTomlTest is Test {
    using stdToml for string;

    string root;
    string path;

    function setUp() public {
        root = vm.projectRoot();
        path = string.concat(root, "/test/fixtures/test.toml");
    }

    struct SimpleToml {
        uint256 a;
        string b;
    }

    struct NestedToml {
        uint256 a;
        string b;
        SimpleToml c;
    }

    function test_readToml() public view {
        string memory json = vm.readFile(path);
        assertEq(json.readUint(".a"), 123);
    }

    function test_writeToml() public {
        string memory json = "json";
        json.serialize("a", uint256(123));
        string memory semiFinal = json.serialize("b", string("test"));
        string memory finalJson = json.serialize("c", semiFinal);
        finalJson.write(path);

        string memory toml = vm.readFile(path);
        bytes memory data = toml.parseRaw("$");
        NestedToml memory decodedData = abi.decode(data, (NestedToml));

        assertEq(decodedData.a, 123);
        assertEq(decodedData.b, "test");
        assertEq(decodedData.c.a, 123);
        assertEq(decodedData.c.b, "test");
    }
}
