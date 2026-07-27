// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity ^0.8.13;

import {VmSafe} from "./Vm.sol";
import {Variable, Type, TypeKind, LibVariable} from "./LibVariable.sol";

/// @notice  A contract that parses a toml configuration file and loads its
///          variables into storage, automatically casting them, on deployment.
///
/// @dev     This contract assumes a toml structure where top-level keys
///          represent chain ids or aliases. Under each chain key, variables are
///          organized by type in separate sub-tables like `[<chain>.<type>]`, where
///          type must be: `bool`, `address`, `bytes32`, `uint`, `int`, `string`, or `bytes`.
///
///          Supported format:
///          ```
///          [mainnet]
///          endpoint_url = "${MAINNET_RPC}"
///
///          [mainnet.bool]
///          is_live = true
///
///          [mainnet.address]
///          weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
///          whitelisted_admins = [
///             "${MAINNET_ADMIN}",
///             "0x00000000000000000000000000000000deadbeef",
///             "0x000000000000000000000000000000c0ffeebabe"
///          ]
///
///          [mainnet.uint]
///          important_number = 123
///          ```
contract StdConfig {
    using LibVariable for Type;
    using LibVariable for TypeKind;

    VmSafe private constant vm = VmSafe(address(uint160(uint256(keccak256("hevm cheat code")))));

    /// @dev Types: `bool`, `address`, `bytes32`, `uint`, `int`, `string`, `bytes`.
    uint8 private constant NUM_TYPES = 7;

    // -- ERRORS ---------------------------------------------------------------

    error AlreadyInitialized(string key);
    error InvalidChainKey(string aliasOrId);
    error ChainNotInitialized(uint256 chainId);
    error UnableToParseVariable(string key);
    error WriteToFileInForbiddenCtxt();

    // -- STORAGE (CACHE FROM CONFIG FILE) ------------------------------------

    /// @dev Path to the loaded TOML configuration file.
    string private _filePath;

    /// @dev List of top-level keys found in the TOML file, assumed to be chain names/aliases.
    string[] private _chainKeys;

    /// @dev Storage for the configured RPC URL for each chain.
    mapping(uint256 => string) private _rpcOf;

    /// @dev Storage for values, organized by chain ID and variable key.
    mapping(uint256 => mapping(string => bytes)) private _dataOf;

    /// @dev Type cache for runtime checking when casting.
    mapping(uint256 => mapping(string => Type)) private _typeOf;

    /// @dev When enabled, `set` will always write updates back to the configuration file.
    ///      Can only be enabled in a scripting context to prevent file corruption from
    ///      concurrent I/O access, as tests run in parallel.
    bool private _writeToFile;

    // -- CONSTRUCTOR ----------------------------------------------------------

    /// @notice Reads the TOML file and iterates through each top-level key, which is
    ///         assumed to be a chain name or ID. For each chain, it caches its RPC
    ///         endpoint and all variables defined in typed sub-tables like `[<chain>.<type>]`,
    ///         where type must be: `bool`, `address`, `bytes32`, `uint`, `int`, `string`, or `bytes`.
    ///
    ///         The constructor attempts to parse each variable first as a single value,
    ///         and if that fails, as an array of that type. If a variable cannot be
    ///         parsed as either, the constructor will revert with an error.
    ///
    /// @param  configFilePath: The local path to the TOML configuration file.
    /// @param  writeToFile: Whether to write updates back to the TOML file. Only for scripts.
    constructor(string memory configFilePath, bool writeToFile) {
        if (writeToFile && !vm.isContext(VmSafe.ForgeContext.ScriptGroup)) {
            revert WriteToFileInForbiddenCtxt();
        }

        _filePath = configFilePath;
        _writeToFile = writeToFile;
        string memory content = vm.resolveEnv(vm.readFile(configFilePath));
        string[] memory chain_keys = vm.parseTomlKeys(content, "$");

        // Cache the entire configuration to storage
        for (uint256 i = 0; i < chain_keys.length; i++) {
            string memory chain_key = chain_keys[i];
            // Ignore top-level keys that are not tables
            if (vm.parseTomlKeys(content, string.concat("$.", chain_key)).length == 0) {
                continue;
            }
            uint256 chainId = resolveChainId(chain_key);
            _chainKeys.push(chain_key);

            // Cache the configured RPC endpoint for that chain.
            // Falls back to `[rpc_endpoints]`. Panics if no rpc endpoint is configured.
            try vm.parseTomlString(content, string.concat("$.", chain_key, ".endpoint_url")) returns (
                string memory url
            ) {
                _rpcOf[chainId] = vm.resolveEnv(url);
            } catch {
                _rpcOf[chainId] = vm.resolveEnv(vm.rpcUrl(chain_key));
            }

            // Iterate through all the available `TypeKind`s (except `None`) to create the sub-section paths
            for (uint8 t = 1; t <= NUM_TYPES; t++) {
                TypeKind ty = TypeKind(t);
                string memory typePath = string.concat("$.", chain_key, ".", ty.toTomlKey());

                try vm.parseTomlKeys(content, typePath) returns (string[] memory keys) {
                    for (uint256 j = 0; j < keys.length; j++) {
                        string memory key = keys[j];
                        if (_typeOf[chainId][key].kind == TypeKind.None) {
                            _loadAndCacheValue(content, string.concat(typePath, ".", key), chainId, key, ty);
                        } else {
                            revert AlreadyInitialized(key);
                        }
                    }
                } catch {}
            }
        }
    }

    function _loadAndCacheValue(
        string memory content,
        string memory path,
        uint256 chainId,
        string memory key,
        TypeKind ty
    ) private {
        bool success = false;
        if (ty == TypeKind.Bool) {
            try vm.parseTomlBool(content, path) returns (bool val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Bool, false);
                success = true;
            } catch {
                try vm.parseTomlBoolArray(content, path) returns (bool[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Bool, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.Address) {
            try vm.parseTomlAddress(content, path) returns (address val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Address, false);
                success = true;
            } catch {
                try vm.parseTomlAddressArray(content, path) returns (address[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Address, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.Bytes32) {
            try vm.parseTomlBytes32(content, path) returns (bytes32 val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Bytes32, false);
                success = true;
            } catch {
                try vm.parseTomlBytes32Array(content, path) returns (bytes32[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Bytes32, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.Uint256) {
            try vm.parseTomlUint(content, path) returns (uint256 val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Uint256, false);
                success = true;
            } catch {
                try vm.parseTomlUintArray(content, path) returns (uint256[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Uint256, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.Int256) {
            try vm.parseTomlInt(content, path) returns (int256 val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Int256, false);
                success = true;
            } catch {
                try vm.parseTomlIntArray(content, path) returns (int256[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Int256, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.Bytes) {
            try vm.parseTomlBytes(content, path) returns (bytes memory val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.Bytes, false);
                success = true;
            } catch {
                try vm.parseTomlBytesArray(content, path) returns (bytes[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.Bytes, true);
                    success = true;
                } catch {}
            }
        } else if (ty == TypeKind.String) {
            try vm.parseTomlString(content, path) returns (string memory val) {
                _dataOf[chainId][key] = abi.encode(val);
                _typeOf[chainId][key] = Type(TypeKind.String, false);
                success = true;
            } catch {
                try vm.parseTomlStringArray(content, path) returns (string[] memory val) {
                    _dataOf[chainId][key] = abi.encode(val);
                    _typeOf[chainId][key] = Type(TypeKind.String, true);
                    success = true;
                } catch {}
            }
        }

        if (!success) {
            revert UnableToParseVariable(key);
        }
    }

    // -- HELPER FUNCTIONS -----------------------------------------------------

    /// @notice Enable or disable automatic writing to the TOML file on `set`.
    ///         Can only be enabled when scripting.
    function writeUpdatesBackToFile(bool enabled) public {
        if (enabled && !vm.isContext(VmSafe.ForgeContext.ScriptGroup)) {
            revert WriteToFileInForbiddenCtxt();
        }

        _writeToFile = enabled;
    }

    /// @notice Resolves a chain alias or a chain id string to its numerical chain id.
    /// @param aliasOrId The string representing the chain alias (i.e. "mainnet") or a numerical ID (i.e. "1").
    /// @return The numerical chain ID.
    /// @dev It first attempts to parse the input as a number. If that fails, it uses `vm.getChain` to resolve a named alias.
    ///      Reverts if the alias is not valid or not a number.
    function resolveChainId(string memory aliasOrId) public view returns (uint256) {
        try vm.parseUint(aliasOrId) returns (uint256 chainId) {
            return chainId;
        } catch {
            try vm.getChain(aliasOrId) returns (VmSafe.Chain memory chainInfo) {
                return chainInfo.chainId;
            } catch {
                revert InvalidChainKey(aliasOrId);
            }
        }
    }

    /// @dev Retrieves the chain key/alias from the configuration based on the chain ID.
    function _getChainKeyFromId(uint256 chainId) private view returns (string memory) {
        for (uint256 i = 0; i < _chainKeys.length; i++) {
            if (resolveChainId(_chainKeys[i]) == chainId) {
                return _chainKeys[i];
            }
        }
        revert ChainNotInitialized(chainId);
    }

    /// @dev Ensures type consistency when setting a value - prevents changing types unless uninitialized.
    ///      Updates type only when the previous type was `None`.
    function _ensureTypeConsistency(uint256 chainId, string memory key, Type memory ty) private {
        Type memory current = _typeOf[chainId][key];

        if (current.kind == TypeKind.None) {
            _typeOf[chainId][key] = ty;
        } else {
            current.assertEq(ty);
        }
    }

    /// @dev Wraps a string in double quotes for JSON compatibility.
    function _quote(string memory s) private pure returns (string memory) {
        return string.concat('"', s, '"');
    }

    /// @dev Writes a JSON-formatted value to a specific key in the TOML file.
    /// @param chainId The chain id to write under.
    /// @param ty The type category ('bool', 'address', 'uint', 'bytes32', 'string', or 'bytes').
    /// @param key The variable key name.
    /// @param jsonValue The JSON-formatted value to write.
    function _writeToToml(uint256 chainId, string memory ty, string memory key, string memory jsonValue) private {
        string memory chainKey = _getChainKeyFromId(chainId);
        string memory valueKey = string.concat("$.", chainKey, ".", ty, ".", key);
        vm.writeToml(jsonValue, _filePath, valueKey);
    }

    // -- GETTER FUNCTIONS -----------------------------------------------------

    /// @dev    Reads a variable for a given chain id and key, and returns it in a generic container.
    ///         The caller should use `LibVariable` to safely coerce the type.
    ///         Example: `uint256 myVar = config.get("my_key").toUint256();`
    ///
    /// @param  chain_id The chain ID to read from.
    /// @param  key The key of the variable to retrieve.
    /// @return `Variable` struct containing the type and the ABI-encoded value.
    function get(uint256 chain_id, string memory key) public view returns (Variable memory) {
        return Variable(_typeOf[chain_id][key], _dataOf[chain_id][key]);
    }

    /// @dev    Reads a variable for the current chain and a given key, and returns it in a generic container.
    ///         The caller should use `LibVariable` to safely coerce the type.
    ///         Example: `uint256 myVar = config.get("my_key").toUint256();`
    ///
    /// @param  key The key of the variable to retrieve.
    /// @return `Variable` struct containing the type and the ABI-encoded value.
    function get(string memory key) public view returns (Variable memory) {
        return get(vm.getChainId(), key);
    }

    /// @dev    Checks the existence of a variable for a given chain ID and key, and returns a boolean.
    ///         Example: `bool hasKey = config.exists(1, "my_key");`
    ///
    /// @param chain_id The chain ID to check.
    /// @param key The variable key name.
    /// @return `bool` indicating whether a variable with the given key exists.
    function exists(uint256 chain_id, string memory key) public view returns (bool) {
        return _dataOf[chain_id][key].length > 0;
    }

    /// @dev    Checks the existence of a variable for the current chain id and a given key, and returns a boolean.
    ///         Example: `bool hasKey = config.exists("my_key");`
    ///
    /// @param key The variable key name.
    /// @return `bool` indicating whether a variable with the given key exists.
    function exists(string memory key) public view returns (bool) {
        return exists(vm.getChainId(), key);
    }

    /// @notice Returns the numerical chain ids for all configured chains.
    function getChainIds() public view returns (uint256[] memory) {
        string[] memory keys = _chainKeys;

        uint256[] memory ids = new uint256[](keys.length);
        for (uint256 i = 0; i < keys.length; i++) {
            ids[i] = resolveChainId(keys[i]);
        }

        return ids;
    }

    /// @notice Reads the RPC URL for a specific chain id.
    function getRpcUrl(uint256 chainId) public view returns (string memory) {
        return _rpcOf[chainId];
    }

    /// @notice Reads the RPC URL for the current chain.
    function getRpcUrl() public view returns (string memory) {
        return _rpcOf[vm.getChainId()];
    }

    // -- SETTER FUNCTIONS (SINGLE VALUES) -------------------------------------

    /// @notice Sets a boolean value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bool value) public {
        Type memory ty = Type(TypeKind.Bool, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, vm.toString(value));
    }

    /// @notice Sets a boolean value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bool value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets an address value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, address value) public {
        Type memory ty = Type(TypeKind.Address, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, _quote(vm.toString(value)));
    }

    /// @notice Sets an address value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, address value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a bytes32 value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bytes32 value) public {
        Type memory ty = Type(TypeKind.Bytes32, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, _quote(vm.toString(value)));
    }

    /// @notice Sets a bytes32 value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bytes32 value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a uint256 value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, uint256 value) public {
        Type memory ty = Type(TypeKind.Uint256, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, vm.toString(value));
    }

    /// @notice Sets a uint256 value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, uint256 value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets an int256 value for a given key and chain ID.
    function set(uint256 chainId, string memory key, int256 value) public {
        Type memory ty = Type(TypeKind.Int256, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, vm.toString(value));
    }

    /// @notice Sets an int256 value for a given key on the current chain.
    function set(string memory key, int256 value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a string value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, string memory value) public {
        Type memory ty = Type(TypeKind.String, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, _quote(value));
    }

    /// @notice Sets a string value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, string memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a bytes value for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bytes memory value) public {
        Type memory ty = Type(TypeKind.Bytes, false);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) _writeToToml(chainId, ty.kind.toTomlKey(), key, _quote(vm.toString(value)));
    }

    /// @notice Sets a bytes value for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bytes memory value) public {
        set(vm.getChainId(), key, value);
    }

    // -- SETTER FUNCTIONS (ARRAYS) --------------------------------------------

    /// @notice Sets a boolean array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bool[] memory value) public {
        Type memory ty = Type(TypeKind.Bool, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, vm.toString(value[i]));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a boolean array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bool[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets an address array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, address[] memory value) public {
        Type memory ty = Type(TypeKind.Address, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, _quote(vm.toString(value[i])));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets an address array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, address[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a bytes32 array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bytes32[] memory value) public {
        Type memory ty = Type(TypeKind.Bytes32, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, _quote(vm.toString(value[i])));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a bytes32 array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bytes32[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a uint256 array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, uint256[] memory value) public {
        Type memory ty = Type(TypeKind.Uint256, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, vm.toString(value[i]));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a uint256 array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, uint256[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a int256 array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, int256[] memory value) public {
        Type memory ty = Type(TypeKind.Int256, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, vm.toString(value[i]));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a int256 array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, int256[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a string array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, string[] memory value) public {
        Type memory ty = Type(TypeKind.String, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, _quote(value[i]));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a string array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, string[] memory value) public {
        set(vm.getChainId(), key, value);
    }

    /// @notice Sets a bytes array for a given key and chain ID.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(uint256 chainId, string memory key, bytes[] memory value) public {
        Type memory ty = Type(TypeKind.Bytes, true);
        _ensureTypeConsistency(chainId, key, ty);
        _dataOf[chainId][key] = abi.encode(value);
        if (_writeToFile) {
            string memory json = "[";
            for (uint256 i = 0; i < value.length; i++) {
                json = string.concat(json, _quote(vm.toString(value[i])));
                if (i < value.length - 1) json = string.concat(json, ",");
            }
            json = string.concat(json, "]");
            _writeToToml(chainId, ty.kind.toTomlKey(), key, json);
        }
    }

    /// @notice Sets a bytes array for a given key on the current chain.
    /// @dev    Sets the cached value in storage and writes the change back to the TOML file if `autoWrite` is enabled.
    function set(string memory key, bytes[] memory value) public {
        set(vm.getChainId(), key, value);
    }
}
