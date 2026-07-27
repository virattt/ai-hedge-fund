// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

import {IERC165} from "./IERC165.sol";

/// @dev Required interface of an ERC-6909 compliant contract, as defined in
/// https://eips.ethereum.org/EIPS/eip-6909
interface IERC6909 is IERC165 {
    /// @dev Emitted when the allowance of a `spender` for an `owner` is set for a token of type `id`.
    event Approval(address indexed owner, address indexed spender, uint256 indexed id, uint256 amount);

    /// @dev Emitted when `owner` grants or revokes operator status for a `spender`.
    event OperatorSet(address indexed owner, address indexed spender, bool approved);

    /// @dev Emitted when `amount` tokens of type `id` are moved from `sender` to `receiver` initiated by `caller`.
    event Transfer(
        address caller, address indexed sender, address indexed receiver, uint256 indexed id, uint256 amount
    );

    ///@dev Returns the amount of tokens of type `id` owned by `owner`.
    function balanceOf(address owner, uint256 id) external view returns (uint256);

    /// @dev Returns the amount of tokens of type `id` that `spender` is allowed to spend on behalf of `owner`.
    /// NOTE: Does not include operator allowances.
    function allowance(address owner, address spender, uint256 id) external view returns (uint256);

    /// @dev Returns true if `spender` is set as an operator for `owner`.
    function isOperator(address owner, address spender) external view returns (bool);

    /// @dev Sets an approval to `spender` for `amount` tokens of type `id` from the caller's tokens.
    /// Must return true.
    function approve(address spender, uint256 id, uint256 amount) external returns (bool);

    /// @dev Grants or revokes unlimited transfer permission of any token id to `spender` for the caller's tokens.
    /// Must return true.
    function setOperator(address spender, bool approved) external returns (bool);

    /// @dev Transfers `amount` of token type `id` from the caller's account to `receiver`.
    /// Must return true.
    function transfer(address receiver, uint256 id, uint256 amount) external returns (bool);

    /// @dev Transfers `amount` of token type `id` from `sender` to `receiver`.
    /// Must return true.
    function transferFrom(address sender, address receiver, uint256 id, uint256 amount) external returns (bool);
}

/// @dev Optional extension of {IERC6909} that adds metadata functions.
interface IERC6909Metadata is IERC6909 {
    /// @dev Returns the name of the token of type `id`.
    function name(uint256 id) external view returns (string memory);

    /// @dev Returns the ticker symbol of the token of type `id`.
    function symbol(uint256 id) external view returns (string memory);

    /// @dev Returns the number of decimals for the token of type `id`.
    function decimals(uint256 id) external view returns (uint8);
}

/// @dev Optional extension of {IERC6909} that adds content URI functions.
interface IERC6909ContentURI is IERC6909 {
    /// @dev Returns URI for the contract.
    function contractURI() external view returns (string memory);

    /// @dev Returns the URI for the token of type `id`.
    function tokenURI(uint256 id) external view returns (string memory);
}

/// @dev Optional extension of {IERC6909} that adds a token supply function.
interface IERC6909TokenSupply is IERC6909 {
    /// @dev Returns the total supply of the token of type `id`.
    function totalSupply(uint256 id) external view returns (uint256);
}
