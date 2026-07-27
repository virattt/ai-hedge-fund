// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {StdAssertions} from "../src/StdAssertions.sol";
import {Vm} from "../src/Vm.sol";

interface VmInternal is Vm {
    function _expectCheatcodeRevert(bytes memory message) external;
}

contract StdAssertionsTest is StdAssertions {
    string constant errorMessage = "User provided message";
    uint256 constant maxDecimals = 77;

    bool constant SHOULD_REVERT = true;
    bool constant SHOULD_RETURN = false;

    bool constant STRICT_REVERT_DATA = true;
    bool constant NON_STRICT_REVERT_DATA = false;

    VmInternal constant vm = VmInternal(address(uint160(uint256(keccak256("hevm cheat code")))));

    function testFuzz_AssertEqCall_Return_Pass(
        bytes memory callDataA,
        bytes memory callDataB,
        bytes memory returnData,
        bool strictRevertData
    ) external {
        address targetA = address(new TestMockCall(returnData, SHOULD_RETURN));
        address targetB = address(new TestMockCall(returnData, SHOULD_RETURN));

        assertEqCall(targetA, callDataA, targetB, callDataB, strictRevertData);
    }

    function testFuzz_RevertWhenCalled_AssertEqCall_Return_Fail(
        bytes memory callDataA,
        bytes memory callDataB,
        bytes memory returnDataA,
        bytes memory returnDataB,
        bool strictRevertData
    ) external {
        vm.assume(keccak256(returnDataA) != keccak256(returnDataB));

        address targetA = address(new TestMockCall(returnDataA, SHOULD_RETURN));
        address targetB = address(new TestMockCall(returnDataB, SHOULD_RETURN));

        vm._expectCheatcodeRevert(
            bytes(
                string.concat(
                    "Call return data does not match: ", vm.toString(returnDataA), " != ", vm.toString(returnDataB)
                )
            )
        );
        assertEqCall(targetA, callDataA, targetB, callDataB, strictRevertData);
    }

    function testFuzz_AssertEqCall_Revert_Pass(
        bytes memory callDataA,
        bytes memory callDataB,
        bytes memory revertDataA,
        bytes memory revertDataB
    ) external {
        address targetA = address(new TestMockCall(revertDataA, SHOULD_REVERT));
        address targetB = address(new TestMockCall(revertDataB, SHOULD_REVERT));

        assertEqCall(targetA, callDataA, targetB, callDataB, NON_STRICT_REVERT_DATA);
    }

    function testFuzz_RevertWhenCalled_AssertEqCall_Revert_Fail(
        bytes memory callDataA,
        bytes memory callDataB,
        bytes memory revertDataA,
        bytes memory revertDataB
    ) external {
        vm.assume(keccak256(revertDataA) != keccak256(revertDataB));

        address targetA = address(new TestMockCall(revertDataA, SHOULD_REVERT));
        address targetB = address(new TestMockCall(revertDataB, SHOULD_REVERT));

        vm._expectCheatcodeRevert(
            bytes(
                string.concat(
                    "Call revert data does not match: ", vm.toString(revertDataA), " != ", vm.toString(revertDataB)
                )
            )
        );
        assertEqCall(targetA, callDataA, targetB, callDataB, STRICT_REVERT_DATA);
    }

    function testFuzz_RevertWhenCalled_AssertEqCall_Fail(
        bytes memory callDataA,
        bytes memory callDataB,
        bytes memory returnDataA,
        bytes memory returnDataB,
        bool strictRevertData
    ) external {
        address targetA = address(new TestMockCall(returnDataA, SHOULD_RETURN));
        address targetB = address(new TestMockCall(returnDataB, SHOULD_REVERT));

        vm.expectRevert(bytes("assertion failed"));
        this.assertEqCallExternal(targetA, callDataA, targetB, callDataB, strictRevertData);

        vm.expectRevert(bytes("assertion failed"));
        this.assertEqCallExternal(targetB, callDataB, targetA, callDataA, strictRevertData);
    }

    // Helper function to test outcome of assertEqCall via `expect` cheatcodes
    function assertEqCallExternal(
        address targetA,
        bytes memory callDataA,
        address targetB,
        bytes memory callDataB,
        bool strictRevertData
    ) public {
        assertEqCall(targetA, callDataA, targetB, callDataB, strictRevertData);
    }
}

contract TestMockCall {
    bytes returnData;
    bool shouldRevert;

    constructor(bytes memory returnData_, bool shouldRevert_) {
        returnData = returnData_;
        shouldRevert = shouldRevert_;
    }

    fallback() external payable {
        bytes memory returnData_ = returnData;

        if (shouldRevert) {
            assembly {
                revert(add(returnData_, 0x20), mload(returnData_))
            }
        } else {
            assembly {
                return(add(returnData_, 0x20), mload(returnData_))
            }
        }
    }
}
