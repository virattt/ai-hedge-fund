// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {stdStorage, StdStorage} from "../src/StdStorage.sol";
import {Test} from "../src/Test.sol";

contract StdStorageTest is Test {
    using stdStorage for StdStorage;

    StorageTest internal test;

    function setUp() public {
        test = new StorageTest();
    }

    function test_StorageHidden() public {
        assertEq(uint256(keccak256("my.random.var")), stdstore.target(address(test)).sig("hidden()").find());
    }

    function test_StorageObvious() public {
        assertEq(uint256(0), stdstore.target(address(test)).sig("exists()").find());
    }

    function test_StorageExtraSload() public {
        assertEq(16, stdstore.target(address(test)).sig(test.extra_sload.selector).find());
    }

    function test_StorageCheckedWriteHidden() public {
        stdstore.target(address(test)).sig(test.hidden.selector).checked_write(100);
        assertEq(uint256(test.hidden()), 100);
    }

    function test_StorageCheckedWriteObvious() public {
        stdstore.target(address(test)).sig(test.exists.selector).checked_write(100);
        assertEq(test.exists(), 100);
    }

    function test_StorageCheckedWriteSignedIntegerHidden() public {
        stdstore.target(address(test)).sig(test.hidden.selector).checked_write_int(-100);
        assertEq(int256(uint256(test.hidden())), -100);
    }

    function test_StorageCheckedWriteSignedIntegerObvious() public {
        stdstore.target(address(test)).sig(test.tG.selector).checked_write_int(-100);
        assertEq(test.tG(), -100);
    }

    function test_StorageMapStructA() public {
        uint256 slot =
            stdstore.target(address(test)).sig(test.map_struct.selector).with_key(address(this)).depth(0).find();
        assertEq(uint256(keccak256(abi.encode(address(this), 4))), slot);
    }

    function test_StorageMapStructB() public {
        uint256 slot =
            stdstore.target(address(test)).sig(test.map_struct.selector).with_key(address(this)).depth(1).find();
        assertEq(uint256(keccak256(abi.encode(address(this), 4))) + 1, slot);
    }

    function test_StorageDeepMap() public {
        uint256 slot = stdstore.target(address(test)).sig(test.deep_map.selector).with_key(address(this))
            .with_key(address(this)).find();
        assertEq(uint256(keccak256(abi.encode(address(this), keccak256(abi.encode(address(this), uint256(5)))))), slot);
    }

    function test_StorageCheckedWriteDeepMap() public {
        stdstore.target(address(test)).sig(test.deep_map.selector).with_key(address(this)).with_key(address(this))
            .checked_write(100);
        assertEq(100, test.deep_map(address(this), address(this)));
    }

    function test_StorageDeepMapStructA() public {
        uint256 slot = stdstore.target(address(test)).sig(test.deep_map_struct.selector).with_key(address(this))
            .with_key(address(this)).depth(0).find();
        assertEq(
            bytes32(
                uint256(keccak256(abi.encode(address(this), keccak256(abi.encode(address(this), uint256(6)))))) + 0
            ),
            bytes32(slot)
        );
    }

    function test_StorageDeepMapStructB() public {
        uint256 slot = stdstore.target(address(test)).sig(test.deep_map_struct.selector).with_key(address(this))
            .with_key(address(this)).depth(1).find();
        assertEq(
            bytes32(
                uint256(keccak256(abi.encode(address(this), keccak256(abi.encode(address(this), uint256(6)))))) + 1
            ),
            bytes32(slot)
        );
    }

    function test_StorageCheckedWriteDeepMapStructA() public {
        stdstore.target(address(test)).sig(test.deep_map_struct.selector).with_key(address(this))
            .with_key(address(this)).depth(0).checked_write(100);
        (uint256 a, uint256 b) = test.deep_map_struct(address(this), address(this));
        assertEq(100, a);
        assertEq(0, b);
    }

    function test_StorageCheckedWriteDeepMapStructB() public {
        stdstore.target(address(test)).sig(test.deep_map_struct.selector).with_key(address(this))
            .with_key(address(this)).depth(1).checked_write(100);
        (uint256 a, uint256 b) = test.deep_map_struct(address(this), address(this));
        assertEq(0, a);
        assertEq(100, b);
    }

    function test_StorageCheckedWriteMapStructA() public {
        stdstore.target(address(test)).sig(test.map_struct.selector).with_key(address(this)).depth(0).checked_write(100);
        (uint256 a, uint256 b) = test.map_struct(address(this));
        assertEq(a, 100);
        assertEq(b, 0);
    }

    function test_StorageCheckedWriteMapStructB() public {
        stdstore.target(address(test)).sig(test.map_struct.selector).with_key(address(this)).depth(1).checked_write(100);
        (uint256 a, uint256 b) = test.map_struct(address(this));
        assertEq(a, 0);
        assertEq(b, 100);
    }

    function test_StorageStructA() public {
        uint256 slot = stdstore.target(address(test)).sig(test.basic.selector).depth(0).find();
        assertEq(uint256(7), slot);
    }

    function test_StorageStructB() public {
        uint256 slot = stdstore.target(address(test)).sig(test.basic.selector).depth(1).find();
        assertEq(uint256(7) + 1, slot);
    }

    function test_StorageCheckedWriteStructA() public {
        stdstore.target(address(test)).sig(test.basic.selector).depth(0).checked_write(100);
        (uint256 a, uint256 b) = test.basic();
        assertEq(a, 100);
        assertEq(b, 1337);
    }

    function test_StorageCheckedWriteStructB() public {
        stdstore.target(address(test)).sig(test.basic.selector).depth(1).checked_write(100);
        (uint256 a, uint256 b) = test.basic();
        assertEq(a, 1337);
        assertEq(b, 100);
    }

    function test_StorageMapAddrFound() public {
        uint256 slot = stdstore.target(address(test)).sig(test.map_addr.selector).with_key(address(this)).find();
        assertEq(uint256(keccak256(abi.encode(address(this), uint256(1)))), slot);
    }

    function test_StorageMapAddrRoot() public {
        (uint256 slot, bytes32 key) =
            stdstore.target(address(test)).sig(test.map_addr.selector).with_key(address(this)).parent();
        assertEq(address(uint160(uint256(key))), address(this));
        assertEq(uint256(1), slot);
        slot = stdstore.target(address(test)).sig(test.map_addr.selector).with_key(address(this)).root();
        assertEq(uint256(1), slot);
    }

    function test_StorageMapUintFound() public {
        uint256 slot = stdstore.target(address(test)).sig(test.map_uint.selector).with_key(100).find();
        assertEq(uint256(keccak256(abi.encode(100, uint256(2)))), slot);
    }

    function test_StorageCheckedWriteMapUint() public {
        stdstore.target(address(test)).sig(test.map_uint.selector).with_key(100).checked_write(100);
        assertEq(100, test.map_uint(100));
    }

    function test_StorageCheckedWriteMapAddr() public {
        stdstore.target(address(test)).sig(test.map_addr.selector).with_key(address(this)).checked_write(100);
        assertEq(100, test.map_addr(address(this)));
    }

    function test_StorageCheckedWriteMapBool() public {
        stdstore.target(address(test)).sig(test.map_bool.selector).with_key(address(this)).checked_write(true);
        assertTrue(test.map_bool(address(this)));
    }

    function testFuzz_StorageCheckedWriteMapPacked(address addr, uint128 value) public {
        stdstore.enable_packed_slots().target(address(test)).sig(test.read_struct_lower.selector).with_key(addr)
            .checked_write(value);
        assertEq(test.read_struct_lower(addr), value);

        stdstore.enable_packed_slots().target(address(test)).sig(test.read_struct_upper.selector).with_key(addr)
            .checked_write(value);
        assertEq(test.read_struct_upper(addr), value);
    }

    function test_StorageCheckedWriteMapPackedFullSuccess() public {
        uint256 full = test.map_packed(address(1337));
        // keep upper 128, set lower 128 to 1337
        full = (full & (uint256((1 << 128) - 1) << 128)) | 1337;
        stdstore.target(address(test)).sig(test.map_packed.selector).with_key(address(uint160(1337)))
            .checked_write(full);
        assertEq(1337, test.read_struct_lower(address(1337)));
    }

    function test_RevertStorageConst() public {
        StorageTestTarget target = new StorageTestTarget(test);

        vm.expectRevert("stdStorage find(StdStorage): No storage use detected for target.");
        target.expectRevertStorageConst();
    }

    function testFuzz_StorageNativePack(uint248 val1, uint248 val2, bool boolVal1, bool boolVal2) public {
        stdstore.enable_packed_slots().target(address(test)).sig(test.tA.selector).checked_write(val1);
        stdstore.enable_packed_slots().target(address(test)).sig(test.tB.selector).checked_write(boolVal1);
        stdstore.enable_packed_slots().target(address(test)).sig(test.tC.selector).checked_write(boolVal2);
        stdstore.enable_packed_slots().target(address(test)).sig(test.tD.selector).checked_write(val2);

        assertEq(test.tA(), val1);
        assertEq(test.tB(), boolVal1);
        assertEq(test.tC(), boolVal2);
        assertEq(test.tD(), val2);
    }

    function test_StorageReadBytes32() public {
        bytes32 val = stdstore.target(address(test)).sig(test.tE.selector).read_bytes32();
        assertEq(val, hex"1337");
    }

    function test_StorageReadBool_False() public {
        bool val = stdstore.target(address(test)).sig(test.tB.selector).read_bool();
        assertEq(val, false);
    }

    function test_StorageReadBool_True() public {
        bool val = stdstore.target(address(test)).sig(test.tH.selector).read_bool();
        assertEq(val, true);
    }

    function test_RevertIf_ReadingNonBoolValue() public {
        vm.expectRevert("stdStorage read_bool(StdStorage): Cannot decode. Make sure you are reading a bool.");
        this.readNonBoolValue();
    }

    function readNonBoolValue() public {
        stdstore.target(address(test)).sig(test.tE.selector).read_bool();
    }

    function test_StorageReadAddress() public {
        address val = stdstore.target(address(test)).sig(test.tF.selector).read_address();
        assertEq(val, address(1337));
    }

    function test_StorageReadUint() public {
        uint256 val = stdstore.target(address(test)).sig(test.exists.selector).read_uint();
        assertEq(val, 1);
    }

    function test_StorageReadInt() public {
        int256 val = stdstore.target(address(test)).sig(test.tG.selector).read_int();
        assertEq(val, type(int256).min);
    }

    function testFuzz_Packed(uint256 val, uint8 elemToGet) public {
        // This function tries an assortment of packed slots, shifts meaning number of elements
        // that are packed. Shiftsizes are the size of each element, i.e. 8 means a data type that is 8 bits, 16 == 16 bits, etc.
        // Combined, these determine how a slot is packed. Making it random is too hard to avoid global rejection limit
        // and make it performant.

        // change the number of shifts
        for (uint256 i = 1; i < 5; i++) {
            uint256 shifts = i;

            elemToGet = uint8(bound(elemToGet, 0, shifts - 1));

            uint256[] memory shiftSizes = new uint256[](shifts);
            for (uint256 j; j < shifts; j++) {
                shiftSizes[j] = 8 * (j + 1);
            }

            test.setRandomPacking(val);

            uint256 leftBits;
            uint256 rightBits;
            for (uint256 j; j < shiftSizes.length; j++) {
                if (j < elemToGet) {
                    leftBits += shiftSizes[j];
                } else if (elemToGet != j) {
                    rightBits += shiftSizes[j];
                }
            }

            // we may have some right bits unaccounted for
            leftBits += 256 - (leftBits + shiftSizes[elemToGet] + rightBits);
            // clear left bits, then clear right bits and realign
            uint256 expectedValToRead = (val << leftBits) >> (leftBits + rightBits);

            uint256 readVal = stdstore.target(address(test)).enable_packed_slots()
                .sig("getRandomPacked(uint8,uint8[],uint8)").with_calldata(abi.encode(shifts, shiftSizes, elemToGet))
                .read_uint();

            assertEq(readVal, expectedValToRead);
        }
    }

    function testFuzz_Packed2(uint256 nvars, uint256 seed) public {
        // Number of random variables to generate.
        nvars = bound(nvars, 1, 20);

        // This will decrease as we generate values in the below loop.
        uint256 bitsRemaining = 256;

        // Generate a random value and size for each variable.
        uint256[] memory vals = new uint256[](nvars);
        uint256[] memory sizes = new uint256[](nvars);
        uint256[] memory offsets = new uint256[](nvars);

        for (uint256 i = 0; i < nvars; i++) {
            // Generate a random value and size.
            offsets[i] = i == 0 ? 0 : offsets[i - 1] + sizes[i - 1];

            uint256 nvarsRemaining = nvars - i;
            uint256 maxVarSize = bitsRemaining - nvarsRemaining + 1;
            sizes[i] = bound(uint256(keccak256(abi.encodePacked(seed, i + 256))), 1, maxVarSize);
            bitsRemaining -= sizes[i];

            uint256 maxVal;
            uint256 varSize = sizes[i];
            assembly {
                // mask = (1 << varSize) - 1
                maxVal := sub(shl(varSize, 1), 1)
            }
            vals[i] = bound(uint256(keccak256(abi.encodePacked(seed, i))), 0, maxVal);
        }

        // Pack all values into the slot.
        for (uint256 i = 0; i < nvars; i++) {
            stdstore.enable_packed_slots().target(address(test)).sig("getRandomPacked(uint256,uint256)")
                .with_key(sizes[i]).with_key(offsets[i]).checked_write(vals[i]);
        }

        // Verify the read data matches.
        for (uint256 i = 0; i < nvars; i++) {
            uint256 readVal = stdstore.enable_packed_slots().target(address(test))
                .sig("getRandomPacked(uint256,uint256)").with_key(sizes[i]).with_key(offsets[i]).read_uint();

            uint256 retVal = test.getRandomPacked(sizes[i], offsets[i]);

            assertEq(readVal, vals[i]);
            assertEq(retVal, vals[i]);
        }
    }

    function testEdgeCaseArray() public {
        stdstore.target(address(test)).sig("edgeCaseArray(uint256)").with_key(uint256(0)).checked_write(1);
        assertEq(test.edgeCaseArray(0), 1);
    }

    // Regression test for https://github.com/foundry-rs/forge-std/issues/740
    // `find()` used to infinite-loop on tokens whose `balanceOf` reads multiple
    // storage slots and returns a derived value (reflection tokens).
    function test_RevertFindOnReflectionToken() public {
        MockReflectionToken token = new MockReflectionToken();
        ReflectionTokenTarget target = new ReflectionTokenTarget(token);
        vm.expectRevert("stdStorage find(StdStorage): Slot(s) not found.");
        target.findBalanceOf(address(this));
    }
}

contract StorageTestTarget {
    using stdStorage for StdStorage;

    StdStorage internal stdstore;
    StorageTest internal test;

    constructor(StorageTest test_) {
        test = test_;
    }

    function expectRevertStorageConst() public {
        stdstore.target(address(test)).sig("const()").find();
    }
}

contract ReflectionTokenTarget {
    using stdStorage for StdStorage;

    StdStorage internal stdstore;
    MockReflectionToken internal token;

    constructor(MockReflectionToken token_) {
        token = token_;
    }

    function findBalanceOf(address who) public {
        stdstore.target(address(token)).sig("balanceOf(address)").with_key(who).find();
    }
}

contract StorageTest {
    uint256 public exists = 1;
    mapping(address => uint256) public map_addr;
    mapping(uint256 => uint256) public map_uint;
    mapping(address => uint256) public map_packed;
    mapping(address => UnpackedStruct) public map_struct;
    mapping(address => mapping(address => uint256)) public deep_map;
    mapping(address => mapping(address => UnpackedStruct)) public deep_map_struct;
    UnpackedStruct public basic;

    uint248 public tA;
    bool public tB;

    bool public tC = false;
    uint248 public tD = 1;

    struct UnpackedStruct {
        uint256 a;
        uint256 b;
    }

    mapping(address => bool) public map_bool;

    bytes32 public tE = hex"1337";
    address public tF = address(1337);
    int256 public tG = type(int256).min;
    bool public tH = true;
    bytes32 private tI = ~bytes32(hex"1337");

    uint256 randomPacking;

    // Array with length matching values of elements.
    uint256[] public edgeCaseArray = [3, 3, 3];

    constructor() {
        basic = UnpackedStruct({a: 1337, b: 1337});

        uint256 two = (1 << 128) | 1;
        map_packed[msg.sender] = two;
        map_packed[address(uint160(1337))] = 1 << 128;
    }

    function read_struct_upper(address who) public view returns (uint256) {
        return map_packed[who] >> 128;
    }

    function read_struct_lower(address who) public view returns (uint256) {
        return map_packed[who] & ((1 << 128) - 1);
    }

    function hidden() public view returns (bytes32 t) {
        bytes32 slot = keccak256("my.random.var");
        assembly ("memory-safe") {
            t := sload(slot)
        }
    }

    function const() public pure returns (bytes32 t) {
        t = bytes32(hex"1337");
    }

    function extra_sload() public view returns (bytes32 t) {
        // trigger read on slot `tE`, and make a staticcall to make sure compiler doesn't optimize this SLOAD away
        assembly {
            pop(staticcall(gas(), sload(tE.slot), 0, 0, 0, 0))
        }
        t = tI;
    }

    function setRandomPacking(uint256 val) public {
        randomPacking = val;
    }

    function _getMask(uint256 size) internal pure returns (uint256 mask) {
        assembly {
            // mask = (1 << size) - 1
            mask := sub(shl(size, 1), 1)
        }
    }

    function setRandomPacking(uint256 val, uint256 size, uint256 offset) public {
        // Generate mask based on the size of the value
        uint256 mask = _getMask(size);
        // Zero out all bits for the word we're about to set
        uint256 cleanedWord = randomPacking & ~(mask << offset);
        // Place val in the correct spot of the cleaned word
        randomPacking = cleanedWord | val << offset;
    }

    function getRandomPacked(uint256 size, uint256 offset) public view returns (uint256) {
        // Generate mask based on the size of the value
        uint256 mask = _getMask(size);
        // Shift to place the bits in the correct position, and use mask to zero out remaining bits
        return (randomPacking >> offset) & mask;
    }

    function getRandomPacked(uint8 shifts, uint8[] memory shiftSizes, uint8 elem) public view returns (uint256) {
        require(elem < shifts, "!elem");
        uint256 leftBits;
        uint256 rightBits;

        for (uint256 i; i < shiftSizes.length; i++) {
            if (i < elem) {
                leftBits += shiftSizes[i];
            } else if (elem != i) {
                rightBits += shiftSizes[i];
            }
        }

        // we may have some right bits unaccounted for
        leftBits += 256 - (leftBits + shiftSizes[elem] + rightBits);

        // clear left bits, then clear right bits and realign
        return (randomPacking << leftBits) >> (leftBits + rightBits);
    }
}

// Minimal mock of a reflection token: `balanceOf` reads many storage slots
// and always returns a constant, so no single slot mutation can change its
// return value and stdStorage can never find a matching slot.
contract MockReflectionToken {
    uint256 internal _a = 1;
    uint256 internal _b = 2;
    uint256 internal _c = 3;
    mapping(address => uint256) internal _balances;

    constructor() {
        _balances[msg.sender] = 1000 ether;
    }

    // Reads _a, _b, _c, and _balances[account] but always returns a constant.
    // This means mutating any single slot won't change the return value.
    function balanceOf(address account) public view returns (uint256) {
        uint256 x = _a + _b + _c + _balances[account];
        x; // suppress unused warning
        return 42;
    }
}
