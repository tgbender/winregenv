# winregenv

A Pythonic, safer interface for common Windows Registry operations built on the standard `winreg` module.

## Why Use winregenv?

Interacting with the Windows Registry using the standard library's `winreg` module can be cumbersome. It often requires manual handle management, parsing raw Windows error codes, and lacks high-level abstractions for common tasks.

`winregenv` provides a more user-friendly, robust, and Pythonic way to perform frequent registry operations without external dependencies. It aims to simplify common workflows while enhancing safety and error handling.

The package has an extensive test suite that includes both mocks and integration tests (238 tests at the time of writing) for its public interface.

There are functions in its public interface that may be helpful even if you're not dealing directly with the registry. The `expand_environment_string` could be helpful for understanding environment variables, and `is_elevated` could be used in any Python script that requires elevated access or knowledge about elevation.

It depends only on the standard library and is written 100% in Python. So long as the public interface of the winreg package doesn't change (and Microsoft doesn't deprecate functionality in kernel32.dll and advapi32.dll) the package should continue working as is indefinitely. Pinning a version in your dependencies or copying the entire thing into a stable location will provide a low maintenance registry interface. It's 0 dependency setup also makes it well suited for secure environments (by preventing supply chain attacks and being small enough to audit). You can pin a version and have confidence it will work as expected.  

## Installation

Install `winregenv` using pip:

```bash
pip install winregenv
```

**Requirements:**
* Python 3.8 or higher
* Microsoft Windows operating system

## Quick Start

Here's a simple example demonstrating how to use `RegistryRoot` to interact with a key in `HKEY_CURRENT_USER`:

```python
import sys
# Import necessary classes, exceptions, and constants
from winregenv import (
    RegistryRoot, RegistryError, RegistryKeyNotFoundError,
    RegistryValueNotFoundError, RegistryKeyNotEmptyError,
    RegistryPermissionError, REG_SZ, REG_DWORD, REG_EXPAND_SZ
)

if sys.platform != "win32":
    print("This example requires Windows.")
    sys.exit(1)

# Define a unique temporary key path for this example to avoid conflicts
TEST_KEY_PATH = r"Software\winregenv_example_test_key"

try:
    # 1. Initialize RegistryRoot for HKEY_CURRENT_USER
    #    Operations will be relative to HKCU.
    hkcu_root = RegistryRoot("HKCU")
    print(f"Initialized RegistryRoot for {hkcu_root.root_key_name}") # Use root_key_name for string representation

    # 2. Create a key and put some values
    print(f"\nCreating key and values under HKCU\\{TEST_KEY_PATH}...")
    # Automatically creates the key if it doesn't exist
    hkcu_root.put_registry_value(TEST_KEY_PATH, "StringValue", "Hello, Registry!") # Type inferred as REG_SZ
    hkcu_root.put_registry_value(TEST_KEY_PATH, "IntValue", 12345) # Type inferred as REG_DWORD
    hkcu_root.put_registry_value(TEST_KEY_PATH, "ExpandValue", "%TEMP%\\example.log", value_type=REG_EXPAND_SZ) # Explicit type
    hkcu_root.put_registry_value(TEST_KEY_PATH, "", "Default Value") # Set the (Default) value
    hkcu_root.put_registry_subkey(TEST_KEY_PATH, "SubKeyA") # Create an empty subkey
    print("Values and subkey created.")

    # 3. Read values
    print(f"\nReading values from HKCU\\{TEST_KEY_PATH}:")
    string_val = hkcu_root.get_registry_value(TEST_KEY_PATH, "StringValue")
    print(f"  '{string_val.name}': {string_val.data} (Type: {string_val.type_name})") # Use type_name for string

    expand_val = hkcu_root.get_registry_value(TEST_KEY_PATH, "ExpandValue")
    print(f"  '{expand_val.name}': {expand_val.data} (Type: {expand_val.type_name})")
    # Access the expanded data property for REG_EXPAND_SZ values
    print(f"    Expanded: {expand_val.expanded_data}")

    # 4. List all values in the key
    print(f"\nListing all values in HKCU\\{TEST_KEY_PATH}:")
    all_values = hkcu_root.list_registry_values(TEST_KEY_PATH)
    for val in all_values:
        print(f"  '{val.name}': {val.data} (Type: {val.type_name})")

    # 5. List subkeys
    print(f"\nListing subkeys in HKCU\\{TEST_KEY_PATH}:")
    subkeys = hkcu_root.list_registry_subkeys(TEST_KEY_PATH)
    print(f"  Subkeys: {subkeys}")

    # 6. Get key metadata
    print(f"\nGetting metadata for HKCU\\{TEST_KEY_PATH}:")
    metadata = hkcu_root.head_registry_key(TEST_KEY_PATH)
    print(f"  Metadata: {metadata}")

    # 7. Delete a value
    print(f"\nDeleting 'IntValue' from HKCU\\{TEST_KEY_PATH}...")
    # No error if the value doesn't exist
    hkcu_root.delete_registry_value(TEST_KEY_PATH, "IntValue")
    print("'IntValue' deleted (or was already missing).")

    # 8. Attempt to delete the key (will fail because SubKeyA exists)
    print(f"\nAttempting to delete HKCU\\{TEST_KEY_PATH} (should fail)...")
    try:
        hkcu_root.delete_registry_key(TEST_KEY_PATH)
    except RegistryKeyNotEmptyError as e:
        print(f"  Caught expected error: {e}")

    # 9. Clean up: Delete the subkey first, then the main key
    print(f"\nCleaning up: Deleting subkey HKCU\\{TEST_KEY_PATH}\\SubKeyA...")
    hkcu_root.delete_registry_key(TEST_KEY_PATH + r"\SubKeyA")
    print("SubKeyA deleted.")

    print(f"\nCleaning up: Deleting main key HKCU\\{TEST_KEY_PATH}...")
    hkcu_root.delete_registry_key(TEST_KEY_PATH)
    print(f"Key HKCU\\{TEST_KEY_PATH} deleted.")

except RegistryKeyNotFoundError:
    print(f"\nError: The key path HKCU\\{TEST_KEY_PATH} or one of its parents was not found during cleanup.", file=sys.stderr)
except RegistryPermissionError as e:
    print(f"\nPermission Error: {e}", file=sys.stderr)
except RegistryError as e:
    print(f"\nA registry error occurred during the example: {e}", file=sys.stderr)
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)

```

## Features

* **Standard Library Only:** No external dependencies required. Works out-of-the-box with any standard Python 3.8+ installation on Windows.
* **Pythonic Interface:** Provides an object-oriented approach centered around the `RegistryRoot` class.
* **Automatic Resource Management:** Ensures registry handles are properly closed using context managers internally, preventing resource leaks.
* **Safer Error Handling:** Translates raw Windows errors (`OSError` with `winerror`) into specific, meaningful Python exceptions.
* **Built-in Type Handling:** Simplifies reading and writing common value types (`REG_SZ`, `REG_DWORD`, `REG_BINARY`, `REG_MULTI_SZ`, `REG_EXPAND_SZ`) with automatic type inference and validation.
* **WOW64 Support:** Provides easy access to the 32-bit registry view on 64-bit systems via an initialization flag.
* **Elevation Awareness:** Includes utilities to check process elevation and adds a safety check for write/delete operations on sensitive system keys (`HKLM`, `HKU`, etc.).
* **Environment Variable Expansion:** Supports reading and expanding `REG_EXPAND_SZ` values easily.
**Important:** This check is a convenience and safety feature provided by `winregenv` and does **not** replace the fundamental security enforced by Windows Access Control Lists (ACLs) on individual registry keys. Operations may still fail with `RegistryPermissionError` due to ACLs, even if the process is elevated or the library's check is bypassed.

### `RegistryRoot` Class

The primary interface for interacting with the registry. You instantiate it with:

* `root_key`: The root hive. Can be an integer handle (like `winreg.HKEY_CURRENT_USER`) or, more commonly, a string name like `"HKLM"`, `"HKCU"`, `"HKCR"`, `"HKU"`. Using string names avoids needing to import `winreg`.
* `root_prefix` (optional): A base path under the root key. All operations using this `RegistryRoot` instance will be relative to `root_key\root_prefix`.
* `access_32bit_view` (default `False`): Set to `True` to access the 32-bit registry view (`Wow6432Node`) on 64-bit Windows.
* `read_only` (default `False`): Set to `True` to prevent any `put_` or `delete_` operations on this instance. Read/list/head operations are still allowed.
* `ignore_elevation_check` (default `False`): **Use with caution.** If `True`, bypasses the explicit check for elevated privileges when performing write/delete operations on potentially sensitive root keys (`HKLM`, `HKU`, `HKCR`, `HKCC`). The operation may still fail with a `RegistryPermissionError` due to Windows Access Control Lists (ACLs).

Setting this to `True` does **not** grant any additional permissions; the operation is still subject to Windows Access Control Lists (ACLs) and may fail with a `RegistryPermissionError` if the necessary OS-level permissions are not present.

`RegistryRoot` provides methods for common registry manipulation:

* `put_registry_value(key_path, value_name, value_data, *, value_type=None)`: Creates or updates a value within the specified key. If `key_path` doesn't exist, it (and any parent keys under the `root_prefix`) will be created. Infers `value_type` based on `value_data` if not explicitly provided.
* `put_registry_subkey(key_path, subkey_name)`: Creates a new subkey under the specified `key_path`. Creates parent keys if necessary.
* `get_registry_value(key_path, value_name)`: Retrieves a single value as a `RegistryValue` object. Raises `RegistryValueNotFoundError` if the value doesn't exist.
* `list_registry_values(key_path)`: Lists all values within a key as a list of `RegistryValue` objects. Returns an empty list if the key has no values.
* `list_registry_subkeys(key_path)`: Lists the names (strings) of the immediate subkeys within a key. Returns an empty list if there are no subkeys.
* `head_registry_key(key_path)`: Retrieves metadata about a key (subkey count, value count, last write time) as a `RegistryKeyInfo` object.
* `delete_registry_value(key_path, value_name)`: Deletes a specific value from a key. Does *not* raise an error if the value is already missing.
* `delete_registry_value(key_path, value_name)`: Deletes a specific value from a key. Does *not* raise an error if the value is already missing.
* `delete_registry_key(key_path)`: Deletes an *empty* key. Raises `RegistryKeyNotEmptyError` if the key contains any subkeys or values. Does *not* raise an error if the key is already missing.

*(All `key_path` arguments are relative to the `RegistryRoot`'s `root_key` and `root_prefix`.)*

### `RegistryValue` Object

Methods that read registry values (`get_registry_value`, `list_registry_values`) return `RegistryValue` objects (or lists thereof). These provide convenient access to value properties:

* `.name`: The value name (`str`). This is `""` for the `(Default)` value of a key.
* `.data`: The value's data, converted to an appropriate Python type (e.g., `str`, `int`, `bytes`, `list[str]`).
* `.type`: The integer registry type constant (e.g., `winreg.REG_SZ`). You can compare this against constants exposed by `winregenv` (like `winregenv.REG_SZ`).
* `.type_name`: A string representation of the registry type (e.g., `"REG_SZ"`).
* `.expanded_data`: For `REG_EXPAND_SZ` values only. This property returns the data string with environment variables expanded using the Windows API (`ExpandEnvironmentStrings`). It returns `None` for other value types or if expansion fails.

### Error Handling

`winregenv` translates common `OSError` exceptions (specifically those with `winerror` codes related to registry operations) into a hierarchy of custom exceptions, all inheriting from `RegistryError`:

* `RegistryError`: Base class for all `winregenv` specific errors.
* `RegistryKeyNotFoundError`: The specified key path does not exist.
* `RegistryValueNotFoundError`: The specified value name does not exist within an existing key.
* `RegistryKeyNotEmptyError`: Attempted to delete a key that still contains subkeys or values.
* `RegistryPermissionError`: The operation was denied due to insufficient privileges. This can be triggered either by the library's explicit elevation check (on sensitive hives) or by underlying Windows ACL permissions.

This allows for more precise error handling using standard Python `try...except` blocks.

### Utility Functions

The library also exposes some useful helper functions:

* `normalize_root_key(key_identifier: int | str) -> int`: Converts a root key identifier (like `winreg.HKEY_LOCAL_MACHINE` or `"HKLM"`) into its standard integer handle. Raises `ValueError` for unknown string names.
* `normalize_registry_type(type_input: int | str) -> int`: Converts a registry value type identifier (like `winreg.REG_SZ` or `"REG_SZ"`) into its standard integer constant. Raises `ValueError` for unknown names or integers.
* `is_elevated() -> bool`: Checks if the current process is running with administrative privileges (High integrity level or higher). Returns `True` if elevated, `False` otherwise. Raises `OSError` if the check fails.
* `get_integrity_level() -> int`: Returns the raw integer RID representing the process's integrity level. Raises `OSError` or `ValueError` if retrieval fails.
* `expand_environment_strings(input_string: str) -> str`: Directly calls the Windows API to expand environment variables within a string (equivalent to `RegistryValue.expanded_data` but callable directly).

## Comparison: Reading a Value with Raw `winreg`

`winregenv` was written to cut down on boiler plate and allow cleaner, safer code. Comparing a simple task between the two libraries illustrates this. Compare reading a single registry value using *only* the standard `winreg` module while ensuring proper resource management and error handling:

```python
import winreg
import sys

# --- Using raw winreg ---

# Define the target key and value
root_key_handle = winreg.HKEY_CURRENT_USER
key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer" # Example path
value_name = "CleanShutdown" # Example value (often REG_DWORD)

key_handle = None # Must initialize handle outside try
value_data = None
value_type = None
print(f"Attempting to read '{value_name}' from HKCU\\{key_path} using raw winreg...")

try:
    # 1. Manually open the key
    # Note: For 32-bit view on 64-bit OS, you'd add winreg.KEY_WOW64_32KEY here
    print("  Opening key...")
    key_handle = winreg.OpenKeyEx(root_key_handle, key_path, 0, winreg.KEY_READ)
    print("  Key opened.")

    try:
        # 2. Manually query the value
        print(f"  Querying value '{value_name}'...")
        value_data, value_type = winreg.QueryValueEx(key_handle, value_name)
        print(f"  Value read: Data={value_data}, Type={value_type}")

    except FileNotFoundError:
        # Handle case where the VALUE doesn't exist within the key
        print(f"  Error: Value '{value_name}' not found in the key.", file=sys.stderr)
        # Decide how to proceed, value_data remains None or set a default

    except PermissionError as e_val:
        # Handle permission error reading the value specifically
        print(f"  Error: Permission denied reading value '{value_name}'. {e_val}", file=sys.stderr)

    except OSError as e_val:
        # Handle other potential OS errors during value query
        print(f"  Error reading value '{value_name}': {e_val}", file=sys.stderr)

except FileNotFoundError:
    # Handle case where the KEY itself doesn't exist
    print(f"Error: Key 'HKCU\\{key_path}' not found.", file=sys.stderr)
    # Cannot proceed further

except PermissionError as e_key:
    # Handle permission error opening the key
    print(f"Error: Permission denied opening key 'HKCU\\{key_path}'. {e_key}", file=sys.stderr)

except OSError as e_key:
    # Handle other potential OS errors during key opening
    print(f"Error opening key 'HKCU\\{key_path}': {e_key}", file=sys.stderr)

finally:
    # 3. CRITICAL: Manually close the key handle if it was opened
    if key_handle:
        try:
            winreg.CloseKey(key_handle)
            print("  Key closed.")
        except OSError as e_close:
            # Handle rare error during CloseKey
            print(f"  Error closing key handle: {e_close}", file=sys.stderr)

# 4. Check if data was successfully retrieved before using it
if value_data is not None:
    print(f"\nFinal result: '{value_name}' = {value_data} (Type: {value_type})")
else:
    print(f"\nCould not retrieve value for '{value_name}'.")

```

**Contrast this with the `winregenv` equivalent:**

```python
# --- Using winregenv ---
import sys
from winregenv import RegistryRoot, RegistryValueNotFoundError, RegistryKeyNotFoundError, RegistryPermissionError

hkcu = RegistryRoot("HKCU")
key_path = r"Software/Microsoft/Windows/CurrentVersion/Explorer" # Slashes work too!
value_name = "CleanShutdown"
print(f"\nAttempting to read '{value_name}' from HKCU\\{key_path} using winregenv...")

try:
    reg_value = hkcu.get_registry_value(key_path, value_name)
    print(f"  Value read successfully:")
    print(f"  Name: {reg_value.name}")
    print(f"  Data: {reg_value.data}")
    print(f"  Type: {reg_value.type_name}") # Access type name easily
    print(f"\nFinal result: '{reg_value.name}' = {reg_value.data} (Type: {reg_value.type})")

except RegistryValueNotFoundError:
    print(f"Error: Value '{value_name}' not found in key 'HKCU\\{key_path}'.", file=sys.stderr)
except RegistryKeyNotFoundError:
    print(f"Error: Key 'HKCU\\{key_path}' not found.", file=sys.stderr)
except RegistryPermissionError as e:
    print(f"Error: Permission denied accessing registry. {e}", file=sys.stderr)
except Exception as e: # Catch other potential errors
    print(f"An unexpected error occurred: {e}", file=sys.stderr)

```

The raw `winreg` approach requires:
*   Manual handle initialization (`key_handle = None`).
*   Explicit `winreg.OpenKeyEx` and `winreg.QueryValueEx` calls.
*   A `try...finally` block *specifically* to ensure `winreg.CloseKey` is called.
*   Nested `try...except` blocks to differentiate between errors opening the key vs. reading the value.
*   Manual checking of `OSError.winerror` codes (or relying on Python 3 mapping some to `FileNotFoundError`/`PermissionError`) to understand *why* an operation failed.
*   More verbose code overall.

`winregenv` handles the key opening/closing automatically via context managers internally and translates errors into specific exceptions, allowing cleaner, safer, and more readable code for the same task.

## Scope and Limitations

`winregenv` focuses on simplifying the *most common* registry read/write operations on the local machine. It is **not** intended as a complete replacement for the `winreg` module or the full Windows Registry API.

Features currently **not** supported include:

* Transactional registry operations.
* Reading or modifying registry key security descriptors (ACLs).
* Registry change notifications (`RegNotifyChangeKeyValue`).
* Connecting to remote registries (`RegConnectRegistry`).
* Loading or unloading registry hives (`RegLoadKey`, `RegUnLoadKey`).
* Registry backup or restore operations.
* Detailed parsing or writing of complex/less common types like `REG_RESOURCE_LIST` or `REG_LINK`.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Contact

If you encounter issues, have suggestions, or have questions, please open an issue on the [GitHub repository](https://github.com/tgbender/winregenv).
