"""Basic Windows registry operations.

This module provides functions for interacting with the Windows registry,
including creation, querying, enumeration, and deletion of keys and values,
with centralized error translation into custom exceptions.
"""

import winreg
from typing import Optional, Any, Type, List, Tuple, Dict
from ctypes.wintypes import HANDLE # Import HANDLE for type hinting
import os # Needed for os.path.split
from datetime import datetime, timezone # Needed for head_registry_key timestamp conversion and UTC

import logging

from .registry_errors import RegistryValueNotFoundError, \
    RegistryKeyNotEmptyError, _handle_winreg_error
from .registry_types import RegistryValue # Import RegistryValue
from .registry_context_managers import RegistryKey as _BaseRegistryKey

logger = logging.getLogger(__name__)

# Constants for FILETIME conversion (100-nanosecond intervals since January 1, 1601 UTC)
_EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as FILETIME
_HUNDREDS_OF_NS_ = 10000000 # Number of 100-nanosecond intervals in one second

def _join_registry_paths(
        prefix: str,
        path: str,
    ) -> str:
    """Join a registry root prefix and a subpath into a single key path.

    Args:
        prefix (str): The base registry path (may be empty).
        path (str): The sub‐path to append (may be empty).

    Returns:
        str: The combined registry path, using backslashes.
    """
    if not prefix:
        return path
    if not path:
        return prefix
    # Use os.path.join which handles separators correctly, but replace / with \ for registry
    return os.path.join(prefix, path).replace('/', '\\')


# Define a new RegistryKey class in this module that inherits from the base one.
# Ensures backwards compatibility across test suite.
class RegistryKey(_BaseRegistryKey):
    """
    Context manager for Windows registry key handles (re-exported for backward compatibility).
    The actual implementation is in registry_context_managers.py.
    """
    pass # No changes needed, it inherits everything

def ensure_registry_key_exists(
        root_key: int,
        key_path: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> None:
    """Ensure that a registry key path exists, creating any missing keys.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Subkey path to ensure, relative to root_prefix.
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Raises:
        RegistryPermissionError: If creation is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)

    if not full_path:
        # Root key always exists
        return

    try:
        # Combine base access with WOW64 flag if requested
        effective_access = winreg.KEY_WRITE
        if access_32bit_view:
            effective_access |= winreg.KEY_WOW64_32KEY

        # winreg.CreateKeyEx opens the key if it exists, or creates it if it doesn't.
        # It creates intermediate keys as needed.
        # We need KEY_CREATE_SUB_KEY access to create keys.
        # We open with KEY_ALL_ACCESS or KEY_WRITE for simplicity, as CreateKeyEx
        # often requires more than just KEY_CREATE_SUB_KEY to open existing keys.
        # Let's use KEY_WRITE which includes KEY_CREATE_SUB_KEY and KEY_SET_VALUE.
        # The handle returned by CreateKeyEx needs to be closed.
        handle = None # Initialize handle to None
        try:
            handle = winreg.CreateKeyEx(root_key, full_path, 0, effective_access) # Use effective_access
        finally:
            if handle: winreg.CloseKey(handle)
    except OSError as e: # Changed from WindowsError
        _handle_winreg_error(e, full_path)


def put_registry_value(
        root_key: int,
        key_path: str,
        value_name: str,
        value_data: Any,
        value_type: int,
        root_prefix: str = "",
        access_32bit_view: bool = False,
    ) -> None:
    """Create or update a registry value, creating its key if necessary.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Subkey path relative to root_prefix.
        value_name (str): Name of the value ("" for default).
        value_data (Any): Value data to store (must be compatible with value_type).
        value_type (int): Registry data type (e.g., winreg.REG_SZ).
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Raises:
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryPermissionError: If setting the value is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)

    # Ensure the parent key exists before attempting to set the value
    ensure_registry_key_exists(root_key, full_path, access_32bit_view=access_32bit_view)

    # Type inference and data validation/conversion are handled by the caller (RegistryRoot).
    # This function expects a valid integer value_type and compatible value_data
    # as required by winreg.SetValueEx.
    try:
        # Open the key with write access, passing the flag
        with RegistryKey(root_key, full_path, winreg.KEY_SET_VALUE, access_32bit_view=access_32bit_view) as key:
            winreg.SetValueEx(key, value_name, 0, value_type, value_data)

    except OSError as e:
        _handle_winreg_error(e, full_path, value_name)


def put_registry_subkey(
        root_key: int,
        key_path: str,
        subkey_name: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> None:
    """Create a new subkey under an existing registry key.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Parent key path relative to root_prefix.
        subkey_name (str): Name of the subkey to create.
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Raises:
        RegistryPermissionError: If creation is denied.
        RegistryError: For other registry errors.
    """
    full_parent_path = _join_registry_paths(root_prefix, key_path)
    full_subkey_path = _join_registry_paths(full_parent_path, subkey_name)

    # Ensure the parent key exists, passing the flag
    ensure_registry_key_exists(root_key, full_parent_path, access_32bit_view=access_32bit_view)

    try:
        # Combine base access with WOW64 flag if requested
        effective_access = winreg.KEY_WRITE
        if access_32bit_view:
            effective_access |= winreg.KEY_WOW64_32KEY

        # winreg.CreateKeyEx is used here as it will create the key if it doesn't exist
        # and return a handle. We need to close this handle.
        # We need KEY_WRITE access on the new key path.
        handle = None # Initialize handle to None
        try:
            handle = winreg.CreateKeyEx(root_key, full_subkey_path, 0, effective_access) # Use effective_access
        finally:
            if handle: winreg.CloseKey(handle)
    except OSError as e: # Changed from WindowsError
        _handle_winreg_error(e, full_subkey_path)


def get_registry_value(
        root_key: int,
        key_path: str,
        value_name: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> RegistryValue:
    """Retrieve the data and type of a registry value.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix.
        value_name (str): Name of the value ("" for default).
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Returns:
        RegistryValue: An object representing the registry value.

    Raises:
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryValueNotFoundError: If the value does not exist.
        RegistryPermissionError: If read access is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)

    try:
        # Open the key with read access, passing the flag
        # Errors from RegistryKey.__enter__ (OpenKey) are caught by the outer except block.
        with RegistryKey(root_key, full_path, winreg.KEY_READ, access_32bit_view=access_32bit_view) as key:
            try:
                # Attempt to query the specific value
                # Errors from QueryValueEx are caught by this inner except block.
                value_data, value_type = winreg.QueryValueEx(key, value_name) # type: ignore # winreg returns tuple
                return RegistryValue(value_name, value_data, value_type)
            except OSError as e:
                # Handle errors specifically from QueryValueEx
                err_code = getattr(e, 'winerror', None)
                if err_code == 2: # ERROR_FILE_NOT_FOUND
                    # If QueryValueEx fails with ERROR_FILE_NOT_FOUND, it means the value doesn't exist.
                    raise RegistryValueNotFoundError(f"Registry value '{value_name}' not found in key '{full_path}'.") from e
                else:
                    # Handle other QueryValueEx errors (e.g., permission denied on the value itself)
                    _handle_winreg_error(e, full_path, value_name)
    except OSError as e:
        # Handle errors specifically from RegistryKey.__enter__ (OpenKey)
        # This will catch RegistryKeyNotFoundError, RegistryPermissionError, etc.,
        # when trying to open the key itself.
        _handle_winreg_error(e, full_path) # No value_name here, as the key itself failed to open


def list_registry_values(
        root_key: int,
        key_path: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> List[RegistryValue]:
    """List all values (including default) under a registry key.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix.
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Returns:
        List[RegistryValue]: A list of RegistryValue objects.

    Raises:
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryPermissionError: If read access is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)
    values = []
    try:
        # Pass the flag to RegistryKey
        with RegistryKey(root_key, full_path, winreg.KEY_READ, access_32bit_view=access_32bit_view) as key:
            # Enumerate named values (this includes the default value if it exists)
            i = 0
            while True:
                try:
                    name, data, vtype = winreg.EnumValue(key, i)
                    values.append(RegistryValue(name, data, vtype))
                    i += 1
                except OSError as e: # Changed from WindowsError
                    # ERROR_NO_MORE_ITEMS (259) indicates the end of enumeration
                    if getattr(e, 'winerror', None) == 259:
                        break
                    # Handle other OSErrors during enumeration
                    _handle_winreg_error(e, full_path)

    except OSError as e: # Changed from (OSError, WindowsError)
        # OSError from RegistryKey if key cannot be opened
        _handle_winreg_error(e, full_path)

    return values


def list_registry_subkeys(
        root_key: int,
        key_path: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> List[str]:
    """List the immediate subkey names under a registry key.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix.
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Returns:
        List[str]: The names of each subkey.

    Raises:
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryPermissionError: If read access is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)
    subkeys = []
    try:
        # Need KEY_ENUMERATE_SUB_KEYS access
        # Pass the flag to RegistryKey
        with RegistryKey(root_key, full_path, winreg.KEY_ENUMERATE_SUB_KEYS, access_32bit_view=access_32bit_view) as key:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                    subkeys.append(name)
                    i += 1
                except OSError as e: # Changed from WindowsError
                    # ERROR_NO_MORE_ITEMS (259) indicates the end of enumeration
                    if getattr(e, 'winerror', None) == 259:
                        break
                    # Handle other OSErrors during enumeration
                    _handle_winreg_error(e, full_path)

    except OSError as e: # Changed from (OSError, WindowsError)
        # OSError from RegistryKey if key cannot be opened
        _handle_winreg_error(e, full_path)

    return subkeys


def head_registry_key(
        root_key: int,
        key_path: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> Dict[str, Any]:
    """Retrieve metadata (counts and last write time) for a registry key.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix.
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

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
    full_path = _join_registry_paths(root_prefix, key_path)
    try:
        # Need KEY_QUERY_VALUE and KEY_ENUMERATE_SUB_KEYS access for QueryInfoKey
        # KEY_READ includes these.
        # Pass the flag to RegistryKey
        with RegistryKey(root_key, full_path, winreg.KEY_READ, access_32bit_view=access_32bit_view) as key:
            # QueryInfoKey returns: num_subkeys, num_values, last_write_time (as an integer FILETIME)
            num_subkeys, num_values, last_write_time_ft = winreg.QueryInfoKey(key)

            # Convert FILETIME (100-nanosecond intervals since 1601-01-01 UTC) to datetime
            # winreg documentation states it returns an integer.
            # Calculate seconds since Unix epoch (1970-01-01 UTC)
            unix_timestamp = (last_write_time_ft - _EPOCH_AS_FILETIME) / _HUNDREDS_OF_NS_
            # Create a timezone-aware UTC datetime object
            last_write_time = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)

            return {
                "num_subkeys": num_subkeys,
                "num_values": num_values,
                "last_write_time": last_write_time, # Now correctly converted
            }

    except OSError as e: # Changed from (OSError, WindowsError)
        # OSError from RegistryKey if key cannot be opened
        _handle_winreg_error(e, full_path)


def delete_registry_value(
        root_key: int,
        key_path: str,
        value_name: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> None:
    """Delete a value from a registry key; no error if the value is missing.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix.
        value_name (str): Name of the value to delete ("" for default).
        root_prefix (str): Base sub‐path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Raises:
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryPermissionError: If delete access is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)
    try:
        # Open the key with KEY_SET_VALUE access (needed for DeleteValue)
        # Pass the flag to RegistryKey
        with RegistryKey(root_key, full_path, winreg.KEY_SET_VALUE, access_32bit_view=access_32bit_view) as key:
            try:
                winreg.DeleteValue(key, value_name)
            except OSError as e: # Changed from WindowsError, catch OSError
                # ERROR_FILE_NOT_FOUND (2) means the value doesn't exist. This is allowed (idempotent).
                # Use getattr for safe access to winerror
                if getattr(e, 'winerror', None) == 2:
                    pass # Value not found, success according to spec
                else:
                    # Handle other OSErrors during deletion
                    _handle_winreg_error(e, full_path, value_name)

    except OSError as e: # Changed from (OSError, WindowsError)
        # OSError from RegistryKey if key cannot be opened (e.g., key_path not found)
        # This will correctly raise RegistryKeyNotFoundError via _handle_winreg_error
        _handle_winreg_error(e, full_path)


def delete_registry_key(
        root_key: int,
        key_path: str,
        root_prefix: str = "",
        access_32bit_view: bool = False, # Add parameter
    ) -> None:
    """Delete an empty registry key; errors if the key is non‑empty or root.

    Args:
        root_key (int): Handle of the root registry hive.
        key_path (str): Key path relative to root_prefix; cannot be "".
        root_prefix (str): Base sub‑path under root_key (may be empty).
        access_32bit_view (bool): If True, access the 32-bit registry view on 64-bit Windows. Defaults to False.

    Raises:
        ValueError: If attempting to delete the root key.
        RegistryKeyNotFoundError: If the key does not exist.
        RegistryKeyNotEmptyError: If the key has subkeys or values.
        RegistryPermissionError: If delete access is denied.
        RegistryError: For other registry errors.
    """
    full_path = _join_registry_paths(root_prefix, key_path)

    if not full_path:
        raise ValueError("Cannot delete the root registry key.")

    # 1. Check if the key exists and is empty (no subkeys, no values)
    try:
        # Open the key to be deleted with read access to query info
        # Use the context manager for safe handle handling
        # Pass the flag to RegistryKey
        with RegistryKey(root_key, full_path, winreg.KEY_READ, access_32bit_view=access_32bit_view) as key_to_delete_handle:
            # QueryInfoKey returns: num_subkeys, num_values, last_modified_time
            num_subkeys, num_values, _ = winreg.QueryInfoKey(key_to_delete_handle)


            if num_subkeys > 0 or num_values > 0:
                # Raise the specific error if not empty
                raise RegistryKeyNotEmptyError(f"Registry key '{full_path}' is not empty (contains {num_subkeys} subkeys and {num_values} values). Cannot delete non-empty keys.")

        # If we reach here, the key exists and is empty. Proceed to delete.

    except OSError as e:
        # Catch errors from the RegistryKey context manager (OpenKey failures)
        # _handle_winreg_error will raise the appropriate custom exception
        _handle_winreg_error(e, full_path)
        # The function exits here if an error occurred during the check.
        # No need for explicit return, exception propagates.


    # 2. If the key is empty, delete it using DeleteKey on the parent
    # Split the full path to get the parent path and the name of the key to delete
    parent_full_path, subkey_name = os.path.split(full_path)

    try:
        # Open the parent key with KEY_CREATE_SUB_KEY access (needed for DeleteKey)
        # Use the context manager for safe handle handling
        # Pass the flag to RegistryKey when opening the PARENT
        with RegistryKey(root_key, parent_full_path, winreg.KEY_CREATE_SUB_KEY, access_32bit_view=access_32bit_view) as parent_key_handle:
            try:
                # DeleteKey itself doesn't take the WOW64 flag directly; it's the parent handle's view that matters.
                winreg.DeleteKey(parent_key_handle, subkey_name)
            except OSError as e: # Changed from WindowsError
                # Handle potential OSErrors during the actual deletion
                # ERROR_FILE_NOT_FOUND (2) might occur if the key was deleted between check and delete (race condition)
                # ERROR_ACCESS_DENIED (5) if permission is denied for deletion (different from read permission check)
                # ERROR_DIR_NOT_EMPTY (247) should not happen due to the check, but handle defensively
                _handle_winreg_error(e, full_path) # Pass the full path for the error message

    except OSError as e:
        # Catch errors opening the parent key (less likely if child existed, but possible)
        # _handle_winreg_error will raise the appropriate custom exception (e.g., RegistryPermissionError)
        _handle_winreg_error(e, parent_full_path) # Pass parent path for the error message
