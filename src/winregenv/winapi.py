# -*- coding: utf-8 -*-
"""
This module provides Windows API utilities, specifically for broadcasting
system-wide messages like WM_SETTINGCHANGE.
"""

import ctypes
import sys
import logging
from ctypes import wintypes
from typing import Optional, Literal, TYPE_CHECKING
from .registry_errors import RegistryError

# Configure logging for this module
logger = logging.getLogger(__name__)

__all__ = ["broadcast_setting_change"]

# --- Platform Check ---
# This code is specific to Windows. Allow import on non-Windows platforms for tooling,
# but raise NotImplementedError only when trying to use the functionality.
if sys.platform != "win32":
    logger.warning("This module is only functional on Windows (win32). Some functionality will raise NotImplementedError.")

# For type checking (without importing), use Literal for setting_name
if TYPE_CHECKING:
    SettingName = Literal["Environment", "intl", "Policy", "Windows", None]
else:
    SettingName = str

# --- Define necessary Windows API constants and function signatures ---

# For SendMessageTimeout:
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002

# Error codes
ERROR_TIMEOUT = 1460  # From WinError.h

# Load user32.dll for messaging functions
try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
except AttributeError:
    # This should be caught by the sys.platform check, but included for robustness
    raise OSError("Failed to load user32.dll. Ensure you are on Windows.")


# BOOL SendMessageTimeoutW(
#   HWND       hWnd,
#   UINT       Msg,
#   WPARAM     wParam,
#   LPARAM     lParam,
#   UINT       fuFlags,
#   UINT       uTimeout,
#   PDWORD_PTR lpdwResult
# );
# Note: LPARAM can be a string (LPWSTR) for WM_SETTINGCHANGE.
# PDWORD_PTR is POINTER(ctypes.c_ulong_p) or POINTER(wintypes.DWORD) depending on architecture,
# but for simple status, POINTER(wintypes.DWORD) is often sufficient.
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND,       # hWnd
    wintypes.UINT,       # Msg
    wintypes.WPARAM,     # wParam
    wintypes.LPWSTR,     # lParam (can be a string for WM_SETTINGCHANGE)
    wintypes.UINT,       # fuFlags
    wintypes.UINT,       # uTimeout
    ctypes.POINTER(wintypes.DWORD) # lpdwResult (using DWORD for simplicity)
]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM  # LRESULT, but often treated as BOOL for success/fail


class MessageTimeoutError(RegistryError):
    """Raised when SendMessageTimeoutW fails due to timeout."""
    def __init__(self, winerror: int, message: str):
        # pass message and winerror into RegistryError
        super().__init__(message, winerror=winerror)


def broadcast_setting_change(
    setting_name: Optional[SettingName] = "Environment",
    timeout_ms: int = 5000
) -> None:
    """
    Broadcasts a WM_SETTINGCHANGE message to all top-level windows.

    This function notifies other applications that a system-wide setting has changed,
    typically used after modifying environment variables in the registry.

    Args:
        setting_name (Optional[str]): A string indicating the area that changed.
            For environment variables, this is typically "Environment".
            If None, a general notification is sent (lParam=0).
            Common values include "Environment", "intl", "Policy", "Windows".
        timeout_ms (int): The duration, in milliseconds, to wait for the message
            to be processed. Defaults to 5000ms (5 seconds).

    Raises:
        MessageTimeoutError: If the message broadcast times out.
        OSError: If the SendMessageTimeoutW API call fails for reasons other than timeout.
        NotImplementedError: If run on a non-Windows operating system.
    """
    if sys.platform != "win32":
        raise NotImplementedError("This function requires Windows (win32).")

    # Prepare lParam
    lparam = ctypes.create_unicode_buffer(setting_name) if setting_name is not None else None

    # Variable to store the result of the broadcast (not typically used for WM_SETTINGCHANGE)
    broadcast_result = wintypes.DWORD()

    logger.debug(
        f"Broadcasting WM_SETTINGCHANGE for '{setting_name if setting_name else 'general'}' "
        f"with timeout {timeout_ms}ms."
    )

    # Call SendMessageTimeoutW
    api_result = user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,  # wParam (not used when lParam is a string for "Environment")
        lparam,
        SMTO_ABORTIFHUNG,  # Flags: abort if hung
        timeout_ms,
        ctypes.byref(broadcast_result)
    )

    if api_result == 0:
        error_code = ctypes.get_last_error()
        ctypes.set_last_error(0)  # Clear the error after getting it

        error_message = f"Failed to broadcast WM_SETTINGCHANGE for '{setting_name if setting_name else 'general'}'."

        if error_code == ERROR_TIMEOUT:
            logger.warning(
                f"WM_SETTINGCHANGE broadcast timed out after {timeout_ms}ms (Error {error_code}). "
                f"Setting name: '{setting_name if setting_name else 'general'}'."
            )
            raise MessageTimeoutError(error_code, error_message)
        else:
            logger.error(
                f"SendMessageTimeoutW failed for WM_SETTINGCHANGE. Error code: {error_code}. "
                f"Setting name: '{setting_name if setting_name else 'general'}'."
            )
            raise ctypes.WinError(error_code, error_message)
    else:
        logger.info(
            f"Successfully broadcast WM_SETTINGCHANGE for '{setting_name if setting_name else 'general'}'. "
            f"API result: {api_result}, Broadcast processing result: {broadcast_result.value}"
        )


# --- Example Usage (for direct execution of this file) ---
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Attempting to broadcast WM_SETTINGCHANGE for 'Environment'...")
    try:
        broadcast_setting_change("Environment")
        logger.info("WM_SETTINGCHANGE for 'Environment' broadcast successfully.")
    except MessageTimeoutError as e:
        logger.warning(f"WM_SETTINGCHANGE timeout: {e}")
    except OSError as e:
        logger.error(f"Failed to broadcast WM_SETTINGCHANGE: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

    logger.info("\nAttempting to broadcast general WM_SETTINGCHANGE (lParam=0)...")
    try:
        broadcast_setting_change(None)  # Test with lParam as NULL
        logger.info("General WM_SETTINGCHANGE broadcast successfully.")
    except MessageTimeoutError as e:
        logger.warning(f"WM_SETTINGCHANGE timeout: {e}")
    except OSError as e:
        logger.error(f"Failed to broadcast general WM_SETTINGCHANGE: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
