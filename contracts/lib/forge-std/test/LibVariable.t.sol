// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity ^0.8.13;

import {Test} from "../src/Test.sol";
import {Variable, Type, TypeKind, LibVariable} from "../src/LibVariable.sol";

contract LibVariableTest is Test {
    using LibVariable for Type;
    using LibVariable for TypeKind;

    LibVariableHelper internal helper;

    bytes internal expectedErr;
    Variable internal uninitVar;
    Variable internal boolVar;
    Variable internal addressVar;
    Variable internal bytes32Var;
    Variable internal uintVar;
    Variable internal intVar;
    Variable internal stringVar;
    Variable internal bytesVar;
    Variable internal boolArrayVar;
    Variable internal addressArrayVar;
    Variable internal bytes32ArrayVar;
    Variable internal uintArrayVar;
    Variable internal intArrayVar;
    Variable internal stringArrayVar;
    Variable internal bytesArrayVar;

    function setUp() public {
        helper = new LibVariableHelper();

        // UNINITIALIZED
        uninitVar = Variable(Type(TypeKind.None, false), "");

        // SINGLE VALUES
        boolVar = Variable(Type(TypeKind.Bool, false), abi.encode(true));
        addressVar = Variable(Type(TypeKind.Address, false), abi.encode(address(0xdeadbeef)));
        bytes32Var = Variable(Type(TypeKind.Bytes32, false), abi.encode(bytes32(uint256(42))));
        uintVar = Variable(Type(TypeKind.Uint256, false), abi.encode(uint256(123)));
        intVar = Variable(Type(TypeKind.Int256, false), abi.encode(int256(-123)));
        stringVar = Variable(Type(TypeKind.String, false), abi.encode("hello world"));
        bytesVar = Variable(Type(TypeKind.Bytes, false), abi.encode(hex"c0ffee"));

        // ARRAY VALUES
        bool[] memory bools = new bool[](2);
        bools[0] = true;
        bools[1] = false;
        boolArrayVar = Variable(Type(TypeKind.Bool, true), abi.encode(bools));

        address[] memory addrs = new address[](2);
        addrs[0] = address(0x1);
        addrs[1] = address(0x2);
        addressArrayVar = Variable(Type(TypeKind.Address, true), abi.encode(addrs));

        bytes32[] memory b32s = new bytes32[](2);
        b32s[0] = bytes32(uint256(1));
        b32s[1] = bytes32(uint256(2));
        bytes32ArrayVar = Variable(Type(TypeKind.Bytes32, true), abi.encode(b32s));

        uint256[] memory uints = new uint256[](2);
        uints[0] = 1;
        uints[1] = 2;
        uintArrayVar = Variable(Type(TypeKind.Uint256, true), abi.encode(uints));

        int256[] memory ints = new int256[](2);
        ints[0] = -1;
        ints[1] = 2;
        intArrayVar = Variable(Type(TypeKind.Int256, true), abi.encode(ints));

        string[] memory strings = new string[](2);
        strings[0] = "one";
        strings[1] = "two";
        stringArrayVar = Variable(Type(TypeKind.String, true), abi.encode(strings));

        bytes[] memory b = new bytes[](2);
        b[0] = hex"01";
        b[1] = hex"02";
        bytesArrayVar = Variable(Type(TypeKind.Bytes, true), abi.encode(b));
    }

    // -- SUCCESS CASES --------------------------------------------------------

    function test_TypeHelpers() public view {
        // TypeKind.toString()
        assertEq(TypeKind.None.toString(), "none");
        assertEq(TypeKind.Bool.toString(), "bool");
        assertEq(TypeKind.Address.toString(), "address");
        assertEq(TypeKind.Bytes32.toString(), "bytes32");
        assertEq(TypeKind.Uint256.toString(), "uint256");
        assertEq(TypeKind.Int256.toString(), "int256");
        assertEq(TypeKind.String.toString(), "string");
        assertEq(TypeKind.Bytes.toString(), "bytes");

        // TypeKind.toTomlKey()
        assertEq(TypeKind.Uint256.toTomlKey(), "uint");
        assertEq(TypeKind.Int256.toTomlKey(), "int");
        assertEq(TypeKind.Bytes32.toTomlKey(), "bytes32");

        // Type.toString()
        assertEq(boolVar.ty.toString(), "bool");
        assertEq(boolArrayVar.ty.toString(), "bool[]");
        assertEq(uintVar.ty.toString(), "uint256");
        assertEq(uintArrayVar.ty.toString(), "uint256[]");
        assertEq(uninitVar.ty.toString(), "none");

        // Type.isEqual()
        assertTrue(boolVar.ty.isEqual(Type(TypeKind.Bool, false)));
        assertFalse(boolVar.ty.isEqual(Type(TypeKind.Bool, true)));
        assertFalse(boolVar.ty.isEqual(Type(TypeKind.Address, false)));

        // Type.assertEq()
        boolVar.ty.assertEq(Type(TypeKind.Bool, false));
        uintArrayVar.ty.assertEq(Type(TypeKind.Uint256, true));
    }

    function test_Coercion() public view {
        // Single values
        assertTrue(helper.toBool(boolVar));
        assertEq(helper.toAddress(addressVar), address(0xdeadbeef));
        assertEq(helper.toBytes32(bytes32Var), bytes32(uint256(42)));
        assertEq(helper.toUint256(uintVar), 123);
        assertEq(helper.toInt256(intVar), -123);
        assertEq(helper.toString(stringVar), "hello world");
        assertEq(helper.toBytes(bytesVar), hex"c0ffee");

        // Bool array
        bool[] memory bools = helper.toBoolArray(boolArrayVar);
        assertEq(bools.length, 2);
        assertTrue(bools[0]);
        assertFalse(bools[1]);

        // Address array
        address[] memory addrs = helper.toAddressArray(addressArrayVar);
        assertEq(addrs.length, 2);
        assertEq(addrs[0], address(0x1));
        assertEq(addrs[1], address(0x2));

        // String array
        string[] memory strings = helper.toStringArray(stringArrayVar);
        assertEq(strings.length, 2);
        assertEq(strings[0], "one");
        assertEq(strings[1], "two");

        // Bytes32 array
        bytes32[] memory b32s = helper.toBytes32Array(bytes32ArrayVar);
        assertEq(b32s.length, 2);
        assertEq(b32s[0], bytes32(uint256(1)));
        assertEq(b32s[1], bytes32(uint256(2)));

        // Int array
        int256[] memory ints = helper.toInt256Array(intArrayVar);
        assertEq(ints.length, 2);
        assertEq(ints[0], -1);
        assertEq(ints[1], 2);

        // Bytes array
        bytes[] memory b = helper.toBytesArray(bytesArrayVar);
        assertEq(b.length, 2);
        assertEq(b[0], hex"01");
        assertEq(b[1], hex"02");
    }

    function test_Downcasting() public view {
        // Uint downcasting
        Variable memory v_uint_small = Variable(Type(TypeKind.Uint256, false), abi.encode(uint256(100)));
        assertEq(helper.toUint128(v_uint_small), 100);
        assertEq(helper.toUint64(v_uint_small), 100);
        assertEq(helper.toUint32(v_uint_small), 100);
        assertEq(helper.toUint16(v_uint_small), 100);
        assertEq(helper.toUint8(v_uint_small), 100);

        // Uint array downcasting
        uint256[] memory small_uints = new uint256[](2);
        small_uints[0] = 10;
        small_uints[1] = 20;
        Variable memory v_uint_array_small = Variable(Type(TypeKind.Uint256, true), abi.encode(small_uints));
        uint8[] memory u8_array = helper.toUint8Array(v_uint_array_small);
        assertEq(u8_array[0], 10);
        assertEq(u8_array[1], 20);

        // Int downcasting
        Variable memory v_int_small_pos = Variable(Type(TypeKind.Int256, false), abi.encode(int256(100)));
        Variable memory v_int_small_neg = Variable(Type(TypeKind.Int256, false), abi.encode(int256(-100)));
        assertEq(helper.toInt128(v_int_small_pos), 100);
        assertEq(helper.toInt64(v_int_small_neg), -100);
        assertEq(helper.toInt32(v_int_small_pos), 100);
        assertEq(helper.toInt16(v_int_small_neg), -100);
        assertEq(helper.toInt8(v_int_small_pos), 100);

        // Int array downcasting
        int256[] memory small_ints = new int256[](2);
        small_ints[0] = -10;
        small_ints[1] = 20;
        Variable memory intArraySmall = Variable(Type(TypeKind.Int256, true), abi.encode(small_ints));
        int8[] memory i8_array = helper.toInt8Array(intArraySmall);
        assertEq(i8_array[0], -10);
        assertEq(i8_array[1], 20);
    }

    // -- REVERT CASES ---------------------------------------------------------

    function testRevert_NotInitialized() public {
        vm.expectRevert(LibVariable.NotInitialized.selector);
        helper.toBool(uninitVar);

        vm.expectRevert(LibVariable.NotInitialized.selector);
        helper.toAddressArray(uninitVar);
    }

    function testRevert_assertExists() public {
        vm.expectRevert(LibVariable.NotInitialized.selector);
        helper.assertExists(uninitVar);
    }

    function testRevert_TypeMismatch() public {
        // Single values
        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "uint256", "bool"));
        helper.toUint256(boolVar);

        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "address", "string"));
        helper.toAddress(stringVar);

        // Arrays
        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "uint256[]", "bool[]"));
        helper.toUint256Array(boolArrayVar);

        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "address[]", "string[]"));
        helper.toAddressArray(stringArrayVar);

        // Single value to array
        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "bool[]", "bool"));
        helper.toBoolArray(boolVar);

        // Array to single value
        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "bool", "bool[]"));
        helper.toBool(boolArrayVar);

        // assertEq reverts
        vm.expectRevert(abi.encodeWithSelector(LibVariable.TypeMismatch.selector, "uint256", "bool"));
        helper.assertEq(boolVar.ty, Type(TypeKind.Uint256, false));
    }

    function testRevert_UnsafeCast() public {
        // uint overflow
        Variable memory uintLarge = Variable(Type(TypeKind.Uint256, false), abi.encode(uint256(type(uint128).max) + 1));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value does not fit in 'uint128'");
        vm.expectRevert(expectedErr);
        helper.toUint128(uintLarge);

        // int overflow
        Variable memory intLarge = Variable(Type(TypeKind.Int256, false), abi.encode(int256(type(int128).max) + 1));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value does not fit in 'int128'");

        vm.expectRevert(expectedErr);
        helper.toInt128(intLarge);

        // int underflow
        Variable memory intSmall = Variable(Type(TypeKind.Int256, false), abi.encode(int256(type(int128).min) - 1));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value does not fit in 'int128'");

        vm.expectRevert(expectedErr);
        helper.toInt128(intSmall);

        // uint array overflow
        uint256[] memory uintArray = new uint256[](2);
        uintArray[0] = 10;
        uintArray[1] = uint256(type(uint64).max) + 1;
        Variable memory uintArrayLarge = Variable(Type(TypeKind.Uint256, true), abi.encode(uintArray));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value in array does not fit in 'uint64'");

        vm.expectRevert(expectedErr);
        helper.toUint64Array(uintArrayLarge);

        // int array overflow
        int256[] memory intArray = new int256[](2);
        intArray[0] = 10;
        intArray[1] = int256(type(int64).max) + 1;
        Variable memory intArrayLarge = Variable(Type(TypeKind.Int256, true), abi.encode(intArray));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value in array does not fit in 'int64'");

        vm.expectRevert(expectedErr);
        helper.toInt64Array(intArrayLarge);

        // int array underflow
        intArray[0] = 10;
        intArray[1] = int256(type(int64).min) - 1;
        Variable memory intArraySmall = Variable(Type(TypeKind.Int256, true), abi.encode(intArray));
        expectedErr = abi.encodeWithSelector(LibVariable.UnsafeCast.selector, "value in array does not fit in 'int64'");

        vm.expectRevert(expectedErr);
        helper.toInt64Array(intArraySmall);
    }
}

/// @dev We must use an external helper contract to ensure proper call depth for `vm.expectRevert`,
///      as direct library calls are inlined by the compiler, causing call depth issues.
contract LibVariableHelper {
    using LibVariable for Type;
    using LibVariable for TypeKind;

    // Assertions
    function assertExists(Variable memory v) external pure {
        v.assertExists();
    }

    function assertEq(Type memory t1, Type memory t2) external pure {
        t1.assertEq(t2);
    }

    // Single Value Coercion
    function toBool(Variable memory v) external pure returns (bool) {
        return v.toBool();
    }

    function toAddress(Variable memory v) external pure returns (address) {
        return v.toAddress();
    }

    function toBytes32(Variable memory v) external pure returns (bytes32) {
        return v.toBytes32();
    }

    function toUint256(Variable memory v) external pure returns (uint256) {
        return v.toUint256();
    }

    function toInt256(Variable memory v) external pure returns (int256) {
        return v.toInt256();
    }

    function toString(Variable memory v) external pure returns (string memory) {
        return v.toString();
    }

    function toBytes(Variable memory v) external pure returns (bytes memory) {
        return v.toBytes();
    }

    // Array Coercion
    function toBoolArray(Variable memory v) external pure returns (bool[] memory) {
        return v.toBoolArray();
    }

    function toAddressArray(Variable memory v) external pure returns (address[] memory) {
        return v.toAddressArray();
    }

    function toBytes32Array(Variable memory v) external pure returns (bytes32[] memory) {
        return v.toBytes32Array();
    }

    function toUint256Array(Variable memory v) external pure returns (uint256[] memory) {
        return v.toUint256Array();
    }

    function toInt256Array(Variable memory v) external pure returns (int256[] memory) {
        return v.toInt256Array();
    }

    function toStringArray(Variable memory v) external pure returns (string[] memory) {
        return v.toStringArray();
    }

    function toBytesArray(Variable memory v) external pure returns (bytes[] memory) {
        return v.toBytesArray();
    }

    // Uint Downcasting
    function toUint128(Variable memory v) external pure returns (uint128) {
        return v.toUint128();
    }

    function toUint64(Variable memory v) external pure returns (uint64) {
        return v.toUint64();
    }

    function toUint32(Variable memory v) external pure returns (uint32) {
        return v.toUint32();
    }

    function toUint16(Variable memory v) external pure returns (uint16) {
        return v.toUint16();
    }

    function toUint8(Variable memory v) external pure returns (uint8) {
        return v.toUint8();
    }

    // Int Downcasting
    function toInt128(Variable memory v) external pure returns (int128) {
        return v.toInt128();
    }

    function toInt64(Variable memory v) external pure returns (int64) {
        return v.toInt64();
    }

    function toInt32(Variable memory v) external pure returns (int32) {
        return v.toInt32();
    }

    function toInt16(Variable memory v) external pure returns (int16) {
        return v.toInt16();
    }

    function toInt8(Variable memory v) external pure returns (int8) {
        return v.toInt8();
    }

    // Uint Array Downcasting
    function toUint128Array(Variable memory v) external pure returns (uint128[] memory) {
        return v.toUint128Array();
    }

    function toUint64Array(Variable memory v) external pure returns (uint64[] memory) {
        return v.toUint64Array();
    }

    function toUint32Array(Variable memory v) external pure returns (uint32[] memory) {
        return v.toUint32Array();
    }

    function toUint16Array(Variable memory v) external pure returns (uint16[] memory) {
        return v.toUint16Array();
    }

    function toUint8Array(Variable memory v) external pure returns (uint8[] memory) {
        return v.toUint8Array();
    }

    // Int Array Downcasting
    function toInt128Array(Variable memory v) external pure returns (int128[] memory) {
        return v.toInt128Array();
    }

    function toInt64Array(Variable memory v) external pure returns (int64[] memory) {
        return v.toInt64Array();
    }

    function toInt32Array(Variable memory v) external pure returns (int32[] memory) {
        return v.toInt32Array();
    }

    function toInt16Array(Variable memory v) external pure returns (int16[] memory) {
        return v.toInt16Array();
    }

    function toInt8Array(Variable memory v) external pure returns (int8[] memory) {
        return v.toInt8Array();
    }
}
