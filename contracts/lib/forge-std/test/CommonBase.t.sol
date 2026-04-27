// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {CommonBase} from "../src/Base.sol";
import {StdConstants} from "../src/StdConstants.sol";
import {Test} from "../src/Test.sol";

contract CommonBaseTest is Test {
    function testVmAddressValue() public pure {
        assertEq(VM_ADDRESS, address(StdConstants.VM));
    }

    function testConsoleValue() public pure {
        assertEq(CONSOLE, StdConstants.CONSOLE);
    }

    function testCreate2FactoryValue() public pure {
        assertEq(CREATE2_FACTORY, StdConstants.CREATE2_FACTORY);
    }

    function testDefaultSenderValue() public pure {
        assertEq(DEFAULT_SENDER, StdConstants.DEFAULT_SENDER);
    }

    function testDefaultTestContractValue() public pure {
        assertEq(DEFAULT_TEST_CONTRACT, StdConstants.DEFAULT_TEST_CONTRACT);
    }

    function testMulticall3AddressValue() public pure {
        assertEq(MULTICALL3_ADDRESS, address(StdConstants.MULTICALL3_ADDRESS));
    }

    function testSecp256k1OrderValue() public pure {
        assertEq(SECP256K1_ORDER, StdConstants.SECP256K1_ORDER);
    }

    function testUint256MaxValue() public pure {
        assertEq(UINT256_MAX, type(uint256).max);
    }

    function testVmValue() public pure {
        assertEq(address(vm), address(StdConstants.VM));
    }
}
