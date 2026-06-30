// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {StdCheats} from "../src/StdCheats.sol";
import {Test} from "../src/Test.sol";
import {stdJson} from "../src/StdJson.sol";
import {stdToml} from "../src/StdToml.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";

contract StdCheatsTest is Test {
    Bar test;

    using stdJson for string;

    function setUp() public {
        test = new Bar();
    }

    function test_Skip() public {
        vm.warp(100);
        skip(25);
        assertEq(block.timestamp, 125);
    }

    function test_Rewind() public {
        vm.warp(100);
        rewind(25);
        assertEq(block.timestamp, 75);
    }

    function test_Hoax() public {
        hoax(address(1337));
        test.bar{value: 100}(address(1337));
    }

    function test_HoaxOrigin() public {
        hoax(address(1337), address(1337));
        test.origin{value: 100}(address(1337));
    }

    function test_HoaxDifferentAddresses() public {
        hoax(address(1337), address(7331));
        test.origin{value: 100}(address(1337), address(7331));
    }

    function test_StartHoax() public {
        startHoax(address(1337));
        test.bar{value: 100}(address(1337));
        test.bar{value: 100}(address(1337));
        vm.stopPrank();
        test.bar(address(this));
    }

    function test_StartHoaxOrigin() public {
        startHoax(address(1337), address(1337));
        test.origin{value: 100}(address(1337));
        test.origin{value: 100}(address(1337));
        vm.stopPrank();
        test.bar(address(this));
    }

    function test_ChangePrankMsgSender() public {
        vm.startPrank(address(1337));
        test.bar(address(1337));
        changePrank(address(0xdead));
        test.bar(address(0xdead));
        changePrank(address(1337));
        test.bar(address(1337));
        vm.stopPrank();
    }

    function test_ChangePrankMsgSenderAndTxOrigin() public {
        vm.startPrank(address(1337), address(1338));
        test.origin(address(1337), address(1338));
        changePrank(address(0xdead), address(0xbeef));
        test.origin(address(0xdead), address(0xbeef));
        changePrank(address(1337), address(1338));
        test.origin(address(1337), address(1338));
        vm.stopPrank();
    }

    function test_MakeAccountEquivalence() public {
        Account memory account = makeAccount("1337");
        (address addr, uint256 key) = makeAddrAndKey("1337");
        assertEq(account.addr, addr);
        assertEq(account.key, key);
    }

    function test_MakeAddrEquivalence() public {
        (address addr,) = makeAddrAndKey("1337");
        assertEq(makeAddr("1337"), addr);
    }

    function test_MakeAddrSigning() public {
        (address addr, uint256 key) = makeAddrAndKey("1337");
        bytes32 hash = keccak256("some_message");

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, hash);
        assertEq(ecrecover(hash, v, r, s), addr);
    }

    function test_Deal() public {
        deal(address(this), 1 ether);
        assertEq(address(this).balance, 1 ether);
    }

    function test_DealToken() public {
        Bar barToken = new Bar();
        address bar = address(barToken);
        deal(bar, address(this), 10000e18);
        assertEq(barToken.balanceOf(address(this)), 10000e18);
    }

    function test_DealTokenAdjustTotalSupply() public {
        Bar barToken = new Bar();
        address bar = address(barToken);
        deal(bar, address(this), 10000e18, true);
        assertEq(barToken.balanceOf(address(this)), 10000e18);
        assertEq(barToken.totalSupply(), 20000e18);
        deal(bar, address(this), 0, true);
        assertEq(barToken.balanceOf(address(this)), 0);
        assertEq(barToken.totalSupply(), 10000e18);
    }

    function test_DealERC1155Token() public {
        BarERC1155 barToken = new BarERC1155();
        address bar = address(barToken);
        dealERC1155(bar, address(this), 0, 10000e18, false);
        assertEq(barToken.balanceOf(address(this), 0), 10000e18);
    }

    function test_DealERC1155TokenAdjustTotalSupply() public {
        BarERC1155 barToken = new BarERC1155();
        address bar = address(barToken);
        dealERC1155(bar, address(this), 0, 10000e18, true);
        assertEq(barToken.balanceOf(address(this), 0), 10000e18);
        assertEq(barToken.totalSupply(0), 20000e18);
        dealERC1155(bar, address(this), 0, 0, true);
        assertEq(barToken.balanceOf(address(this), 0), 0);
        assertEq(barToken.totalSupply(0), 10000e18);
    }

    function test_DealERC721Token() public {
        BarERC721 barToken = new BarERC721();
        address bar = address(barToken);
        dealERC721(bar, address(2), 1);
        assertEq(barToken.balanceOf(address(2)), 1);
        assertEq(barToken.balanceOf(address(1)), 0);
        dealERC721(bar, address(1), 2);
        assertEq(barToken.balanceOf(address(1)), 1);
        assertEq(barToken.balanceOf(bar), 1);
    }

    function test_DeployCode() public {
        address deployed = deployCode("StdCheats.t.sol:Bar", bytes(""));
        assertEq(string(getCode(deployed)), string(getCode(address(test))));
    }

    function test_DestroyAccount() public {
        // deploy something to destroy it
        BarERC721 barToken = new BarERC721();
        address bar = address(barToken);
        vm.setNonce(bar, 10);
        deal(bar, 100);

        uint256 prevThisBalance = address(this).balance;
        uint256 size;
        assembly {
            size := extcodesize(bar)
        }

        assertGt(size, 0);
        assertEq(bar.balance, 100);
        assertEq(vm.getNonce(bar), 10);

        destroyAccount(bar, address(this));
        assembly {
            size := extcodesize(bar)
        }
        assertEq(address(this).balance, prevThisBalance + 100);
        assertEq(vm.getNonce(bar), 0);
        assertEq(size, 0);
        assertEq(bar.balance, 0);
    }

    function test_DeployCodeNoArgs() public {
        address deployed = deployCode("StdCheats.t.sol:Bar");
        assertEq(string(getCode(deployed)), string(getCode(address(test))));
    }

    function test_DeployCodeVal() public {
        address deployed = deployCode("StdCheats.t.sol:Bar", bytes(""), 1 ether);
        assertEq(string(getCode(deployed)), string(getCode(address(test))));
        assertEq(deployed.balance, 1 ether);
    }

    function test_DeployCodeValNoArgs() public {
        address deployed = deployCode("StdCheats.t.sol:Bar", 1 ether);
        assertEq(string(getCode(deployed)), string(getCode(address(test))));
        assertEq(deployed.balance, 1 ether);
    }

    // We need this so we can call "this.deployCode" rather than "deployCode" directly
    function deployCodeHelper(string memory what) external {
        deployCode(what);
    }

    function test_RevertIf_DeployCodeFail() public {
        vm.expectRevert(bytes("StdCheats deployCode(string): Deployment failed."));
        this.deployCodeHelper("StdCheats.t.sol:RevertingContract");
    }

    function getCode(address who) internal view returns (bytes memory o_code) {
        assembly ("memory-safe") {
            // retrieve the size of the code, this needs assembly
            let size := extcodesize(who)
            // allocate output byte array - this could also be done without assembly
            // by using o_code = new bytes(size)
            o_code := mload(0x40)
            // new "memory end" including padding
            mstore(0x40, add(o_code, and(add(add(size, 0x20), 0x1f), not(0x1f))))
            // store length in memory
            mstore(o_code, size)
            // actually retrieve the code, this needs assembly
            extcodecopy(who, add(o_code, 0x20), 0, size)
        }
    }

    function test_DeriveRememberKey() public {
        string memory mnemonic = "test test test test test test test test test test test junk";

        (address deployer, uint256 privateKey) = deriveRememberKey(mnemonic, 0);
        assertEq(deployer, 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266);
        assertEq(privateKey, 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80);
    }

    function test_BytesToUint() public pure {
        assertEq(3, bytesToUint_test(hex"03"));
        assertEq(2, bytesToUint_test(hex"02"));
        assertEq(255, bytesToUint_test(hex"ff"));
        assertEq(29625, bytesToUint_test(hex"73b9"));
    }

    function test_ParseJsonTxDetail() public view {
        string memory root = vm.projectRoot();
        string memory path = string.concat(root, "/test/fixtures/broadcast.log.json");
        string memory json = vm.readFile(path);
        bytes memory transactionDetails = json.parseRaw(".transactions[0].tx");
        RawTx1559Detail memory rawTxDetail = abi.decode(transactionDetails, (RawTx1559Detail));
        Tx1559Detail memory txDetail = rawToConvertedEIP1559Detail(rawTxDetail);
        assertEq(txDetail.from, 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266);
        assertEq(txDetail.to, 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512);
        assertEq(
            txDetail.data,
            hex"23e99187000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000013370000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000004"
        );
        assertEq(txDetail.nonce, 3);
        assertEq(txDetail.txType, 2);
        assertEq(txDetail.gas, 29625);
        assertEq(txDetail.value, 0);
    }

    function test_ReadEIP1559Transaction() public view {
        string memory root = vm.projectRoot();
        string memory path = string.concat(root, "/test/fixtures/broadcast.log.json");
        uint256 index = 0;
        Tx1559 memory transaction = readTx1559(path, index);
        transaction;
    }

    function test_ReadEIP1559Transactions() public view {
        string memory root = vm.projectRoot();
        string memory path = string.concat(root, "/test/fixtures/broadcast.log.json");
        Tx1559[] memory transactions = readTx1559s(path);
        transactions;
    }

    function test_ReadReceipt() public view {
        string memory root = vm.projectRoot();
        string memory path = string.concat(root, "/test/fixtures/broadcast.log.json");
        uint256 index = 5;
        Receipt memory receipt = readReceipt(path, index);
        assertEq(
            receipt.logsBloom,
            hex"00000000000800000000000000000010000000000000000000000000000180000000000000000000000000000000000000000000000008000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100"
        );
    }

    function test_ReadReceipts() public view {
        string memory root = vm.projectRoot();
        string memory path = string.concat(root, "/test/fixtures/broadcast.log.json");
        Receipt[] memory receipts = readReceipts(path);
        receipts;
    }

    function test_GasMeteringModifier() public {
        uint256 gas_start_normal = gasleft();
        addInLoop();
        uint256 gas_used_normal = gas_start_normal - gasleft();

        uint256 gas_start_single = gasleft();
        addInLoopNoGas();
        uint256 gas_used_single = gas_start_single - gasleft();

        uint256 gas_start_double = gasleft();
        addInLoopNoGasNoGas();
        uint256 gas_used_double = gas_start_double - gasleft();

        assertTrue(gas_used_double + gas_used_single < gas_used_normal);
    }

    function addInLoop() internal pure returns (uint256) {
        uint256 b;
        for (uint256 i; i < 10000; i++) {
            b += i;
        }
        return b;
    }

    function addInLoopNoGas() internal noGasMetering returns (uint256) {
        return addInLoop();
    }

    function addInLoopNoGasNoGas() internal noGasMetering returns (uint256) {
        return addInLoopNoGas();
    }

    function bytesToUint_test(bytes memory b) private pure returns (uint256) {
        uint256 number;
        for (uint256 i = 0; i < b.length; i++) {
            number = number + uint256(uint8(b[i])) * (2 ** (8 * (b.length - (i + 1))));
        }
        return number;
    }

    function testFuzz_AssumeAddressIsNot(address addr) external {
        // skip over Payable and NonPayable enums
        for (uint8 i = 2; i < uint8(type(AddressType).max); i++) {
            assumeAddressIsNot(addr, AddressType(i));
        }
        assertTrue(addr != address(0));
        assertTrue(addr < address(1) || addr > address(9));
        assertTrue(addr != address(vm) || addr != 0x000000000000000000636F6e736F6c652e6c6f67);
    }

    function test_AssumePayable() external {
        // We deploy a mock version so we can properly test the revert.
        StdCheatsMock stdCheatsMock = new StdCheatsMock();

        // all should revert since these addresses are not payable

        // VM address
        vm.expectRevert();
        stdCheatsMock.exposedAssumePayable(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

        // Console address
        vm.expectRevert();
        stdCheatsMock.exposedAssumePayable(0x000000000000000000636F6e736F6c652e6c6f67);

        // Create2Deployer
        vm.expectRevert();
        stdCheatsMock.exposedAssumePayable(0x4e59b44847b379578588920cA78FbF26c0B4956C);

        // all should pass since these addresses are payable

        // vitalik.eth
        stdCheatsMock.exposedAssumePayable(0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045);

        // mock payable contract
        MockContractPayable cp = new MockContractPayable();
        stdCheatsMock.exposedAssumePayable(address(cp));
    }

    function test_AssumeNotPayable() external {
        // We deploy a mock version so we can properly test the revert.
        StdCheatsMock stdCheatsMock = new StdCheatsMock();

        // all should pass since these addresses are not payable

        // VM address
        stdCheatsMock.exposedAssumeNotPayable(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

        // Console address
        stdCheatsMock.exposedAssumeNotPayable(0x000000000000000000636F6e736F6c652e6c6f67);

        // Create2Deployer
        stdCheatsMock.exposedAssumeNotPayable(0x4e59b44847b379578588920cA78FbF26c0B4956C);

        // all should revert since these addresses are payable

        // vitalik.eth
        vm.expectRevert();
        stdCheatsMock.exposedAssumeNotPayable(0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045);

        // mock payable contract
        MockContractPayable cp = new MockContractPayable();
        vm.expectRevert();
        stdCheatsMock.exposedAssumeNotPayable(address(cp));
    }

    function testFuzz_AssumeNotPrecompile(address addr) external {
        assumeNotPrecompile(addr, getChain("optimism_sepolia").chainId);
        assertTrue(
            addr < address(1) || (addr > address(9) && addr < address(0x4200000000000000000000000000000000000000))
                || addr > address(0x4200000000000000000000000000000000000800)
        );
    }

    function testFuzz_AssumeNotForgeAddress(address addr) external pure {
        assumeNotForgeAddress(addr);
        assertTrue(
            addr != address(vm) && addr != 0x000000000000000000636F6e736F6c652e6c6f67
                && addr != 0x4e59b44847b379578588920cA78FbF26c0B4956C
        );
    }

    function test_RevertIf_CannotDeployCodeTo() external {
        vm.expectRevert("StdCheats deployCodeTo(string,bytes,uint256,address): Failed to create runtime bytecode.");
        this._revertDeployCodeTo();
    }

    function _revertDeployCodeTo() external {
        deployCodeTo("StdCheats.t.sol:RevertingContract", address(0));
    }

    function test_DeployCodeTo() external {
        address arbitraryAddress = makeAddr("arbitraryAddress");

        deployCodeTo(
            "StdCheats.t.sol:MockContractWithConstructorArgs",
            abi.encode(uint256(6), true, bytes20(arbitraryAddress)),
            1 ether,
            arbitraryAddress
        );

        MockContractWithConstructorArgs ct = MockContractWithConstructorArgs(arbitraryAddress);

        assertEq(arbitraryAddress.balance, 1 ether);
        assertEq(ct.x(), 6);
        assertTrue(ct.y());
        assertEq(ct.z(), bytes20(arbitraryAddress));
    }
}

contract StdCheatsMock is StdCheats {
    function exposedAssumePayable(address addr) external {
        assumePayable(addr);
    }

    function exposedAssumeNotPayable(address addr) external {
        assumeNotPayable(addr);
    }

    // We deploy a mock version so we can properly test expected reverts.
    function exposedAssumeNotBlacklisted(address token, address addr) external view {
        return assumeNotBlacklisted(token, addr);
    }
}

contract StdCheatsForkTest is Test {
    address internal constant USDC_BLACKLISTED_USER = 0x1E34A77868E19A6647b1f2F47B51ed72dEDE95DD;
    address internal constant USDT_BLACKLISTED_USER = 0x8f8a8F4B54a2aAC7799d7bc81368aC27b852822A;

    MockUSDT public USDT;
    MockUSDC public USDC;

    function setUp() public {
        USDT = new MockUSDT();
        USDC = new MockUSDC();

        USDC.setBlacklisted(USDC_BLACKLISTED_USER, true);
        USDT.setBlacklisted(USDT_BLACKLISTED_USER, true);
    }

    function test_RevertIf_CannotAssumeNoBlacklisted_EOA() external {
        // We deploy a mock version so we can properly test the revert.
        StdCheatsMock stdCheatsMock = new StdCheatsMock();
        address eoa = vm.addr({privateKey: 1});
        vm.expectRevert("StdCheats assumeNotBlacklisted(address,address): Token address is not a contract.");
        stdCheatsMock.exposedAssumeNotBlacklisted(eoa, address(0));
    }

    function testFuzz_AssumeNotBlacklisted_TokenWithoutBlacklist(address addr) external view {
        assumeNotBlacklisted(address(USDC), addr);
        assumeNotBlacklisted(address(USDT), addr);
        assertTrue(true);
    }

    function test_RevertIf_AssumeNoBlacklisted_USDC() external {
        // We deploy a mock version so we can properly test the revert.
        StdCheatsMock stdCheatsMock = new StdCheatsMock();
        vm.expectRevert();
        stdCheatsMock.exposedAssumeNotBlacklisted(address(USDC), USDC_BLACKLISTED_USER);
    }

    function testFuzz_AssumeNotBlacklisted_USDC(address addr) external view {
        assumeNotBlacklisted(address(USDC), addr);
        assertFalse(USDCLike(USDC).isBlacklisted(addr));
    }

    function test_RevertIf_AssumeNoBlacklisted_USDT() external {
        // We deploy a mock version so we can properly test the revert.
        StdCheatsMock stdCheatsMock = new StdCheatsMock();
        vm.expectRevert();
        stdCheatsMock.exposedAssumeNotBlacklisted(address(USDT), USDT_BLACKLISTED_USER);
    }

    function testFuzz_AssumeNotBlacklisted_USDT(address addr) external view {
        assumeNotBlacklisted(address(USDT), addr);
        assertFalse(USDTLike(USDT).isBlackListed(addr));
    }
}

/// @dev https://etherscan.io/token/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48#readProxyContract
interface USDCLike {
    function isBlacklisted(address) external view returns (bool);
}

/// @dev https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7#readContract
interface USDTLike {
    function isBlackListed(address) external view returns (bool);
}

contract MockUSDT is USDTLike {
    mapping(address => bool) private blacklist;

    function isBlackListed(address addr) external view returns (bool) {
        return blacklist[addr];
    }

    function setBlacklisted(address addr, bool value) external {
        blacklist[addr] = value;
    }
}

contract MockUSDC is USDCLike {
    mapping(address => bool) private blacklist;

    function isBlacklisted(address addr) external view returns (bool) {
        return blacklist[addr];
    }

    function setBlacklisted(address addr, bool value) external {
        blacklist[addr] = value;
    }
}

contract Bar {
    constructor() payable {
        /// `DEAL` STDCHEAT
        totalSupply = 10000e18;
        balanceOf[address(this)] = totalSupply;
    }

    /// `HOAX` and `CHANGEPRANK` STDCHEATS
    function bar(address expectedSender) public payable {
        require(msg.sender == expectedSender, "!prank");
    }

    function origin(address expectedSender) public payable {
        require(msg.sender == expectedSender, "!prank");
        require(tx.origin == expectedSender, "!prank");
    }

    function origin(address expectedSender, address expectedOrigin) public payable {
        require(msg.sender == expectedSender, "!prank");
        require(tx.origin == expectedOrigin, "!prank");
    }

    /// `DEAL` STDCHEAT
    mapping(address => uint256) public balanceOf;
    uint256 public totalSupply;
}

contract BarERC1155 {
    constructor() payable {
        /// `DEALERC1155` STDCHEAT
        _totalSupply[0] = 10000e18;
        _balances[0][address(this)] = _totalSupply[0];
    }

    function balanceOf(address account, uint256 id) public view virtual returns (uint256) {
        return _balances[id][account];
    }

    function totalSupply(uint256 id) public view virtual returns (uint256) {
        return _totalSupply[id];
    }

    /// `DEALERC1155` STDCHEAT
    mapping(uint256 => mapping(address => uint256)) private _balances;
    mapping(uint256 => uint256) private _totalSupply;
}

contract BarERC721 {
    constructor() payable {
        /// `DEALERC721` STDCHEAT
        _owners[1] = address(1);
        _balances[address(1)] = 1;
        _owners[2] = address(this);
        _owners[3] = address(this);
        _balances[address(this)] = 2;
    }

    function balanceOf(address owner) public view virtual returns (uint256) {
        return _balances[owner];
    }

    function ownerOf(uint256 tokenId) public view virtual returns (address) {
        address owner = _owners[tokenId];
        return owner;
    }

    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
}

contract RevertingContract {
    constructor() {
        revert();
    }
}

contract MockContractWithConstructorArgs {
    uint256 public immutable x;
    bool public y;
    bytes20 public z;

    constructor(uint256 _x, bool _y, bytes20 _z) payable {
        x = _x;
        y = _y;
        z = _z;
    }
}

contract MockContractPayable {
    receive() external payable {}
}
