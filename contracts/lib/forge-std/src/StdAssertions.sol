// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {Vm} from "./Vm.sol";

/// @notice Abstract contract providing assertion utilities for Forge tests.
abstract contract StdAssertions {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    event log(string);
    event logs(bytes);

    event log_address(address);
    event log_bytes32(bytes32);
    event log_int(int256);
    event log_uint(uint256);
    event log_bytes(bytes);
    event log_string(string);

    event log_named_address(string key, address val);
    event log_named_bytes32(string key, bytes32 val);
    event log_named_decimal_int(string key, int256 val, uint256 decimals);
    event log_named_decimal_uint(string key, uint256 val, uint256 decimals);
    event log_named_int(string key, int256 val);
    event log_named_uint(string key, uint256 val);
    event log_named_bytes(string key, bytes val);
    event log_named_string(string key, string val);

    event log_array(uint256[] val);
    event log_array(int256[] val);
    event log_array(address[] val);
    event log_named_array(string key, uint256[] val);
    event log_named_array(string key, int256[] val);
    event log_named_array(string key, address[] val);

    bytes32 private constant FAILED_SLOT = bytes32("failed");

    bool private _failed;

    /// @notice Returns true if any test assertion has failed.
    /// @return True if any assertion has failed, false otherwise.
    function failed() public view returns (bool) {
        if (_failed) {
            return true;
        } else {
            return vm.load(address(vm), FAILED_SLOT) != bytes32(0);
        }
    }

    /// @notice Marks the test as failed and records the failure in storage.
    function fail() internal virtual {
        vm.store(address(vm), FAILED_SLOT, bytes32(uint256(1)));
        _failed = true;
    }

    /// @notice Marks the test as failed with a custom message.
    /// @param message The failure message to display.
    function fail(string memory message) internal virtual {
        fail();
        vm.assertTrue(false, message);
    }

    /// @notice Asserts that `data` is true.
    /// @param data The boolean value to assert.
    function assertTrue(bool data) internal pure virtual {
        if (!data) {
            vm.assertTrue(data);
        }
    }

    /// @notice Asserts that `data` is true with a custom error message.
    /// @param data The boolean value to assert.
    /// @param err The error message on failure.
    function assertTrue(bool data, string memory err) internal pure virtual {
        if (!data) {
            vm.assertTrue(data, err);
        }
    }

    /// @notice Asserts that `data` is false.
    /// @param data The boolean value to assert.
    function assertFalse(bool data) internal pure virtual {
        if (data) {
            vm.assertFalse(data);
        }
    }

    /// @notice Asserts that `data` is false with a custom error message.
    /// @param data The boolean value to assert.
    /// @param err The error message on failure.
    function assertFalse(bool data, string memory err) internal pure virtual {
        if (data) {
            vm.assertFalse(data, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bool left, bool right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bool left, bool right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(uint256 left, uint256 right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertEqDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertEqDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertEqDecimal(uint256 left, uint256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertEqDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(int256 left, int256 right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(int256 left, int256 right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertEqDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertEqDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertEqDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertEqDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(address left, address right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(address left, address right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bytes32 left, bytes32 right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bytes32 left, bytes32 right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right` (legacy bytes32 variant).
    /// @dev Alias for assertEq(bytes32,bytes32) kept for backwards-compatibility.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq32(bytes32 left, bytes32 right) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right);
        }
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message (legacy bytes32 variant).
    /// @dev Alias for assertEq(bytes32,bytes32,string) kept for backwards-compatibility.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq32(bytes32 left, bytes32 right, string memory err) internal pure virtual {
        if (left != right) {
            vm.assertEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(string memory left, string memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(string memory left, string memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bytes memory left, bytes memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bytes memory left, bytes memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bool[] memory left, bool[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bool[] memory left, bool[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(uint256[] memory left, uint256[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(uint256[] memory left, uint256[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(int256[] memory left, int256[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(int256[] memory left, int256[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(address[] memory left, address[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(address[] memory left, address[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bytes32[] memory left, bytes32[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bytes32[] memory left, bytes32[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(string[] memory left, string[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(string[] memory left, string[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEq(bytes[] memory left, bytes[] memory right) internal pure virtual {
        vm.assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertEq(bytes[] memory left, bytes[] memory right, string memory err) internal pure virtual {
        vm.assertEq(left, right, err);
    }

    // Legacy helper
    /// @notice Asserts that `left` is equal to `right` (legacy uint256 variant).
    /// @dev Legacy helper kept for backwards-compatibility.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertEqUint(uint256 left, uint256 right) internal pure virtual {
        assertEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bool left, bool right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bool left, bool right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(uint256 left, uint256 right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertNotEqDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertNotEqDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is not equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertNotEqDecimal(uint256 left, uint256 right, uint256 decimals, string memory err)
        internal
        pure
        virtual
    {
        vm.assertNotEqDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(int256 left, int256 right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(int256 left, int256 right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertNotEqDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertNotEqDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is not equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertNotEqDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertNotEqDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(address left, address right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(address left, address right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bytes32 left, bytes32 right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bytes32 left, bytes32 right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` (legacy bytes32 variant).
    /// @dev Alias for assertNotEq(bytes32,bytes32) kept for backwards-compatibility.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq32(bytes32 left, bytes32 right) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right);
        }
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message (legacy bytes32 variant).
    /// @dev Alias for assertNotEq(bytes32,bytes32,string) kept for backwards-compatibility.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq32(bytes32 left, bytes32 right, string memory err) internal pure virtual {
        if (left == right) {
            vm.assertNotEq(left, right, err);
        }
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(string memory left, string memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(string memory left, string memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bytes memory left, bytes memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bytes memory left, bytes memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bool[] memory left, bool[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bool[] memory left, bool[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(uint256[] memory left, uint256[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(uint256[] memory left, uint256[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(int256[] memory left, int256[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(int256[] memory left, int256[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(address[] memory left, address[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(address[] memory left, address[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bytes32[] memory left, bytes32[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bytes32[] memory left, bytes32[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(string[] memory left, string[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(string[] memory left, string[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertNotEq(bytes[] memory left, bytes[] memory right) internal pure virtual {
        vm.assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertNotEq(bytes[] memory left, bytes[] memory right, string memory err) internal pure virtual {
        vm.assertNotEq(left, right, err);
    }

    /// @notice Asserts that `left` is strictly less than `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertLt(uint256 left, uint256 right) internal pure virtual {
        if (left >= right) {
            vm.assertLt(left, right);
        }
    }

    /// @notice Asserts that `left` is strictly less than `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertLt(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left >= right) {
            vm.assertLt(left, right, err);
        }
    }

    /// @notice Asserts that `left` is strictly less than `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertLtDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertLtDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is strictly less than `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertLtDecimal(uint256 left, uint256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertLtDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is strictly less than `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertLt(int256 left, int256 right) internal pure virtual {
        if (left >= right) {
            vm.assertLt(left, right);
        }
    }

    /// @notice Asserts that `left` is strictly less than `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertLt(int256 left, int256 right, string memory err) internal pure virtual {
        if (left >= right) {
            vm.assertLt(left, right, err);
        }
    }

    /// @notice Asserts that `left` is strictly less than `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertLtDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertLtDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is strictly less than `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertLtDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertLtDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is strictly greater than `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertGt(uint256 left, uint256 right) internal pure virtual {
        if (left <= right) {
            vm.assertGt(left, right);
        }
    }

    /// @notice Asserts that `left` is strictly greater than `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertGt(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left <= right) {
            vm.assertGt(left, right, err);
        }
    }

    /// @notice Asserts that `left` is strictly greater than `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertGtDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertGtDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is strictly greater than `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertGtDecimal(uint256 left, uint256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertGtDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is strictly greater than `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertGt(int256 left, int256 right) internal pure virtual {
        if (left <= right) {
            vm.assertGt(left, right);
        }
    }

    /// @notice Asserts that `left` is strictly greater than `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertGt(int256 left, int256 right, string memory err) internal pure virtual {
        if (left <= right) {
            vm.assertGt(left, right, err);
        }
    }

    /// @notice Asserts that `left` is strictly greater than `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertGtDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertGtDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is strictly greater than `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertGtDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertGtDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is less than or equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertLe(uint256 left, uint256 right) internal pure virtual {
        if (left > right) {
            vm.assertLe(left, right);
        }
    }

    /// @notice Asserts that `left` is less than or equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertLe(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left > right) {
            vm.assertLe(left, right, err);
        }
    }

    /// @notice Asserts that `left` is less than or equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertLeDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertLeDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is less than or equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertLeDecimal(uint256 left, uint256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertLeDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is less than or equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertLe(int256 left, int256 right) internal pure virtual {
        if (left > right) {
            vm.assertLe(left, right);
        }
    }

    /// @notice Asserts that `left` is less than or equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertLe(int256 left, int256 right, string memory err) internal pure virtual {
        if (left > right) {
            vm.assertLe(left, right, err);
        }
    }

    /// @notice Asserts that `left` is less than or equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertLeDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertLeDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is less than or equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertLeDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertLeDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is greater than or equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertGe(uint256 left, uint256 right) internal pure virtual {
        if (left < right) {
            vm.assertGe(left, right);
        }
    }

    /// @notice Asserts that `left` is greater than or equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertGe(uint256 left, uint256 right, string memory err) internal pure virtual {
        if (left < right) {
            vm.assertGe(left, right, err);
        }
    }

    /// @notice Asserts that `left` is greater than or equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertGeDecimal(uint256 left, uint256 right, uint256 decimals) internal pure virtual {
        vm.assertGeDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is greater than or equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertGeDecimal(uint256 left, uint256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertGeDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that `left` is greater than or equal to `right`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    function assertGe(int256 left, int256 right) internal pure virtual {
        if (left < right) {
            vm.assertGe(left, right);
        }
    }

    /// @notice Asserts that `left` is greater than or equal to `right` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param err The error message on failure.
    function assertGe(int256 left, int256 right, string memory err) internal pure virtual {
        if (left < right) {
            vm.assertGe(left, right, err);
        }
    }

    /// @notice Asserts that `left` is greater than or equal to `right`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    function assertGeDecimal(int256 left, int256 right, uint256 decimals) internal pure virtual {
        vm.assertGeDecimal(left, right, decimals);
    }

    /// @notice Asserts that `left` is greater than or equal to `right`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertGeDecimal(int256 left, int256 right, uint256 decimals, string memory err) internal pure virtual {
        vm.assertGeDecimal(left, right, decimals, err);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    function assertApproxEqAbs(uint256 left, uint256 right, uint256 maxDelta) internal pure virtual {
        vm.assertApproxEqAbs(left, right, maxDelta);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param err The error message on failure.
    function assertApproxEqAbs(uint256 left, uint256 right, uint256 maxDelta, string memory err) internal pure virtual {
        vm.assertApproxEqAbs(left, right, maxDelta, err);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param decimals The number of decimals for formatting.
    function assertApproxEqAbsDecimal(uint256 left, uint256 right, uint256 maxDelta, uint256 decimals)
        internal
        pure
        virtual
    {
        vm.assertApproxEqAbsDecimal(left, right, maxDelta, decimals);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertApproxEqAbsDecimal(
        uint256 left,
        uint256 right,
        uint256 maxDelta,
        uint256 decimals,
        string memory err
    ) internal pure virtual {
        vm.assertApproxEqAbsDecimal(left, right, maxDelta, decimals, err);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    function assertApproxEqAbs(int256 left, int256 right, uint256 maxDelta) internal pure virtual {
        vm.assertApproxEqAbs(left, right, maxDelta);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param err The error message on failure.
    function assertApproxEqAbs(int256 left, int256 right, uint256 maxDelta, string memory err) internal pure virtual {
        vm.assertApproxEqAbs(left, right, maxDelta, err);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param decimals The number of decimals for formatting.
    function assertApproxEqAbsDecimal(int256 left, int256 right, uint256 maxDelta, uint256 decimals)
        internal
        pure
        virtual
    {
        vm.assertApproxEqAbsDecimal(left, right, maxDelta, decimals);
    }

    /// @notice Asserts that the absolute difference between `left` and `right` is at most `maxDelta`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxDelta The maximum absolute difference allowed.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertApproxEqAbsDecimal(int256 left, int256 right, uint256 maxDelta, uint256 decimals, string memory err)
        internal
        pure
        virtual
    {
        vm.assertApproxEqAbsDecimal(left, right, maxDelta, decimals, err);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    function assertApproxEqRel(
        uint256 left,
        uint256 right,
        uint256 maxPercentDelta // An 18 decimal fixed point number, where 1e18 == 100%
    )
        internal
        pure
        virtual
    {
        vm.assertApproxEqRel(left, right, maxPercentDelta);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param err The error message on failure.
    function assertApproxEqRel(
        uint256 left,
        uint256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        string memory err
    )
        internal
        pure
        virtual
    {
        vm.assertApproxEqRel(left, right, maxPercentDelta, err);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param decimals The number of decimals for formatting.
    function assertApproxEqRelDecimal(
        uint256 left,
        uint256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        uint256 decimals
    )
        internal
        pure
        virtual
    {
        vm.assertApproxEqRelDecimal(left, right, maxPercentDelta, decimals);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertApproxEqRelDecimal(
        uint256 left,
        uint256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        uint256 decimals,
        string memory err
    ) internal pure virtual {
        vm.assertApproxEqRelDecimal(left, right, maxPercentDelta, decimals, err);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    function assertApproxEqRel(int256 left, int256 right, uint256 maxPercentDelta) internal pure virtual {
        vm.assertApproxEqRel(left, right, maxPercentDelta);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta` with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param err The error message on failure.
    function assertApproxEqRel(
        int256 left,
        int256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        string memory err
    )
        internal
        pure
        virtual
    {
        vm.assertApproxEqRel(left, right, maxPercentDelta, err);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`, formatting values with `decimals` decimal places on failure.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param decimals The number of decimals for formatting.
    function assertApproxEqRelDecimal(
        int256 left,
        int256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        uint256 decimals
    )
        internal
        pure
        virtual
    {
        vm.assertApproxEqRelDecimal(left, right, maxPercentDelta, decimals);
    }

    /// @notice Asserts that the relative difference between `left` and `right` is at most `maxPercentDelta`, formatting values with `decimals` decimal places on failure, with a custom error message.
    /// @param left The left-hand side value.
    /// @param right The right-hand side value.
    /// @param maxPercentDelta The maximum relative delta allowed, as an 18 decimal fixed point number where 1e18 == 100%.
    /// @param decimals The number of decimals for formatting.
    /// @param err The error message on failure.
    function assertApproxEqRelDecimal(
        int256 left,
        int256 right,
        uint256 maxPercentDelta, // An 18 decimal fixed point number, where 1e18 == 100%
        uint256 decimals,
        string memory err
    ) internal pure virtual {
        vm.assertApproxEqRelDecimal(left, right, maxPercentDelta, decimals, err);
    }

    // Inherited from DSTest, not used but kept for backwards-compatibility
    /// @notice Returns true if `left` and `right` have equal content.
    /// @dev Inherited from DSTest, kept for backwards-compatibility.
    /// @param left The left-hand side bytes.
    /// @param right The right-hand side bytes.
    /// @return True if the byte content is equal, false otherwise.
    function checkEq0(bytes memory left, bytes memory right) internal pure returns (bool) {
        return keccak256(left) == keccak256(right);
    }

    /// @notice Asserts that `left` is equal to `right` (legacy bytes variant).
    /// @dev Alias for assertEq(bytes,bytes) kept for backwards-compatibility.
    /// @param left The left-hand side bytes.
    /// @param right The right-hand side bytes.
    function assertEq0(bytes memory left, bytes memory right) internal pure virtual {
        assertEq(left, right);
    }

    /// @notice Asserts that `left` is equal to `right` with a custom error message (legacy bytes variant).
    /// @dev Alias for assertEq(bytes,bytes,string) kept for backwards-compatibility.
    /// @param left The left-hand side bytes.
    /// @param right The right-hand side bytes.
    /// @param err The error message on failure.
    function assertEq0(bytes memory left, bytes memory right, string memory err) internal pure virtual {
        assertEq(left, right, err);
    }

    /// @notice Asserts that `left` is not equal to `right` (legacy bytes variant).
    /// @dev Alias for assertNotEq(bytes,bytes) kept for backwards-compatibility.
    /// @param left The left-hand side bytes.
    /// @param right The right-hand side bytes.
    function assertNotEq0(bytes memory left, bytes memory right) internal pure virtual {
        assertNotEq(left, right);
    }

    /// @notice Asserts that `left` is not equal to `right` with a custom error message (legacy bytes variant).
    /// @dev Alias for assertNotEq(bytes,bytes,string) kept for backwards-compatibility.
    /// @param left The left-hand side bytes.
    /// @param right The right-hand side bytes.
    /// @param err The error message on failure.
    function assertNotEq0(bytes memory left, bytes memory right, string memory err) internal pure virtual {
        assertNotEq(left, right, err);
    }

    /// @notice Asserts that two calls to the same target with different calldata produce equal return or revert data.
    /// @param target The contract address to call.
    /// @param callDataA The calldata for the first call.
    /// @param callDataB The calldata for the second call.
    function assertEqCall(address target, bytes memory callDataA, bytes memory callDataB) internal virtual {
        assertEqCall(target, callDataA, target, callDataB, true);
    }

    /// @notice Asserts that calls to two different targets produce equal return or revert data.
    /// @param targetA The first contract address.
    /// @param callDataA The calldata for the first call.
    /// @param targetB The second contract address.
    /// @param callDataB The calldata for the second call.
    function assertEqCall(address targetA, bytes memory callDataA, address targetB, bytes memory callDataB)
        internal
        virtual
    {
        assertEqCall(targetA, callDataA, targetB, callDataB, true);
    }

    /// @notice Asserts that two calls to the same target with different calldata produce equal return or revert data.
    /// @param target The contract address to call.
    /// @param callDataA The calldata for the first call.
    /// @param callDataB The calldata for the second call.
    /// @param strictRevertData If true, also asserts that revert data matches when both calls revert.
    function assertEqCall(address target, bytes memory callDataA, bytes memory callDataB, bool strictRevertData)
        internal
        virtual
    {
        assertEqCall(target, callDataA, target, callDataB, strictRevertData);
    }

    /// @notice Asserts that calls to two targets produce equal return or revert data.
    /// @param targetA The first contract address.
    /// @param callDataA The calldata for the first call.
    /// @param targetB The second contract address.
    /// @param callDataB The calldata for the second call.
    /// @param strictRevertData If true, also asserts that revert data matches when both calls revert.
    function assertEqCall(
        address targetA,
        bytes memory callDataA,
        address targetB,
        bytes memory callDataB,
        bool strictRevertData
    ) internal virtual {
        (bool successA, bytes memory returnDataA) = address(targetA).call(callDataA);
        (bool successB, bytes memory returnDataB) = address(targetB).call(callDataB);

        if (successA && successB) {
            assertEq(returnDataA, returnDataB, "Call return data does not match");
        }

        if (!successA && !successB && strictRevertData) {
            assertEq(returnDataA, returnDataB, "Call revert data does not match");
        }

        if (!successA && successB) {
            emit log("Error: Calls were not equal");
            emit log_named_bytes("  Left call revert data", returnDataA);
            emit log_named_bytes(" Right call return data", returnDataB);
            revert("assertion failed");
        }

        if (successA && !successB) {
            emit log("Error: Calls were not equal");
            emit log_named_bytes("  Left call return data", returnDataA);
            emit log_named_bytes(" Right call revert data", returnDataB);
            revert("assertion failed");
        }
    }
}
