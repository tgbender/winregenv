"""Provides the primary public interface for interacting with the Windows Registry.

This module defines the `RegistryRoot` class, which serves as the main entry point
for users of the `winregenv` package to perform registry operations. It wraps
the lower-level functions from `registry_base`, offering a convenient, object-oriented
approach scoped to a specific registry root key (e.g., HKEY_CURRENT_USER) and
an optional base path prefix, and allowing specification of the registry view (native or 32-bit).

Usage typically involves creating an instance of `RegistryRoot` and then calling
its methods (e.g., `get_value`, `put_subkey`, `delete_key`) to interact with
keys and values relative to the configured root, prefix, and view.
""" # noqa: E501
import winreg
import inspect
from typing import Any, List, Tuple, Dict, Optional
import logging
from .registry_base import (
    put_registry_value,
    put_registry_subkey,
    get_registry_value,
    list_registry_values,
    list_registry_subkeys,
    head_registry_key,
    delete_registry_value,
    delete_registry_key,
)
from .registry_errors import RegistryError, RegistryKeyNotFoundError, RegistryValueNotFoundError, \
    RegistryKeyNotEmptyError, RegistryPermissionError
from .elevation_check import is_elevated
from .registry_types import RegistryValue # Import RegistryValue

# --- Import functions and constants from registry_translation ---
from .registry_translation import (
    _normalize_registry_type_input,
    _infer_registry_type_for_new_value,
    _validate_and_convert_data_for_type,
    REG_SZ, REG_EXPAND_SZ, REG_BINARY, REG_DWORD, REG_QWORD, REG_MULTI_SZ
)
# --- End registry_translation imports ---

logger = logging.getLogger(__name__)


# Define the root key names corresponding to the integer values for error messages
# This is a partial map used for specific error messages related to elevation
_ELEVATION_REQUIRED_ROOT_KEY_NAMES = {
    winreg.HKEY_LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
    winreg.HKEY_USERS: "HKEY_USERS",
    winreg.HKEY_CLASSES_ROOT: "HKEY_CLASSES_ROOT",
    # Add abbreviations for consistency if needed, but the full names are fine for errors
    # winreg.HKEY_CLASSES_ROOT: "HKCR",
    winreg.HKEY_CURRENT_CONFIG: "HKEY_CURRENT_CONFIG",
}
def _create_root_key_mapping():
    """
    Dynamically create a mapping of root key names to their values. Used so users can specify the base key by name in
    addition to int
    """
    mapping = {}

    # Get all constants from winreg
    for name, value in inspect.getmembers(winreg):
        # Looking for HKEY constants
        if name.startswith('HKEY_') and isinstance(value, int):
            mapping[name] = value

            # Add abbreviation if it's one of the common ones
            if name == 'HKEY_CLASSES_ROOT':
                mapping['HKCR'] = value
            elif name == 'HKEY_CURRENT_USER':
                mapping['HKCU'] = value
            elif name == 'HKEY_LOCAL_MACHINE':
                mapping['HKLM'] = value
            elif name == 'HKEY_USERS':
                mapping['HKU'] = value

    return mapping


# Then use this in the get_root_key function
ROOT_KEY_MAPPING = _create_root_key_mapping()

# Create a reverse mapping from integer value to string name for the root_key_name property
# Prioritize abbreviations for common keys where available
_ROOT_KEY_INT_TO_NAME = {
    value: name for name, value in ROOT_KEY_MAPPING.items()
}
# Overwrite with abbreviations for common keys for the property display
_ROOT_KEY_INT_TO_NAME[winreg.HKEY_CLASSES_ROOT] = "HKCR"
_ROOT_KEY_INT_TO_NAME[winreg.HKEY_CURRENT_USER] = "HKCU"
_ROOT_KEY_INT_TO_NAME[winreg.HKEY_LOCAL_MACHINE] = "HKLM"
_ROOT_KEY_INT_TO_NAME[winreg.HKEY_USERS] = "HKU"


def normalize_root_key(key_identifier : int | str) -> int:
    """
    Helper function to get the root key value from a string or int.
    Allows users to specify the base key by name in addition to int.
    """
    if isinstance(key_identifier, int):
        return key_identifier
    elif isinstance(key_identifier, str):
        key_upper = key_identifier.upper()
        if key_upper in ROOT_KEY_MAPPING:
            return ROOT_KEY_MAPPING[key_upper]
        else:
            raise ValueError(f"Unknown root key: {key_identifier}. Valid keys are: {', '.join(ROOT_KEY_MAPPING.keys())}")
    else:
        raise TypeError("Root key must be an integer or string")
# Add HKEY_CLASSES_ROOT and HKEY_CURRENT_CONFIG to the set of keys that typically require elevation
_ELEVATION_REQUIRED_ROOT_KEYS = {
    winreg.HKEY_LOCAL_MACHINE,
    winreg.HKEY_USERS,
    winreg.HKEY_CLASSES_ROOT,
    winreg.HKEY_CURRENT_CONFIG,
}


class RegistryRoot:
    def __init__(
        self,
        root_key: int | str,
        root_prefix: str = None,
        access_32bit_view: bool = False,
        read_only: bool = False,
        ignore_elevation_check: bool = False,
    ):
        """Initializes a RegistryRoot instance.

        Args:
            root_key (int | str): Handle or name of the root registry hive (e.g., winreg.HKEY_CURRENT_USER, "HKLM").
            root_prefix (str, optional): A base path prefix under the root key. All operations

                                         will be relative to this prefix. Defaults to None (no prefix).
            access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows.
                                      Defaults to False (accesses the native view).
        """
        self.root_key: int = normalize_root_key(root_key)

        self.root_prefix = root_prefix # Keep root_prefix as None if passed None
        self._access_32bit_view = access_32bit_view # Store the flag
        self._read_only = read_only # Store the read-only flag
        self._ignore_elevation_check = ignore_elevation_check # Store the ignore flag

        # Cache for elevation status:
        # None: Not yet checked for this instance.
        # True: Checked and process is elevated OR ignore_elevation_check is True.
        # False: Checked and process is NOT elevated.
        # Initialize to True if ignoring the check, otherwise None.
        self._is_elevated_cached: Optional[bool] = True if ignore_elevation_check else None

    @property
    def root_key_name(self) -> str:
        """The string name of the root registry hive (e.g., "HKCU", "HKEY_LOCAL_MACHINE")."""
        return _ROOT_KEY_INT_TO_NAME.get(self.root_key, f"UnknownRoot({self.root_key})")

    def _check_write_permission(self) -> None:
        """
        Internal helper to check if a write/delete operation is permitted
        based on read_only flag, root key, and process elevation status.

        Raises:
            RegistryPermissionError: If the operation is not permitted.
        """
        if self._read_only:
            raise RegistryPermissionError("Cannot perform write/delete operation in read-only mode.")

        # Check if the root key typically requires elevation for write operations
        if self.root_key in _ELEVATION_REQUIRED_ROOT_KEYS:
            # Check if elevation status for this instance is already determined
            # This check is skipped if ignore_elevation_check was True (handled by _is_elevated_cached initial value).
            if self._is_elevated_cached is None:
                # Determine and cache the elevation status the first time it's needed
                try:
                    self._is_elevated_cached = is_elevated()
                except OSError as e:
                    # Handle potential failure of is_elevated() itself.
                    root_key_name = _ELEVATION_REQUIRED_ROOT_KEY_NAMES.get(self.root_key, str(self.root_key))
                    # Wrap the OSError in a RegistryPermissionError for consistency
                    raise RegistryPermissionError(f"Failed to determine process elevation status required for write/delete operations on root key '{root_key_name}' ({self.root_key}). Underlying check failed: {e}") from e # Chain the exception

            # If the process is not elevated (and we are not ignoring the check)
            if not self._is_elevated_cached:
                root_key_name = _ELEVATION_REQUIRED_ROOT_KEY_NAMES.get(self.root_key, str(self.root_key))
                raise RegistryPermissionError(f"Write/delete operation on root key '{root_key_name}' ({self.root_key}) typically requires elevated (administrator) privileges, but the current process is not elevated.")

    def put_registry_value(
        self,
        key_path:str,
        value_name:str,
        value_data:Any,
        *,
        value_type: Optional[int | str] = None,
    ) -> None:
        """
        Create or update a registry value under the root key and prefix,
        creating its key path if necessary.

        Args:
            key_path (str): Subkey path relative to the root prefix.
            value_name (str): Name of the value ("" for default).
            value_data (Any): Value data to store.
            value_type (Optional[int | str]): Registry data type (e.g., winreg.REG_SZ, "REG_DWORD").
                                              If None, the type is inferred from value_data.

        Raises:
            TypeError: If value_data is incompatible with the specified or inferred type.
            RegistryPermissionError: If setting the value is denied.
            RegistryError: For other registry errors.
        """
        self._check_write_permission()

        final_value_data = value_data
        final_value_type = value_type

        if final_value_type is None:
            final_value_data, final_value_type_int = _infer_registry_type_for_new_value(value_data) # This function remains internal
        else:
            final_value_type_int = _normalize_registry_type_input(final_value_type)
            final_value_data = _validate_and_convert_data_for_type(value_data, final_value_type_int)

        return put_registry_value(
            root_key = self.root_key,
            key_path = key_path,
            value_name = value_name,
            value_data = final_value_data,
            value_type = final_value_type_int,
            root_prefix = self.root_prefix,
            access_32bit_view = self._access_32bit_view,
            )

    def put_registry_subkey(
        self,
        key_path: str,
        subkey_name: str,
    ) -> None:
        """
        Create a new subkey under the root key and prefix.

        Args:
            key_path (str): Parent key path relative to the root prefix.
            subkey_name (str): Name of the subkey to create.

        Raises:
            RegistryPermissionError: If creation is denied.
            RegistryError: For other registry errors.
        """
        self._check_write_permission()

        return put_registry_subkey(
            root_key=self.root_key,
            key_path=key_path,
            subkey_name=subkey_name,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def get_registry_value(
        self, key_path: str,
        value_name: str,
    ) -> RegistryValue:
        """
        Retrieve the data and type of a registry value under the root key and prefix.

        Args:
            key_path (str): Key path relative to the root prefix.
            value_name (str): Name of the value ("" for default).

        Returns:
            RegistryValue: An object representing the registry value.

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryValueNotFoundError: If the value does not exist.
            RegistryPermissionError: If read access is denied.
            RegistryError: For other registry errors.
        """
        return get_registry_value(
            root_key=self.root_key,
            key_path=key_path,
            value_name=value_name,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def list_registry_values(
        self, key_path: str,
    ) -> List[RegistryValue]:
        """
        List all values (including default) under a registry key relative to the root key and prefix.

        Args:
            key_path (str): Key path relative to the root prefix.

        Returns:
            List[RegistryValue]: A list of RegistryValue objects.

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryPermissionError: If read access is denied.
            RegistryError: For other registry errors.
        """
        return list_registry_values(
            root_key=self.root_key,
            key_path=key_path,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def list_registry_subkeys(
        self, key_path: str,
    ) -> List[str]:
        """
        List the immediate subkey names under a registry key relative to the root key and prefix.

        Args:
            key_path (str): Key path relative to the root prefix.

        Returns:
            List[str]: The names of each subkey.

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryPermissionError: If read access is denied.
            RegistryError: For other registry errors.
        """
        return list_registry_subkeys(
            root_key=self.root_key,
            key_path=key_path,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def head_registry_key(
        self, key_path: str,
    ) -> Dict[str, Any]:
        """
        Retrieve metadata (counts and last write time) for a registry key relative to the root key and prefix.

        Args:
            key_path (str): Key path relative to the root prefix.

        Returns:
            Dict[str, Any]:
                num_subkeys (int): Number of immediate subkeys.
                num_values (int): Number of values.
                last_write_time (datetime): Last write time as UTC datetime.

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryPermissionError: If read access is denied.
            RegistryError: For other registry errors.
        """
        return head_registry_key(
            root_key=self.root_key,
            key_path=key_path,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def delete_registry_value(
        self, key_path: str,
        value_name: str,
    ) -> None:
        """
        Delete a value from a registry key relative to the root key and prefix; no error if the value is missing.

        Args:
            key_path (str): Key path relative to the root prefix.
            value_name (str): Name of the value to delete ("" for default).

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryPermissionError: If delete access is denied.
            RegistryError: For other registry errors.
        """
        self._check_write_permission()
        return delete_registry_value(
            root_key=self.root_key,
            key_path=key_path,
            value_name=value_name,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )

    def delete_registry_key(
        self, key_path: str,
    ) -> None:
        """
        Delete an empty registry key relative to the root key and prefix; errors if the key is non-empty or root.

        Args:
            key_path (str): Key path relative to the root prefix; cannot be "".

        Raises:
            ValueError: If attempting to delete the root key (relative path is empty).
            RegistryKeyNotFoundError: If the key does not exist.
            RegistryKeyNotEmptyError: If the key has subkeys or values.
            RegistryPermissionError: If delete access is denied.
            RegistryError: For other registry errors.
        """
        self._check_write_permission()
        return delete_registry_key(
            root_key=self.root_key,
            key_path=key_path,
            root_prefix=self.root_prefix,
            access_32bit_view=self._access_32bit_view,
        )
