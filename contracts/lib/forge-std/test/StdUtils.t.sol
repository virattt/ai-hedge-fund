// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {Test, StdUtils} from "../src/Test.sol";

contract StdUtilsMock is StdUtils {
    // We deploy a mock version so we can properly test expected reverts.
    function exposedGetTokenBalances(address token, address[] memory addresses)
        external
        returns (uint256[] memory balances)
    {
        return getTokenBalances(token, addresses);
    }

    function exposedBound(int256 num, int256 min, int256 max) external pure returns (int256) {
        return bound(num, min, max);
    }

    function exposedBound(uint256 num, uint256 min, uint256 max) external pure returns (uint256) {
        return bound(num, min, max);
    }

    function exposedBytesToUint(bytes memory b) external pure returns (uint256) {
        return bytesToUint(b);
    }
}

contract StdUtilsTest is Test {
    /*//////////////////////////////////////////////////////////////////////////
                                     BOUND UINT
    //////////////////////////////////////////////////////////////////////////*/

    function test_Bound() public pure {
        assertEq(bound(uint256(5), 0, 4), 0);
        assertEq(bound(uint256(0), 69, 69), 69);
        assertEq(bound(uint256(0), 68, 69), 68);
        assertEq(bound(uint256(10), 150, 190), 174);
        assertEq(bound(uint256(300), 2800, 3200), 3107);
        assertEq(bound(uint256(9999), 1337, 6666), 4669);
    }

    function test_Bound_WithinRange() public pure {
        assertEq(bound(uint256(51), 50, 150), 51);
        assertEq(bound(uint256(51), 50, 150), bound(bound(uint256(51), 50, 150), 50, 150));
        assertEq(bound(uint256(149), 50, 150), 149);
        assertEq(bound(uint256(149), 50, 150), bound(bound(uint256(149), 50, 150), 50, 150));
    }

    function test_Bound_EdgeCoverage() public pure {
        assertEq(bound(uint256(0), 50, 150), 50);
        assertEq(bound(uint256(1), 50, 150), 51);
        assertEq(bound(uint256(2), 50, 150), 52);
        assertEq(bound(uint256(3), 50, 150), 53);
        assertEq(bound(type(uint256).max, 50, 150), 150);
        assertEq(bound(type(uint256).max - 1, 50, 150), 149);
        assertEq(bound(type(uint256).max - 2, 50, 150), 148);
        assertEq(bound(type(uint256).max - 3, 50, 150), 147);
    }

    function testFuzz_Bound_DistributionIsEven(uint256 min, uint256 size) public pure {
        size = size % 100 + 1;
        min = bound(min, UINT256_MAX / 2, UINT256_MAX / 2 + size);
        uint256 max = min + size - 1;
        uint256 result;

        for (uint256 i = 1; i <= size * 4; ++i) {
            // x > max
            result = bound(max + i, min, max);
            assertEq(result, min + (i - 1) % size);
            // x < min
            result = bound(min - i, min, max);
            assertEq(result, max - (i - 1) % size);
        }
    }

    function testFuzz_Bound(uint256 num, uint256 min, uint256 max) public pure {
        if (min > max) (min, max) = (max, min);

        uint256 result = bound(num, min, max);

        assertGe(result, min);
        assertLe(result, max);
        assertEq(result, bound(result, min, max));
        if (num >= min && num <= max) assertEq(result, num);
    }

    function test_BoundUint256Max() public pure {
        assertEq(bound(0, type(uint256).max - 1, type(uint256).max), type(uint256).max - 1);
        assertEq(bound(1, type(uint256).max - 1, type(uint256).max), type(uint256).max);
    }

    function test_RevertIf_BoundMaxLessThanMin() public {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        vm.expectRevert(bytes("StdUtils bound(uint256,uint256,uint256): Max is less than min."));
        stdUtils.exposedBound(uint256(5), 100, 10);
    }

    function testFuzz_RevertIf_BoundMaxLessThanMin(uint256 num, uint256 min, uint256 max) public {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        vm.assume(min > max);
        vm.expectRevert(bytes("StdUtils bound(uint256,uint256,uint256): Max is less than min."));
        stdUtils.exposedBound(num, min, max);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                     BOUND INT
    //////////////////////////////////////////////////////////////////////////*/

    function test_BoundInt() public pure {
        assertEq(bound(-3, 0, 4), 2);
        assertEq(bound(0, -69, -69), -69);
        assertEq(bound(0, -69, -68), -68);
        assertEq(bound(-10, 150, 190), 154);
        assertEq(bound(-300, 2800, 3200), 2908);
        assertEq(bound(9999, -1337, 6666), 1995);
    }

    function test_BoundInt_WithinRange() public pure {
        assertEq(bound(51, -50, 150), 51);
        assertEq(bound(51, -50, 150), bound(bound(51, -50, 150), -50, 150));
        assertEq(bound(149, -50, 150), 149);
        assertEq(bound(149, -50, 150), bound(bound(149, -50, 150), -50, 150));
    }

    function test_BoundInt_EdgeCoverage() public pure {
        assertEq(bound(type(int256).min, -50, 150), -50);
        assertEq(bound(type(int256).min + 1, -50, 150), -49);
        assertEq(bound(type(int256).min + 2, -50, 150), -48);
        assertEq(bound(type(int256).min + 3, -50, 150), -47);
        assertEq(bound(type(int256).min, 10, 150), 10);
        assertEq(bound(type(int256).min + 1, 10, 150), 11);
        assertEq(bound(type(int256).min + 2, 10, 150), 12);
        assertEq(bound(type(int256).min + 3, 10, 150), 13);

        assertEq(bound(type(int256).max, -50, 150), 150);
        assertEq(bound(type(int256).max - 1, -50, 150), 149);
        assertEq(bound(type(int256).max - 2, -50, 150), 148);
        assertEq(bound(type(int256).max - 3, -50, 150), 147);
        assertEq(bound(type(int256).max, -50, -10), -10);
        assertEq(bound(type(int256).max - 1, -50, -10), -11);
        assertEq(bound(type(int256).max - 2, -50, -10), -12);
        assertEq(bound(type(int256).max - 3, -50, -10), -13);
    }

    function testFuzz_BoundInt_DistributionIsEven(int256 min, uint256 size) public pure {
        size = size % 100 + 1;
        min = bound(min, -int256(size / 2), int256(size - size / 2));
        int256 max = min + int256(size) - 1;
        int256 result;

        for (uint256 i = 1; i <= size * 4; ++i) {
            // x > max
            result = bound(max + int256(i), min, max);
            assertEq(result, min + int256((i - 1) % size));
            // x < min
            result = bound(min - int256(i), min, max);
            assertEq(result, max - int256((i - 1) % size));
        }
    }

    function testFuzz_BoundInt(int256 num, int256 min, int256 max) public pure {
        if (min > max) (min, max) = (max, min);

        int256 result = bound(num, min, max);

        assertGe(result, min);
        assertLe(result, max);
        assertEq(result, bound(result, min, max));
        if (num >= min && num <= max) assertEq(result, num);
    }

    function test_BoundIntInt256Max() public pure {
        assertEq(bound(0, type(int256).max - 1, type(int256).max), type(int256).max - 1);
        assertEq(bound(1, type(int256).max - 1, type(int256).max), type(int256).max);
    }

    function test_BoundIntInt256Min() public pure {
        assertEq(bound(0, type(int256).min, type(int256).min + 1), type(int256).min);
        assertEq(bound(1, type(int256).min, type(int256).min + 1), type(int256).min + 1);
    }

    function test_RevertIf_BoundIntMaxLessThanMin() public {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        vm.expectRevert(bytes("StdUtils bound(int256,int256,int256): Max is less than min."));
        stdUtils.exposedBound(-5, 100, 10);
    }

    function testFuzz_RevertIf_BoundIntMaxLessThanMin(int256 num, int256 min, int256 max) public {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        vm.assume(min > max);
        vm.expectRevert(bytes("StdUtils bound(int256,int256,int256): Max is less than min."));
        stdUtils.exposedBound(num, min, max);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                BOUND PRIVATE KEY
    //////////////////////////////////////////////////////////////////////////*/

    function test_BoundPrivateKey() public pure {
        assertEq(boundPrivateKey(0), 1);
        assertEq(boundPrivateKey(1), 1);
        assertEq(boundPrivateKey(300), 300);
        assertEq(boundPrivateKey(9999), 9999);
        assertEq(boundPrivateKey(SECP256K1_ORDER - 1), SECP256K1_ORDER - 1);
        assertEq(boundPrivateKey(SECP256K1_ORDER), 1);
        assertEq(boundPrivateKey(SECP256K1_ORDER + 1), 2);
        assertEq(boundPrivateKey(UINT256_MAX), UINT256_MAX & SECP256K1_ORDER - 1); // x&y is equivalent to x-x%y
    }

    /*//////////////////////////////////////////////////////////////////////////
                                   BYTES TO UINT
    //////////////////////////////////////////////////////////////////////////*/

    function test_BytesToUint() external pure {
        bytes memory maxUint = hex"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
        bytes memory two = hex"02";
        bytes memory millionEther = hex"d3c21bcecceda1000000";

        assertEq(bytesToUint(maxUint), type(uint256).max);
        assertEq(bytesToUint(two), 2);
        assertEq(bytesToUint(millionEther), 1_000_000 ether);
    }

    function test_RevertIf_BytesLengthExceeds32() external {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        bytes memory thirty3Bytes = hex"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
        vm.expectRevert("StdUtils bytesToUint(bytes): Bytes length exceeds 32.");
        stdUtils.exposedBytesToUint(thirty3Bytes);
    }

    /*//////////////////////////////////////////////////////////////////////////
                               COMPUTE CREATE ADDRESS
    //////////////////////////////////////////////////////////////////////////*/

    function test_ComputeCreateAddress() external pure {
        address deployer = 0x6C9FC64A53c1b71FB3f9Af64d1ae3A4931A5f4E9;
        uint256 nonce = 14;
        address createAddress = computeCreateAddress(deployer, nonce);
        assertEq(createAddress, 0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45);
    }

    /*//////////////////////////////////////////////////////////////////////////
                              COMPUTE CREATE2 ADDRESS
    //////////////////////////////////////////////////////////////////////////*/

    function test_ComputeCreate2Address() external pure {
        bytes32 salt = bytes32(uint256(31415));
        bytes32 initcodeHash = keccak256(abi.encode(0x6080));
        address deployer = 0x6C9FC64A53c1b71FB3f9Af64d1ae3A4931A5f4E9;
        address create2Address = computeCreate2Address(salt, initcodeHash, deployer);
        assertEq(create2Address, 0xB147a5d25748fda14b463EB04B111027C290f4d3);
    }

    function test_ComputeCreate2AddressWithDefaultDeployer() external pure {
        bytes32 salt = 0xc290c670fde54e5ef686f9132cbc8711e76a98f0333a438a92daa442c71403c0;
        bytes32 initcodeHash = hashInitCode(hex"6080", "");
        assertEq(initcodeHash, 0x1a578b7a4b0b5755db6d121b4118d4bc68fe170dca840c59bc922f14175a76b0);
        address create2Address = computeCreate2Address(salt, initcodeHash);
        assertEq(create2Address, 0xc0ffEe2198a06235aAbFffe5Db0CacF1717f5Ac6);
    }
}

contract StdUtilsForkTest is Test {
    /*//////////////////////////////////////////////////////////////////////////
                                  GET TOKEN BALANCES
    //////////////////////////////////////////////////////////////////////////*/

    address internal SHIB = 0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE;
    address internal SHIB_HOLDER_0 = 0x855F5981e831D83e6A4b4EBFCAdAa68D92333170;
    address internal SHIB_HOLDER_1 = 0x8F509A90c2e47779cA408Fe00d7A72e359229AdA;
    address internal SHIB_HOLDER_2 = 0x0e3bbc0D04fF62211F71f3e4C45d82ad76224385;

    address internal USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address internal USDC_HOLDER_0 = 0xDa9CE944a37d218c3302F6B82a094844C6ECEb17;
    address internal USDC_HOLDER_1 = 0x3e67F4721E6d1c41a015f645eFa37BEd854fcf52;

    function setUp() public {
        // All tests of the `getTokenBalances` method are fork tests using live contracts.
        vm.createSelectFork({urlOrAlias: "mainnet", blockNumber: 16_428_900});
    }

    function test_RevertIf_CannotGetTokenBalances_NonTokenContract() external {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        // The UniswapV2Factory contract has neither a `balanceOf` function nor a fallback function,
        // so the `balanceOf` call should revert.
        address token = address(0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f);
        address[] memory addresses = new address[](1);
        addresses[0] = USDC_HOLDER_0;

        vm.expectRevert("Multicall3: call failed");
        stdUtils.exposedGetTokenBalances(token, addresses);
    }

    function test_RevertIf_CannotGetTokenBalances_EOA() external {
        // We deploy a mock version so we can properly test the revert.
        StdUtilsMock stdUtils = new StdUtilsMock();

        address eoa = vm.addr({privateKey: 1});
        address[] memory addresses = new address[](1);
        addresses[0] = USDC_HOLDER_0;
        vm.expectRevert("StdUtils getTokenBalances(address,address[]): Token address is not a contract.");
        stdUtils.exposedGetTokenBalances(eoa, addresses);
    }

    function test_GetTokenBalances_Empty() external {
        address[] memory addresses = new address[](0);
        uint256[] memory balances = getTokenBalances(USDC, addresses);
        assertEq(balances.length, 0);
    }

    function test_GetTokenBalances_USDC() external {
        address[] memory addresses = new address[](2);
        addresses[0] = USDC_HOLDER_0;
        addresses[1] = USDC_HOLDER_1;
        uint256[] memory balances = getTokenBalances(USDC, addresses);
        assertEq(balances[0], 159_000_000_000_000);
        assertEq(balances[1], 131_350_000_000_000);
    }

    function test_GetTokenBalances_SHIB() external {
        address[] memory addresses = new address[](3);
        addresses[0] = SHIB_HOLDER_0;
        addresses[1] = SHIB_HOLDER_1;
        addresses[2] = SHIB_HOLDER_2;
        uint256[] memory balances = getTokenBalances(SHIB, addresses);
        assertEq(balances[0], 3_323_256_285_484.42e18);
        assertEq(balances[1], 1_271_702_771_149.99999928e18);
        assertEq(balances[2], 606_357_106_247e18);
    }
}
