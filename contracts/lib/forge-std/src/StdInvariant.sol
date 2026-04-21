// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity >=0.8.13 <0.9.0;

/// @notice Abstract contract providing configuration utilities for Forge invariant tests.
abstract contract StdInvariant {
    struct FuzzSelector {
        address addr;
        bytes4[] selectors;
    }

    struct FuzzArtifactSelector {
        string artifact;
        bytes4[] selectors;
    }

    struct FuzzInterface {
        address addr;
        string[] artifacts;
    }

    address[] private _excludedContracts;
    address[] private _excludedSenders;
    address[] private _targetedContracts;
    address[] private _targetedSenders;

    string[] private _excludedArtifacts;
    string[] private _targetedArtifacts;

    FuzzArtifactSelector[] private _targetedArtifactSelectors;

    FuzzSelector[] private _excludedSelectors;
    FuzzSelector[] private _targetedSelectors;

    FuzzInterface[] private _targetedInterfaces;

    // Functions for users:
    // These are intended to be called in tests.

    /// @notice Excludes a contract address from invariant target selection.
    /// @param newExcludedContract_ The contract address to exclude.
    function excludeContract(address newExcludedContract_) internal {
        _excludedContracts.push(newExcludedContract_);
    }

    /// @notice Excludes specific selectors on a contract from invariant fuzzing.
    /// @param newExcludedSelector_ The selector configuration to exclude.
    function excludeSelector(FuzzSelector memory newExcludedSelector_) internal {
        _excludedSelectors.push(newExcludedSelector_);
    }

    /// @notice Excludes a sender from invariant fuzzing; exclusion takes precedence over targeted senders.
    /// @param newExcludedSender_ The sender address to exclude.
    function excludeSender(address newExcludedSender_) internal {
        _excludedSenders.push(newExcludedSender_);
    }

    /// @notice Excludes an artifact identifier from invariant target selection.
    /// @param newExcludedArtifact_ The artifact identifier to exclude.
    function excludeArtifact(string memory newExcludedArtifact_) internal {
        _excludedArtifacts.push(newExcludedArtifact_);
    }

    /// @notice Targets an artifact identifier for invariant fuzzing.
    /// @param newTargetedArtifact_ The artifact identifier to target.
    function targetArtifact(string memory newTargetedArtifact_) internal {
        _targetedArtifacts.push(newTargetedArtifact_);
    }

    /// @notice Targets specific selectors for an artifact identifier during invariant fuzzing.
    /// @param newTargetedArtifactSelector_ The artifact-selector configuration to target.
    function targetArtifactSelector(FuzzArtifactSelector memory newTargetedArtifactSelector_) internal {
        _targetedArtifactSelectors.push(newTargetedArtifactSelector_);
    }

    /// @notice Targets a contract address for invariant fuzzing.
    /// @param newTargetedContract_ The contract address to target.
    function targetContract(address newTargetedContract_) internal {
        _targetedContracts.push(newTargetedContract_);
    }

    /// @notice Targets specific selectors on a contract for invariant fuzzing.
    /// @param newTargetedSelector_ The selector configuration to target.
    function targetSelector(FuzzSelector memory newTargetedSelector_) internal {
        _targetedSelectors.push(newTargetedSelector_);
    }

    /// @notice Adds a sender to the invariant sender allowlist; when non-empty, fuzzing uses only targeted non-excluded senders.
    /// @param newTargetedSender_ The sender address to target.
    function targetSender(address newTargetedSender_) internal {
        _targetedSenders.push(newTargetedSender_);
    }

    /// @notice Targets an address plus artifact interfaces for invariant fuzzing.
    /// @param newTargetedInterface_ The address-interface configuration to target.
    function targetInterface(FuzzInterface memory newTargetedInterface_) internal {
        _targetedInterfaces.push(newTargetedInterface_);
    }

    // Functions for forge:
    // These are called by forge to run invariant tests and don't need to be called in tests.

    /// @notice Returns artifact identifiers configured via `excludeArtifact`.
    /// @return excludedArtifacts_ The list of excluded artifact identifiers.
    function excludeArtifacts() public view returns (string[] memory excludedArtifacts_) {
        excludedArtifacts_ = _excludedArtifacts;
    }

    /// @notice Returns contract addresses configured via `excludeContract`.
    /// @return excludedContracts_ The list of excluded contract addresses.
    function excludeContracts() public view returns (address[] memory excludedContracts_) {
        excludedContracts_ = _excludedContracts;
    }

    /// @notice Returns selector exclusions configured via `excludeSelector`.
    /// @return excludedSelectors_ The list of excluded selector configurations.
    function excludeSelectors() public view returns (FuzzSelector[] memory excludedSelectors_) {
        excludedSelectors_ = _excludedSelectors;
    }

    /// @notice Returns senders configured via `excludeSender`.
    /// @return excludedSenders_ The list of excluded sender addresses.
    function excludeSenders() public view returns (address[] memory excludedSenders_) {
        excludedSenders_ = _excludedSenders;
    }

    /// @notice Returns artifact identifiers configured via `targetArtifact`.
    /// @return targetedArtifacts_ The list of targeted artifact identifiers.
    function targetArtifacts() public view returns (string[] memory targetedArtifacts_) {
        targetedArtifacts_ = _targetedArtifacts;
    }

    /// @notice Returns artifact-selector targets configured via `targetArtifactSelector`.
    /// @return targetedArtifactSelectors_ The list of targeted artifact-selector configurations.
    function targetArtifactSelectors() public view returns (FuzzArtifactSelector[] memory targetedArtifactSelectors_) {
        targetedArtifactSelectors_ = _targetedArtifactSelectors;
    }

    /// @notice Returns contract addresses configured via `targetContract`.
    /// @return targetedContracts_ The list of targeted contract addresses.
    function targetContracts() public view returns (address[] memory targetedContracts_) {
        targetedContracts_ = _targetedContracts;
    }

    /// @notice Returns selector targets configured via `targetSelector`.
    /// @return targetedSelectors_ The list of targeted selector configurations.
    function targetSelectors() public view returns (FuzzSelector[] memory targetedSelectors_) {
        targetedSelectors_ = _targetedSelectors;
    }

    /// @notice Returns sender allowlist configured via `targetSender` (empty means no sender allowlist).
    /// @return targetedSenders_ The list of targeted sender addresses.
    function targetSenders() public view returns (address[] memory targetedSenders_) {
        targetedSenders_ = _targetedSenders;
    }

    /// @notice Returns address-interface targets configured via `targetInterface`.
    /// @return targetedInterfaces_ The list of targeted address-interface configurations.
    function targetInterfaces() public view returns (FuzzInterface[] memory targetedInterfaces_) {
        targetedInterfaces_ = _targetedInterfaces;
    }
}
