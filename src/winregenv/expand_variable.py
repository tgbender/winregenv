"""
Provides functionality to expand environment variable strings using the
Windows API.

This is particularly useful for processing REG_EXPAND_SZ registry values.
"""

import ctypes
from ctypes import wintypes
import sys
from typing import Optional

# --- Platform Check ---
# This code is specific to Windows. Raise an error if run on other platforms.
if sys.platform != "win32":
    # Raise immediately on import if not on Windows
    raise NotImplementedError("This module requires Windows APIs and only runs on Windows.")

# --- Load necessary Windows API libraries and define function signatures ---
# Defining argtypes and restype is a crucial ctypes best practice for robustness.
# It helps ctypes marshal data correctly and catch type errors early.

# kernel32.dll contains process and environment functions
try:
    kernel32 = ctypes.windll.kernel32
except AttributeError:
    # This should be caught by the sys.platform check, but included for robustness
    raise OSError("Failed to load kernel32.dll. Ensure you are on Windows.")

# Define the function signature for ExpandEnvironmentStringsW (Unicode version)
# DWORD ExpandEnvironmentStringsW(
#   [in]            LPCWSTR lpSrc,
#   [out, optional] LPWSTR  lpDst,
#   [in]            DWORD  nSize
# );
kernel32.ExpandEnvironmentStringsW.argtypes = [
    wintypes.LPCWSTR,  # lpSrc: Input string (Unicode)
    wintypes.LPWSTR,   # lpDst: Output buffer (Unicode)
    wintypes.DWORD     # nSize: Size of output buffer in characters
]
# Return value is the required buffer size (including null terminator) or 0 on error
kernel32.ExpandEnvironmentStringsW.restype = wintypes.DWORD

# Define a reasonable initial buffer size for the first attempt
# MAX_PATH is 260, but expanded strings can be longer. 1024 is a safer start.
_INITIAL_BUFFER_SIZE = 1024

def expand_environment_strings(source_string: str) -> str:
    """
    Expands environment-variable strings in a source string using the
    Windows API function ExpandEnvironmentStringsW.

    Environment variables are in the form %VARIABLE%. Case is ignored.
    If a variable is not found, the %VARIABLE% portion is left unexpanded.

    Args:
        source_string (str): The string containing environment variables
                             to be expanded.

    Returns:
        str: The expanded string.

    Raises:
        TypeError: If source_string is not a string.
        OSError: If the underlying Windows API call fails for reasons
                 other than insufficient buffer size.
    """
    # The platform check is done at the module level, but a function-level
    # check can be added if this function might be called directly without
    # the module being imported first (less likely in a package).
    # if sys.platform != "win32":
    #      raise NotImplementedError("Environment variable expansion using Windows API is only supported on Windows.")

    if not isinstance(source_string, str):
        raise TypeError("source_string must be a string")

    # Use the two-pass approach to handle buffer sizing:
    # 1. Call with a small buffer to get the required size.
    # 2. Allocate a buffer of the required size.
    # 3. Call again with the correctly sized buffer.

    buffer_size = _INITIAL_BUFFER_SIZE
    while True:
        # Create a buffer of the current size.
        # ctypes.create_unicode_buffer allocates memory and manages it.
        buffer = ctypes.create_unicode_buffer(buffer_size)

        # Call the API function.
        # lpSrc and lpDst must be different buffers.
        # The return value is the required size (including null) on success
        # or if the buffer is too small, or 0 on other errors.
        required_size = kernel32.ExpandEnvironmentStringsW(
            source_string,
            buffer,
            buffer_size
        )

        # Check the return value.
        if required_size == 0:
            # An error occurred (other than insufficient buffer).
            error_code = ctypes.get_last_error()
            # Clear the last error after retrieving it (good practice)
            ctypes.set_last_error(0)
            # Raise a ctypes.WinError which automatically formats the message
            # Include the original string in the error message for context.
            raise ctypes.WinError(error_code, f"Failed to expand environment strings for '{source_string}'")
        elif required_size <= buffer_size:
            # Success! The required size fits within or equals the buffer size.
            # required_size includes the null terminator.
            # buffer.value gives the string up to the null terminator.
            return buffer.value
        else:
            # Buffer was too small. required_size is the correct size needed.
            buffer_size = required_size
            # Loop will continue with the new, larger buffer_size.

# Example Usage (optional, for testing the module directly)
if __name__ == "__main__":
    try:
        print(f"Expanding %TEMP%: {expand_environment_strings('%TEMP%')}")
        print(f"Expanding %USERPROFILE%: {expand_environment_strings('%USERPROFILE%')}")

        # Build the string with backslashes outside the f-string
        system32_path = r'%SystemRoot%\System32' # Using a raw string is good practice for paths

        # Use the built string in the f-string or format
        print(f"Expanding {system32_path}: {expand_environment_strings(system32_path)}")
        # Alternatively, using .format():
        # print("Expanding {}: {}".format(system32_path, expand_environment_strings(system32_path)))


        print(f"Expanding %NON_EXISTENT_VAR%: {expand_environment_strings('%NON_EXISTENT_VAR%')}") # Should remain unexpanded

        # Build the mixed string outside
        mixed_string = 'User: %USERNAME%, Temp: %TEMP%'
        print(f"Expanding mixed string: {expand_environment_strings(mixed_string)}")

        # Build the path string outside
        user_path_string = 'Path: %PATH%'
        print(f"Expanding user Path: {expand_environment_strings(user_path_string)}")


        # Test with a string that might exceed the initial buffer size
        # Build the long string template outside the print statement
        long_string_template_built = r"Path: %SystemRoot%\\" + "a" * 500 + r"\%TEMP%" # Using raw strings for path parts
        # Note: The string passed to expand_environment_strings should have single backslashes
        # Ensure the string passed to the function is correctly formatted for the function
        # In this case, the built string `long_string_template_built` already has the literal backslashes correct.

        print(f"\nExpanding potentially long string: {long_string_template_built}")

        # Pass the built string to the function
        expanded_long_string = expand_environment_strings(long_string_template_built)

        print(f"Expanded: {expanded_long_string}")
        print(f"Length: {len(expanded_long_string)}")


    except NotImplementedError as e:
        print(f"Error: {e}", file=sys.stderr)
    except OSError as e:
        print(f"Error expanding string: {e}", file=sys.stderr)
        if isinstance(e, ctypes.WinError):
             print(f"  Windows Error Code: {e.winerror}", file=sys.stderr)
             print(f"  Message: {e.strerror}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

