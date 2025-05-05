import winreg
from typing import Optional, Any, Type, List, Tuple, Dict
from ctypes.wintypes import HANDLE # Import HANDLE for type hinting
import os # Needed for os.path.split
from datetime import datetime, timezone # Needed for head_registry_key timestamp conversion and UTC

import logging

from .registry_errors import RegistryValueNotFoundError, \
    RegistryKeyNotEmptyError, _handle_winreg_error

logger = logging.getLogger(__name__)

class RegistryKey:
    """Context manager for Windows registry key handles.

    Ensures that OpenKey is closed via CloseKey on exit, even if errors occur
    inside the with‐block.

    Attributes:
        _root_key (int): The root hive handle (e.g. HKEY_CURRENT_USER).
        _subkey (str): The subkey path under the root.
        _access (int): Desired access rights.
        _access_32bit_view (bool): Whether to access the 32-bit registry view on 64-bit Windows.
        _key_handle (Optional[HANDLE]): The open key handle.
    """
    def __init__(self, root_key: int, subkey: str, access: int, access_32bit_view: bool = False):
        self._root_key = root_key
        self._subkey = subkey
        self._access = access
        self._access_32bit_view = access_32bit_view # Store the flag
        self._key_handle: Optional[HANDLE] = None # Use HANDLE for the handle type

    def __enter__(self) -> HANDLE: # Use HANDLE for the return type hint
        """Open the registry key and return its handle.

        Returns:
            HANDLE: The opened key handle.

        Raises:
            RegistryError or subclass: If the key cannot be opened.
        """
        try:
            # Combine base access with WOW64 flag if requested
            effective_access = self._access
            if self._access_32bit_view:
                effective_access |= winreg.KEY_WOW64_32KEY

            # winreg.OpenKey requires the root key handle, subkey string,
            # reserved (must be 0), and access rights.
            # winreg.OpenKey returns an HKEY object, which is compatible with HANDLE
            self._key_handle = winreg.OpenKey(
                self._root_key,
                self._subkey,
                0, # Reserved, must be zero
                effective_access # Use the potentially modified access mask
            )
            return self._key_handle
        except OSError as e: # Changed from WindowsError
            # Wrap WindowsError in OSError for consistency with Python's file I/O
            # and then map to custom RegistryError
            _handle_winreg_error(e, self._subkey)


    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        """Close the registry key handle on context exit."""
        if self._key_handle:
            try:
                winreg.CloseKey(self._key_handle)
            except OSError as e:  # Changed from WindowsError
                # DEBUG: report any problem closing the handle
                logger.debug(
                    "Failed to close registry key handle for '%s': WinError %s: %s",
                    self._subkey,
                    getattr(e, "winerror", None),
                    e.strerror or e,
                )
            finally:
                self._key_handle = None # Ensure it's not closed again
