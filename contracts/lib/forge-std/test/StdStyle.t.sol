// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {Test, console2, StdStyle} from "../src/Test.sol";

contract StdStyleTest is Test {
    function test_StyleColor() public pure {
        console2.log(StdStyle.red("StdStyle.red String Test"));
        console2.log(StdStyle.red(uint256(10e18)));
        console2.log(StdStyle.red(int256(-10e18)));
        console2.log(StdStyle.red(true));
        console2.log(StdStyle.red(address(0)));
        console2.log(StdStyle.redBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.redBytes32("StdStyle.redBytes32"));
        console2.log(StdStyle.green("StdStyle.green String Test"));
        console2.log(StdStyle.green(uint256(10e18)));
        console2.log(StdStyle.green(int256(-10e18)));
        console2.log(StdStyle.green(true));
        console2.log(StdStyle.green(address(0)));
        console2.log(StdStyle.greenBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.greenBytes32("StdStyle.greenBytes32"));
        console2.log(StdStyle.yellow("StdStyle.yellow String Test"));
        console2.log(StdStyle.yellow(uint256(10e18)));
        console2.log(StdStyle.yellow(int256(-10e18)));
        console2.log(StdStyle.yellow(true));
        console2.log(StdStyle.yellow(address(0)));
        console2.log(StdStyle.yellowBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.yellowBytes32("StdStyle.yellowBytes32"));
        console2.log(StdStyle.blue("StdStyle.blue String Test"));
        console2.log(StdStyle.blue(uint256(10e18)));
        console2.log(StdStyle.blue(int256(-10e18)));
        console2.log(StdStyle.blue(true));
        console2.log(StdStyle.blue(address(0)));
        console2.log(StdStyle.blueBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.blueBytes32("StdStyle.blueBytes32"));
        console2.log(StdStyle.magenta("StdStyle.magenta String Test"));
        console2.log(StdStyle.magenta(uint256(10e18)));
        console2.log(StdStyle.magenta(int256(-10e18)));
        console2.log(StdStyle.magenta(true));
        console2.log(StdStyle.magenta(address(0)));
        console2.log(StdStyle.magentaBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.magentaBytes32("StdStyle.magentaBytes32"));
        console2.log(StdStyle.cyan("StdStyle.cyan String Test"));
        console2.log(StdStyle.cyan(uint256(10e18)));
        console2.log(StdStyle.cyan(int256(-10e18)));
        console2.log(StdStyle.cyan(true));
        console2.log(StdStyle.cyan(address(0)));
        console2.log(StdStyle.cyanBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.cyanBytes32("StdStyle.cyanBytes32"));
    }

    function test_StyleFontWeight() public pure {
        console2.log(StdStyle.bold("StdStyle.bold String Test"));
        console2.log(StdStyle.bold(uint256(10e18)));
        console2.log(StdStyle.bold(int256(-10e18)));
        console2.log(StdStyle.bold(address(0)));
        console2.log(StdStyle.bold(true));
        console2.log(StdStyle.boldBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.boldBytes32("StdStyle.boldBytes32"));
        console2.log(StdStyle.dim("StdStyle.dim String Test"));
        console2.log(StdStyle.dim(uint256(10e18)));
        console2.log(StdStyle.dim(int256(-10e18)));
        console2.log(StdStyle.dim(address(0)));
        console2.log(StdStyle.dim(true));
        console2.log(StdStyle.dimBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.dimBytes32("StdStyle.dimBytes32"));
        console2.log(StdStyle.italic("StdStyle.italic String Test"));
        console2.log(StdStyle.italic(uint256(10e18)));
        console2.log(StdStyle.italic(int256(-10e18)));
        console2.log(StdStyle.italic(address(0)));
        console2.log(StdStyle.italic(true));
        console2.log(StdStyle.italicBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.italicBytes32("StdStyle.italicBytes32"));
        console2.log(StdStyle.underline("StdStyle.underline String Test"));
        console2.log(StdStyle.underline(uint256(10e18)));
        console2.log(StdStyle.underline(int256(-10e18)));
        console2.log(StdStyle.underline(address(0)));
        console2.log(StdStyle.underline(true));
        console2.log(StdStyle.underlineBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.underlineBytes32("StdStyle.underlineBytes32"));
        console2.log(StdStyle.inverse("StdStyle.inverse String Test"));
        console2.log(StdStyle.inverse(uint256(10e18)));
        console2.log(StdStyle.inverse(int256(-10e18)));
        console2.log(StdStyle.inverse(address(0)));
        console2.log(StdStyle.inverse(true));
        console2.log(StdStyle.inverseBytes(hex"7109709ECfa91a80626fF3989D68f67F5b1DD12D"));
        console2.log(StdStyle.inverseBytes32("StdStyle.inverseBytes32"));
    }

    function test_StyleCombined() public pure {
        console2.log(StdStyle.red(StdStyle.bold("Red Bold String Test")));
        console2.log(StdStyle.green(StdStyle.dim(uint256(10e18))));
        console2.log(StdStyle.yellow(StdStyle.italic(int256(-10e18))));
        console2.log(StdStyle.blue(StdStyle.underline(address(0))));
        console2.log(StdStyle.magenta(StdStyle.inverse(true)));
    }

    function test_StyleCustom() public pure {
        console2.log(h1("Custom Style 1"));
        console2.log(h2("Custom Style 2"));
    }

    function h1(string memory a) private pure returns (string memory) {
        return StdStyle.cyan(StdStyle.inverse(StdStyle.bold(a)));
    }

    function h2(string memory a) private pure returns (string memory) {
        return StdStyle.magenta(StdStyle.bold(StdStyle.underline(a)));
    }
}
