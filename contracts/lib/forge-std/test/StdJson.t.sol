// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {Test, stdJson} from "../src/Test.sol";

contract StdJsonTest is Test {
    using stdJson for string;

    string root;
    string path;

    function setUp() public {
        root = vm.projectRoot();
        path = string.concat(root, "/test/fixtures/test.json");
    }

    struct SimpleJson {
        uint256 a;
        string b;
    }

    struct NestedJson {
        uint256 a;
        string b;
        SimpleJson c;
    }

    function test_readJson() public view {
        string memory json = vm.readFile(path);
        assertEq(json.readUint(".a"), 123);
    }

    function test_writeJson() public {
        string memory json = "json";
        json.serialize("a", uint256(123));
        string memory semiFinal = json.serialize("b", string("test"));
        string memory finalJson = json.serialize("c", semiFinal);
        finalJson.write(path);

        string memory json_ = vm.readFile(path);
        bytes memory data = json_.parseRaw("$");
        NestedJson memory decodedData = abi.decode(data, (NestedJson));

        assertEq(decodedData.a, 123);
        assertEq(decodedData.b, "test");
        assertEq(decodedData.c.a, 123);
        assertEq(decodedData.c.b, "test");
    }
}
