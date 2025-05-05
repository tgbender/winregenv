# -*- coding: utf-8 -*-
"""
This module provides functionality to check if the current Python process
is running with elevated (administrator) privileges on Microsoft Windows.
It uses the ctypes module to interact directly with the Windows API.
"""

import ctypes
import sys
import logging # Import logging
from ctypes import wintypes
from typing import Optional, Type
from types import TracebackType

# Configure logging for this module
logger = logging.getLogger(__name__)

# --- Platform Check ---
# This code is specific to Windows. Raise an error if run on other platforms.
if sys.platform != "win32":
    raise NotImplementedError("This module requires Windows APIs and only runs on Windows.")


# --- Define necessary Windows API constants and structures ---
# These values are standard and can be found in Windows SDK header files
# (like winnt.h, security.h)

# Access rights for OpenProcessToken
TOKEN_QUERY = 0x0008

# Information class for GetTokenInformation to get the integrity level
# (Enum value defined in TOKEN_INFORMATION_CLASS)
TokenIntegrityLevel = 25 # Correct enum value for Integrity Level

# Structure for SID and attributes (used within TOKEN_MANDATORY_LABEL)
class SID_AND_ATTRIBUTES(ctypes.Structure):
    """Represents a SID and its attributes."""
    _fields_ = [
        # Corrected: PSID is represented as ctypes.c_void_p
        ('Sid', ctypes.c_void_p),      # Pointer to the SID structure
        ('Attributes', wintypes.DWORD) # Attributes associated with the SID
    ]

# Structure for Token Mandatory Label (returned by GetTokenInformation for TokenIntegrityLevel)
class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    """Contains the mandatory integrity level SID for a token."""
    _fields_ = [
        ('Label', SID_AND_ATTRIBUTES) # Contains the integrity level SID
    ]

# Integrity levels (Relative Identifiers - RIDs)
# These are standard SIDs representing different integrity levels
SECURITY_MANDATORY_UNTRUSTED_RID  = 0x00000000 # Untrusted (rarely used)
SECURITY_MANDATORY_LOW_RID        = 0x00001000 # Low integrity level
SECURITY_MANDATORY_MEDIUM_RID     = 0x00002000 # Standard user integrity level
SECURITY_MANDATORY_MEDIUM_PLUS_RID= 0x00002500 # Medium Plus integrity level (rarely used)
SECURITY_MANDATORY_HIGH_RID       = 0x00003000 # Elevated (administrator) integrity level
SECURITY_MANDATORY_SYSTEM_RID     = 0x00004000 # System integrity level
SECURITY_MANDATORY_PROTECTED_PROCESS_RID = 0x00005000 # Protected Process integrity level

# Mapping RIDs to descriptive names
INTEGRITY_LEVEL_NAMES = {
    SECURITY_MANDATORY_UNTRUSTED_RID: "Untrusted",
    SECURITY_MANDATORY_LOW_RID: "Low",
    SECURITY_MANDATORY_MEDIUM_RID: "Medium",
    SECURITY_MANDATORY_MEDIUM_PLUS_RID: "Medium Plus",
    SECURITY_MANDATORY_HIGH_RID: "High",
    SECURITY_MANDATORY_SYSTEM_RID: "System",
    SECURITY_MANDATORY_PROTECTED_PROCESS_RID: "Protected Process",
    # Add other known RIDs if necessary, or handle unknown ones below
}


# --- Load necessary Windows API libraries and define function signatures ---
# Defining argtypes and restype is a crucial ctypes best practice for robustness.
# It helps ctypes marshal data correctly and catch type errors early.

# kernel32.dll contains process and handle management functions
try:
    kernel32 = ctypes.windll.kernel32
except AttributeError:
    # This should be caught by the sys.platform check, but included for robustness
    raise OSError("Failed to load kernel32.dll. Ensure you are on Windows.")

# advapi32.dll contains security-related functions (tokens, SIDs)
try:
    advapi32 = ctypes.windll.advapi32
except AttributeError:
     # This should be caught by the sys.platform check, but included for robustness
     raise OSError("Failed to load advapi32.dll. Ensure you are on Windows.")


# HANDLE GetCurrentProcess();
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
# No argtypes needed for functions without arguments

# BOOL CloseHandle(HANDLE hObject);
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

# BOOL OpenProcessToken(HANDLE ProcessHandle, DWORD DesiredAccess, PHANDLE TokenHandle);
advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
]
advapi32.OpenProcessToken.restype = wintypes.BOOL

# BOOL GetTokenInformation(HANDLE TokenHandle, TOKEN_INFORMATION_CLASS TokenInformationClass,
#                          LPVOID TokenInformation, DWORD TokenInformationLength, PDWORD ReturnLength);
advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
]
advapi32.GetTokenInformation.restype = wintypes.BOOL

# Corrected based on MSDN: GetSidSubAuthorityCount returns a pointer to the *actual*
# SubAuthorityCount field within the SID structure, which is a UCHAR.
# PUCHAR GetSidSubAuthorityCount(PSID pSid);
advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p] # Corrected: PSID is ctypes.c_void_p
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte) # PUCHAR

# PDWORD GetSidSubAuthority(PSID pSid, DWORD nSubAuthority);
advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD] # Corrected: PSID is ctypes.c_void_p
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD) # PDWORD


# --- Context Managers for Resource Handling ---

class WindowsHandle:
    """
    A context manager for safely managing Windows handles that require closing
    via kernel32.CloseHandle.

    Ensures the handle is closed even if errors occur within the 'with' block.
    """
    def __init__(self, handle_value: wintypes.HANDLE):
        """
        Adds a handle to the context manager.

        Args:
            handle_value: The Windows HANDLE obtained from an API call.
                          Should be a valid handle or a zero/invalid handle.
        """
        # Store the handle. wintypes.HANDLE is often just an integer wrapper.
        # We store the object itself.
        self._handle = handle_value

    def __enter__(self) -> wintypes.HANDLE:
        """Returns the handle value when entering the 'with' block."""
        return self._handle

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        """
        Closes the handle upon exiting the 'with' block.

        Args:
            exc_type: Exception type if an exception occurred in the block.
            exc_val: Exception value if an exception occurred.
            exc_tb: Traceback object if an exception occurred.
        """
        # A handle value of 0 or -1 (INVALID_HANDLE_VALUE) is typically invalid
        # Check the underlying value of the handle object
        if self._handle and self._handle.value not in (0, -1):
            kernel32.CloseHandle(self._handle)
        # Return None (implicitly) to propagate exceptions if they occurred.

class ProcessToken(WindowsHandle):
    """
    Context manager specifically to acquire and release the current process's
    access token handle using OpenProcessToken and CloseHandle.

    Inherits from WindowsHandle to leverage its __exit__ method for closing.
    Raises OSError if the token cannot be opened.
    """
    def __init__(self):
        """
        Acquires the current process token.

        Raises:
            OSError: If OpenProcessToken fails, containing the Windows error code.
        """
        process_handle = kernel32.GetCurrentProcess() # Pseudo-handle, doesn't need closing
        token_handle = wintypes.HANDLE(0) # Initialize to invalid handle value

        success = advapi32.OpenProcessToken(
            process_handle,
            TOKEN_QUERY,
            ctypes.byref(token_handle)
        )

        if not success:
            error_code = ctypes.get_last_error()
            # It's good practice to clear the last error after retrieving it
            ctypes.set_last_error(0)
            # Raise a ctypes.WinError which automatically formats the error message
            logger.error(f"Failed to open process token. Error code: {error_code}")
            raise ctypes.WinError(error_code, "Failed to open process token")

        # Initialize the base class with the successfully acquired handle
        super().__init__(token_handle)


# --- Core Function to Get Integrity Level ---

def get_integrity_level() -> int:
    """
    Retrieves the integrity level (as a numerical Relative Identifier - RID)
    of the current process token on Windows.

    This is a harmless, read-only check.

    Returns:
        The integer RID representing the process's integrity level
        (e.g., SECURITY_MANDATORY_MEDIUM_RID, SECURITY_MANDATORY_HIGH_RID).

    Raises:
        NotImplementedError: If run on a non-Windows operating system.
        OSError: If any underlying Windows API call fails. The error
                 message will contain details and the Windows error code.
        ValueError: If the integrity SID structure is unexpected (e.g., NULL pointer, zero sub-authorities).
    """
    # The ProcessToken context manager handles acquiring and releasing the token handle.
    # If acquiring fails (__init__ raises OSError), the 'with' block is never entered,
    # and the exception propagates.
    try:
        with ProcessToken() as token:
            # --- Get the required buffer size for the token integrity level ---
            buffer_size = wintypes.DWORD()
            # Call GetTokenInformation with null buffer to get required size.
            # This call is expected to fail with ERROR_INSUFFICIENT_BUFFER (122).
            # We check the return value *and* the last error code.
            success = advapi32.GetTokenInformation(
                token,
                TokenIntegrityLevel, # Requesting the integrity level info
                None,                # No buffer provided yet
                0,                   # Buffer size is zero
                ctypes.byref(buffer_size) # ReturnLength parameter
            )

            error_code = ctypes.get_last_error()
            ctypes.set_last_error(0) # Clear the error after getting it

            # --- Interpret the result of the size query call ---
            # The call should return False and set GetLastError to 122 (ERROR_INSUFFICIENT_BUFFER).
            # However, some environments might behave differently.
            # The most reliable indicator of success in getting the size is buffer_size.value > 0.
            if success:
                 # Unexpected success on the size query call. This shouldn't happen.
                 # Treat this as an error.
                 # Include the error_code we just retrieved, even if it's 0.
                 logger.error(f"GetTokenInformation succeeded unexpectedly on size query (error code {error_code}). Expected failure with ERROR_INSUFFICIENT_BUFFER (122).")
                 raise OSError(f"GetTokenInformation succeeded unexpectedly (error code {error_code}). Expected failure with ERROR_INSUFFICIENT_BUFFER (122).")

            # If we are here, success is False.
            # Now check if we got a buffer size.
            if buffer_size.value == 0:
                # It failed, and didn't return the required size. This is a real error.
                # Use the error_code we retrieved.
                # If error_code is 0 here, it's still weird, but we report the failure.
                logger.error(f"GetTokenInformation failed to get buffer size. Error code: {error_code}")
                raise ctypes.WinError(error_code, "Failed to get token information buffer size")

            # If we reached here, buffer_size.value is the required size (and > 0)

            # --- Allocate the buffer ---
            # Use create_string_buffer for raw byte buffer managed by ctypes.
            buffer = ctypes.create_string_buffer(buffer_size.value)

            # --- Get the token integrity level information into the buffer ---
            # Call GetTokenInformation again, this time with the allocated buffer.
            if not advapi32.GetTokenInformation(
                token,
                TokenIntegrityLevel,
                buffer,
                buffer_size.value,
                ctypes.byref(buffer_size) # ReturnLength parameter
            ):
                error_code = ctypes.get_last_error()
                ctypes.set_last_error(0)
                logger.error(f"Failed to get token information into buffer. Error code: {error_code}")
                raise ctypes.WinError(error_code, "Failed to get token information")

            # --- Interpret the buffer as the structure and extract the SID ---
            # Cast the raw buffer bytes to a pointer to our structure type.
            # .contents dereferences the pointer to get the actual structure.
            # The SID pointer (pSid) within the structure points into `buffer`.
            token_label = ctypes.cast(buffer, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
            sid = token_label.Label.Sid

            # --- Validate the SID pointer ---
            if not sid:
                 # This indicates the TOKEN_MANDATORY_LABEL structure didn't contain a valid SID pointer
                 # This is highly unexpected for TokenIntegrityLevel
                 logger.error("Integrity SID pointer obtained from GetTokenInformation is NULL.")
                 raise ValueError("Integrity SID pointer obtained from GetTokenInformation is NULL.")

            # --- Get the number of sub-authorities in the SID ---
            # The integrity level RID is the last sub-authority.
            # GetSidSubAuthorityCount returns a pointer to the UCHAR count field within the SID.
            # Clear last error before the call
            ctypes.set_last_error(0)
            sub_authority_count_ptr = advapi32.GetSidSubAuthorityCount(sid)
            error_code_after_count = ctypes.get_last_error()
            # No need to clear error_code_after_count, we just read it.

            if not sub_authority_count_ptr:
                 # This typically fails if 'sid' is not a valid SID pointer
                 # Use the error code captured *after* the call
                 # Raise ctypes.WinError for API call failures
                 logger.error(f"GetSidSubAuthorityCount failed (returned NULL pointer). LastError: {error_code_after_count}")
                 raise ctypes.WinError(error_code_after_count, "GetSidSubAuthorityCount failed (returned NULL pointer)")

            # If we are here, sub_authority_count_ptr is non-NULL.
            # Check if GetLastError was set, even if the pointer is non-NULL.
            # This is less common for pointer-returning functions but worth checking.
            if error_code_after_count != 0:
                 # This is an unusual state: non-NULL pointer but error code set.
                 # Treat as a failure.
                 logger.error(f"GetSidSubAuthorityCount returned non-NULL pointer but set last error: {error_code_after_count}")
                 raise ctypes.WinError(error_code_after_count, "GetSidSubAuthorityCount returned non-NULL pointer but set last error")


            # Dereference the pointer and get the value (which is the count).
            sub_authority_count = sub_authority_count_ptr.contents.value

            if sub_authority_count == 0:
                # An integrity SID should always have at least one sub-authority (the RID)
                # If we reached here, sid was non-NULL, sub_authority_count_ptr was non-NULL,
                # GetLastError was 0 after the call, but the count byte at that location is 0.
                # This is still highly unexpected and indicates a problem with the SID data itself.
                logger.error("Integrity SID reported zero sub-authorities.")
                raise ValueError("Integrity SID reported zero sub-authorities.")


            # --- Get the last sub-authority (the integrity level RID) ---
            # GetSidSubAuthority returns a pointer to the DWORD value of the sub-authority.
            # The index is 0-based, so the last one is at index (count - 1).
            integrity_level_ptr = advapi32.GetSidSubAuthority(sid, sub_authority_count - 1)
            # Check GetLastError after this call too
            error_code_after_subauthority = ctypes.get_last_error()
            ctypes.set_last_error(0) # Clear after reading

            if not integrity_level_ptr:
                 # This can fail if the index is out of bounds or 'sid' is invalid.
                 logger.error(f"GetSidSubAuthority failed (returned NULL pointer). LastError: {error_code_after_subauthority}")
                 raise ctypes.WinError(error_code_after_subauthority, "GetSidSubAuthority failed (returned NULL pointer)")

            # Check GetLastError even if pointer is non-NULL
            if error_code_after_subauthority != 0:
                 logger.error(f"GetSidSubAuthority returned non-NULL pointer but set last error: {error_code_after_subauthority}")
                 raise ctypes.WinError(error_code_after_subauthority, "GetSidSubAuthority returned non-NULL pointer but set last error")


            # Dereference the pointer and get the DWORD value.
            # No need to keep the 'integrity_level_ptr' object itself around.
            integrity_level = integrity_level_ptr.contents.value

            # Return the numerical integrity level RID
            return integrity_level

    # Catch potential OSError from ProcessToken.__init__ or API calls within the 'with' block
    # ctypes.WinError is a subclass of OSError
    except OSError as e:
        # Re-raise the caught OSError to provide detailed error info to the caller
        # Logging already happens within the function for specific API errors
        raise e
    # Catch potential ValueError from sub-authority count check or NULL SID pointer check
    except ValueError as e:
        # Wrap it in an OSError for consistency, though it indicates data corruption/unexpected state
        # Logging already happens within the function for specific ValueErrors
        raise OSError(f"Integrity SID data appears invalid: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during processing
        logger.exception("An unexpected error occurred during integrity level retrieval.")
        # Wrap the unexpected exception in an OSError
        raise OSError(f"An unexpected error occurred during integrity level retrieval: {e}") from e


# --- Convenience Function to Check for Elevation ---

def is_elevated() -> bool:
    """
    Checks if the current process is running with elevated (administrator)
    privileges on Windows by comparing its integrity level to HIGH.

    Returns:
        True if the process integrity level is HIGH or greater, False otherwise.

    Raises:
        NotImplementedError: If run on a non-Windows operating system.
        OSError: If any underlying Windows API call fails (propagated from
                 get_integrity_level).
        ValueError: If the integrity SID structure is unexpected (propagated
                    from get_integrity_level).
    """
    # A process is considered elevated if its integrity level is HIGH or higher.
    # (e.g., HIGH, SYSTEM, Protected Process)
    return get_integrity_level() >= SECURITY_MANDATORY_HIGH_RID


# --- Example Usage ---
if __name__ == "__main__":
    # Configure basic logging for the example usage
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

    try:
        # Note: Running this script directly from a standard command prompt
        # will show "standard user permissions". To see "elevated", you must
        # run the command prompt itself "as administrator" and then run the script.

        # Get the numerical level
        level_rid = get_integrity_level()

        # Map the numerical level to a name
        level_name = INTEGRITY_LEVEL_NAMES.get(level_rid, f"Unknown ({level_rid})")

        print(f"The script is running with integrity level: {level_name}")

        # Use the convenience function
        if is_elevated():
            print("This level is considered elevated (>= High).")
        else:
            print("This level is considered standard user or lower (< High).")

    except NotImplementedError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) # Indicate failure
    except OSError as e:
        print(f"\nError checking elevation status:", file=sys.stderr)
        # ctypes.WinError objects have winerror and strerror attributes
        # Check if it's a WinError before accessing attributes
        if isinstance(e, ctypes.WinError):
            print(f"  Windows Error Code: {e.winerror}", file=sys.stderr)
            print(f"  Message: {e.strerror}", file=sys.stderr)
            # If the original message from our code is useful, print it too
            # Check if the OSError has more than 2 arguments (WinError adds winerror, strerror)
            # The custom message is the 3rd argument (index 2)
            if len(e.args) > 2 and isinstance(e.args[2], str):
                 print(f"  Context: {e.args[2]}", file=sys.stderr)
        else:
             # Handle generic OSErrors (like the ValueError wrapped in OSError)
             print(f"  Message: {e}", file=sys.stderr)
             if e.__cause__:
                 print(f"  Caused by: {e.__cause__}", file=sys.stderr)

        sys.exit(1) # Indicate failure
    except Exception as e:
        # Catch any other unexpected errors not already caught and wrapped
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
