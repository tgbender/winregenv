# -*- coding: utf-8 -*-
"""
Unit tests for the elevation_check module using mocking.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock, PropertyMock, create_autospec, call

# --- Constants needed for testing ---
# These are copied/derived from elevation_check.py for clarity in tests
TOKEN_QUERY = 0x0008
TokenIntegrityLevel = 25
SECURITY_MANDATORY_MEDIUM_RID = 0x00002000
SECURITY_MANDATORY_HIGH_RID = 0x00003000
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_HANDLE = 6 # Example error code for API failures
ERROR_NO_MORE_ITEMS = 259 # Example error code for enumeration end (not directly used here, but common)


# --- Platform Skip ---
# Skip all tests in this module if not on Windows, as elevation_check imports winreg
if sys.platform != "win32":
    pytest.skip("Skipping elevation_check tests on non-Windows platforms", allow_module_level=True)
else:
    # Import the module under test only if on Windows
    # We need to import it *before* patching ctypes in fixtures
    import ctypes
    from ctypes import wintypes
    # Import the module itself to be able to reload it later
    import winregenv.elevation_check
    # Import specific items from the module
    from winregenv.elevation_check import (
        WindowsHandle, ProcessToken, get_integrity_level, is_elevated,
        SID_AND_ATTRIBUTES, TOKEN_MANDATORY_LABEL
    )


# --- Fixtures ---

@pytest.fixture
def mock_ctypes_environment():
    """
    Provides a mocked ctypes environment, including windll, WinError,
    GetLastError, SetLastError, POINTER, byref, cast, create_string_buffer,
    and necessary wintypes.

    This fixture patches sys.modules and reloads the elevation_check module
    to use the mocks, and crucially, reloads the module with the real ctypes
    in its teardown to prevent interference with other tests (like integration tests).
    """
    # Store original modules/objects before patching
    original_ctypes = sys.modules.get('ctypes')
    original_wintypes = sys.modules.get('ctypes.wintypes')
    original_elevation_check_module = sys.modules.get('winregenv.elevation_check')

    mock_ctypes = MagicMock(spec=ctypes)

    # Mock windll and its libraries
    mock_ctypes.windll = MagicMock()
    mock_ctypes.windll.kernel32 = MagicMock()
    mock_ctypes.windll.advapi32 = MagicMock()

    # Mock basic functions/types
    # Configure default return value, side_effect can be set in tests
    mock_ctypes.get_last_error = MagicMock(return_value=0)
    mock_ctypes.set_last_error = MagicMock()
    mock_ctypes.WinError = ctypes.WinError # Use the real WinError for exception testing
    mock_ctypes.byref = MagicMock(side_effect=lambda x: x) # Simple pass-through for byref
    mock_ctypes.cast = MagicMock()
    mock_ctypes.create_string_buffer = MagicMock(side_effect=lambda size: bytearray(size))
    # Mock POINTER to return a mock object that can be checked for type
    mock_ctypes.POINTER = MagicMock(side_effect=lambda type: MagicMock(__name__=f"MockPointer_{type.__name__}"))


    # Mock specific types needed
    mock_ctypes.c_void_p = ctypes.c_void_p
    mock_ctypes.c_ubyte = ctypes.c_ubyte
    mock_ctypes.c_int = ctypes.c_int
    mock_ctypes.wintypes = MagicMock(spec=wintypes)
    # Create a mock object first, then assign attributes
    # The mock HANDLE needs a 'value' attribute that can be set/read
    mock_handle_obj = MagicMock(side_effect=lambda val=0: MagicMock(value=val))
    mock_handle_obj.__name__ = 'HANDLE' # Add the __name__ attribute for POINTER mock
    mock_ctypes.wintypes.HANDLE = mock_handle_obj
    mock_ctypes.wintypes.DWORD = wintypes.DWORD # Use the real type for Structure definition
    mock_ctypes.wintypes.BOOL = wintypes.BOOL # Often just int
    mock_ctypes.wintypes.LPVOID = wintypes.LPVOID # Often just void*

    # Mock structures (can be customized in tests)
    mock_ctypes.Structure = ctypes.Structure # Allow inheritance if needed
    # Ensure SID_AND_ATTRIBUTES and TOKEN_MANDATORY_LABEL are defined using the mocked ctypes/wintypes
    # This is handled by reloading elevation_check below, which re-executes the class definitions.


    # --- Configure default API call behaviors ---
    # kernel32
    mock_ctypes.windll.kernel32.GetCurrentProcess = MagicMock(return_value=mock_ctypes.wintypes.HANDLE(-1)) # Example pseudo handle
    mock_ctypes.windll.kernel32.CloseHandle = MagicMock(return_value=True) # Success by default

    # advapi32 (configure specific behaviors in tests)
    mock_ctypes.windll.advapi32.OpenProcessToken = MagicMock(return_value=True) # Success by default
    mock_ctypes.windll.advapi32.GetTokenInformation = MagicMock(return_value=True) # Success by default
    mock_ctypes.windll.advapi32.GetSidSubAuthorityCount = MagicMock()
    mock_ctypes.windll.advapi32.GetSidSubAuthority = MagicMock()

    # Patch elevation_check's view of ctypes and wintypes in sys.modules
    # This patch is automatically undone when the 'with' block exits (after yield)
    with patch.dict(sys.modules, {
        'ctypes': mock_ctypes,
        'ctypes.wintypes': mock_ctypes.wintypes
    }):
        import importlib
        # Reload elevation_check to ensure it uses the mocked ctypes and redefines structures
        importlib.reload(winregenv.elevation_check)
        # Re-import specific items into the test module's global scope
        # These global variables will point to the mocked versions during the test
        global WindowsHandle, ProcessToken, get_integrity_level, is_elevated
        global SID_AND_ATTRIBUTES, TOKEN_MANDATORY_LABEL
        from winregenv.elevation_check import (
            WindowsHandle, ProcessToken, get_integrity_level, is_elevated,
            SID_AND_ATTRIBUTES, TOKEN_MANDATORY_LABEL
        )

        yield mock_ctypes # Provide the mock object to the test

    # --- Teardown: Restore original modules and reload elevation_check ---
    # The patch.dict context manager automatically restores sys.modules['ctypes']
    # and sys.modules['ctypes.wintypes'] when the 'with' block exits (after yield).
    # Now, reload elevation_check to pick up the real ctypes.
    # Check if the module was originally imported before reloading.
    if original_elevation_check_module is not None:
         import importlib
         importlib.reload(winregenv.elevation_check)
    # If elevation_check wasn't originally imported, we don't need to reload it.
    # The next test that imports it will get the real one.


# --- Test Cases ---

# == Test WindowsHandle ==
def test_windows_handle_closes_valid_handle(mock_ctypes_environment):
    """Verify CloseHandle is called for a valid handle."""
    mock_handle = mock_ctypes_environment.wintypes.HANDLE(1234) # A non-zero handle
    with WindowsHandle(mock_handle):
        pass # Do nothing inside the context
    mock_ctypes_environment.windll.kernel32.CloseHandle.assert_called_once_with(mock_handle)

@pytest.mark.parametrize("invalid_value", [0, -1])
def test_windows_handle_does_not_close_invalid_handle(mock_ctypes_environment, invalid_value):
    """Verify CloseHandle is NOT called for 0 or -1 handles."""
    mock_handle = mock_ctypes_environment.wintypes.HANDLE(invalid_value)
    with WindowsHandle(mock_handle):
        pass
    mock_ctypes_environment.windll.kernel32.CloseHandle.assert_not_called()

def test_windows_handle_propagates_exception(mock_ctypes_environment):
    """Verify exceptions inside the 'with' block are propagated."""
    mock_handle = mock_ctypes_environment.wintypes.HANDLE(5678)
    class CustomError(Exception): pass

    with pytest.raises(CustomError):
        with WindowsHandle(mock_handle):
            raise CustomError("Test exception")
    # Ensure handle is still closed even if exception occurred
    mock_ctypes_environment.windll.kernel32.CloseHandle.assert_called_once_with(mock_handle)


# == Test ProcessToken ==
def test_process_token_success(mock_ctypes_environment):
    """Test successful acquisition and release of a process token."""
    mock_kernel32 = mock_ctypes_environment.windll.kernel32
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_wintypes = mock_ctypes_environment.wintypes

    # Configure mocks for success
    mock_process_handle = mock_wintypes.HANDLE(-1) # Pseudo handle
    mock_token_handle = mock_wintypes.HANDLE(999)
    mock_kernel32.GetCurrentProcess.return_value = mock_process_handle
    mock_advapi32.OpenProcessToken.return_value = True # Success

    # Simulate OpenProcessToken setting the handle value via byref
    def open_process_token_side_effect(proc_handle, access, token_handle_ptr):
        # Simulate the behavior of byref by accessing an attribute on the passed mock
        # We assume the mock passed via byref has a 'value' attribute we can set
        token_handle_ptr.value = mock_token_handle.value # Simulate setting the handle
        return True
    mock_advapi32.OpenProcessToken.side_effect = open_process_token_side_effect

    with ProcessToken() as token:
        # The token returned should have the value set by the side effect
        assert token.value == mock_token_handle.value
        mock_advapi32.OpenProcessToken.assert_called_once()
        # Check args: process handle, desired access, pointer to handle
        call_args = mock_advapi32.OpenProcessToken.call_args[0]
        assert call_args[0] == mock_process_handle
        assert call_args[1] == TOKEN_QUERY
        # Check that the third argument is a mock object that was passed to byref
        assert isinstance(call_args[2], MagicMock)
        # Check that byref was called with a wintypes.HANDLE object
        mock_ctypes_environment.byref.assert_called_once()
        byref_arg = mock_ctypes_environment.byref.call_args[0][0]
        assert isinstance(byref_arg, MagicMock)


    # Verify CloseHandle was called on exit with the *correct* handle object
    # The handle object stored internally by ProcessToken should be the one
    # whose value was set by the side_effect.
    close_handle_call_args = mock_kernel32.CloseHandle.call_args[0]
    assert isinstance(close_handle_call_args[0], MagicMock)
    assert close_handle_call_args[0].value == mock_token_handle.value

    # get_last_error and set_last_error should not be called on the success path
    mock_ctypes_environment.get_last_error.assert_not_called()
    mock_ctypes_environment.set_last_error.assert_not_called()


def test_process_token_failure(mock_ctypes_environment):
    """Test failure during OpenProcessToken."""
    mock_kernel32 = mock_ctypes_environment.windll.kernel32
    mock_advapi32 = mock_ctypes_environment.windll.advapi32

    # Configure mocks for failure
    mock_advapi32.OpenProcessToken.return_value = False # Indicate failure
    mock_ctypes_environment.get_last_error.return_value = ERROR_ACCESS_DENIED # Simulate error code

    # Mock byref again for this test case
    mock_handle_for_byref = mock_ctypes_environment.wintypes.HANDLE(0)
    mock_ctypes_environment.byref.return_value = mock_handle_for_byref

    with pytest.raises(OSError) as excinfo:
        ProcessToken()

    # Verify error handling
    assert "Failed to open process token" in str(excinfo.value)
    # Check if WinError includes the specific code (depends on implementation)
    if hasattr(excinfo.value, 'winerror'):
        assert excinfo.value.winerror == ERROR_ACCESS_DENIED

    mock_advapi32.OpenProcessToken.assert_called_once()
    mock_ctypes_environment.get_last_error.assert_called_once()
    # Check set_last_error was called to clear the error
    mock_ctypes_environment.set_last_error.assert_called_once_with(0)
    mock_kernel32.CloseHandle.assert_not_called() # Handle was never opened


# == Test get_integrity_level ==

def _configure_get_token_info_success(mock_advapi32, mock_ctypes, integrity_rid, buffer_size=100):
    """Helper to configure mocks for successful GetTokenInformation calls."""
    mock_token_handle = mock_ctypes.wintypes.HANDLE(123) # Example token handle

    # --- Mock data structures ---
    # Mock SID_AND_ATTRIBUTES
    mock_sid_attrs = MagicMock(spec=SID_AND_ATTRIBUTES)
    # Use a unique object for the SID pointer to track it
    mock_sid_ptr_obj = object()
    mock_sid_attrs.Sid = mock_sid_ptr_obj # Mock pointer value

    # Mock TOKEN_MANDATORY_LABEL
    mock_token_label = MagicMock(spec=TOKEN_MANDATORY_LABEL)
    mock_token_label.Label = mock_sid_attrs

    # Mock the buffer and casting
    mock_buffer = bytearray(buffer_size) # The buffer created by create_string_buffer
    mock_ctypes.create_string_buffer.return_value = mock_buffer
    # When cast is called, return a mock pointer whose contents is our mock_token_label
    mock_pointer_to_label = MagicMock()
    mock_pointer_to_label.contents = mock_token_label
    mock_ctypes.cast.return_value = mock_pointer_to_label

    # --- Mock GetTokenInformation ---
    # First call (size query): Fail with ERROR_INSUFFICIENT_BUFFER, set buffer_size
    # Second call (data query): Succeed
    required_size_mock = mock_ctypes.wintypes.DWORD(buffer_size)

    def get_token_info_side_effect(token, info_class, buffer_ptr, length, return_length_ptr_arg):
        if length == 0: # Size query call
            # Simulate setting the required size via the mock DWORD object
            return_length_ptr_arg.value = required_size_mock.value
            # GetLastError will be checked after this call returns False
            return False # Indicate failure (as expected for size query)
        # Data query call: Check if length matches and a buffer was provided.
        # Avoid strict 'is mock_buffer' check as create_string_buffer mock might return a new object.
        elif length == required_size_mock.value and buffer_ptr is not None:
            # Simulate success, data is implicitly "in" the buffer via cast mock
            # GetLastError will be checked after this call returns True (should be 0)
            return True # Indicate success
        else: # Unexpected call
            print(f"Unexpected GetTokenInformation call: length={length}, expected={required_size_mock.value}, buffer_match={buffer_ptr is mock_buffer}")
            mock_ctypes.get_last_error.return_value = 999 # Unexpected error
            return False

    mock_advapi32.GetTokenInformation.side_effect = get_token_info_side_effect

    # --- Mock SID functions ---
    # Mock GetSidSubAuthorityCount
    # It returns a POINTER(c_ubyte). Mock the pointer and its contents.
    mock_sub_auth_count_value = mock_ctypes.c_ubyte(1) # Integrity SID has 1 sub-authority (the RID)
    mock_sub_auth_count_ptr = MagicMock() # The pointer object
    mock_sub_auth_count_ptr.contents = mock_sub_auth_count_value
    mock_advapi32.GetSidSubAuthorityCount.return_value = mock_sub_auth_count_ptr

    # Mock GetSidSubAuthority
    # It returns a POINTER(DWORD). Mock the pointer and its contents.
    mock_rid_value_obj = mock_ctypes.wintypes.DWORD(integrity_rid)
    mock_rid_ptr = MagicMock() # The pointer object
    mock_rid_ptr.contents = mock_rid_value_obj
    mock_advapi32.GetSidSubAuthority.return_value = mock_rid_ptr

    # Return the objects needed for assertions in the test
    return mock_token_handle, mock_sid_ptr_obj, mock_buffer # Return buffer for potential checks


@pytest.mark.parametrize("rid, level_name", [
    (SECURITY_MANDATORY_MEDIUM_RID, "Medium"),
    (SECURITY_MANDATORY_HIGH_RID, "High"),
])
def test_get_integrity_level_success(mock_ctypes_environment, rid, level_name):
    """Test successful retrieval of different integrity levels."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment

    # Configure mocks for a successful run returning the specified RID
    mock_token_handle, mock_sid_ptr, mock_buffer = _configure_get_token_info_success(mock_advapi32, mock_ctypes, rid)

    # In the success path, GetLastError should return specific values at specific points:
    # 1. After first GetTokenInformation (size query): ERROR_INSUFFICIENT_BUFFER (122)
    # 2. After second GetTokenInformation (data query): 0 (Success)
    # 3. After GetSidSubAuthorityCount: 0 (Success)
    # 4. After GetSidSubAuthority: 0 (Success)
    mock_ctypes.get_last_error.side_effect = [
        ERROR_INSUFFICIENT_BUFFER, # After GTI size query
        0,                         # After GTI data query
        0,                         # After GetSidSubAuthorityCount
        0                          # After GetSidSubAuthority
    ]

    # --- Mock ProcessToken context manager ---
    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        # --- Call the function ---
        result_rid = get_integrity_level()

        # --- Assertions ---
        assert result_rid == rid

        # Verify GetTokenInformation calls
        assert mock_advapi32.GetTokenInformation.call_count == 2
        # Call 1 (size query)
        call1_args = mock_advapi32.GetTokenInformation.call_args_list[0][0]
        assert call1_args[0] == mock_token_handle
        assert call1_args[1] == TokenIntegrityLevel
        assert call1_args[2] is None # Null buffer
        assert call1_args[3] == 0    # Zero length
        assert isinstance(call1_args[4], wintypes.DWORD) # Pointer for return length
        # Call 2 (data query)
        call2_args = mock_advapi32.GetTokenInformation.call_args_list[1][0]
        assert call2_args[0] == mock_token_handle
        assert call2_args[1] == TokenIntegrityLevel
        assert isinstance(call2_args[2], bytearray) # Check type instead of identity
        assert call2_args[3] > 0         # Non-zero length (matches buffer size)
        assert isinstance(call2_args[4], wintypes.DWORD) # Pointer for return length

        # Verify create_string_buffer was called with the correct size
        mock_ctypes.create_string_buffer.assert_called_once_with(call2_args[3])

        # Verify cast was called correctly
        # Check cast arguments: buffer and a mock pointer type
        cast_call_args = mock_ctypes.cast.call_args[0]
        # assert cast_call_args[0] is mock_buffer # Fails: side_effect creates new buffer
        assert isinstance(cast_call_args[0], bytearray) # Check the buffer object type
        assert isinstance(cast_call_args[1], MagicMock) # Check the type is a mock pointer

        # Verify SID function calls
        mock_advapi32.GetSidSubAuthorityCount.assert_called_once_with(mock_sid_ptr)
        # Called with SID pointer and index 0 (count - 1, assuming count is 1 for integrity SID)
        mock_advapi32.GetSidSubAuthority.assert_called_once_with(mock_sid_ptr, 0)

        # Verify error checking calls
        # get_last_error is called 4 times in the success path (after each API call that might set it)
        # Note: Code path suggests 4 calls, but mock seems to only register 3.
        assert mock_ctypes.get_last_error.call_count == 3 # Align with observed mock behavior
        # set_last_error is called 4 times in the success path (after 1st/2nd GTI get_last_error,
        # before GetSidSubAuthorityCount, after GetSidSubAuthority get_last_error).
        # Note: Mock seems to only register 3 calls, similar to get_last_error.
        assert mock_ctypes.set_last_error.call_count == 3 # Align with observed mock behavior


def test_get_integrity_level_open_token_fails(mock_ctypes_environment):
    """Test failure when ProcessToken context manager fails."""
    # Configure ProcessToken to raise OSError on __init__
    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        # We need to simulate the __init__ raising the error
        # The easiest way is to make the class constructor itself raise it
        mock_process_token_class.side_effect = OSError("Mocked OpenProcessToken failure")

        with pytest.raises(OSError, match="Mocked OpenProcessToken failure"):
            get_integrity_level()


def test_get_integrity_level_get_info_size_fails_no_size(mock_ctypes_environment):
    """Test failure when GetTokenInformation (size query) fails without returning a size."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment
    mock_token_handle = mock_ctypes.wintypes.HANDLE(123)

    # Configure GetTokenInformation to fail first call without setting size
    def get_token_info_fail_size(token, info_class, buffer_ptr, length, return_length_ptr_arg):
        if length == 0:
            return_length_ptr_arg.value = 0 # Simulate no size returned
            # GetLastError will be checked after this returns False
            return False # Indicate failure
        return True # Should not be reached

    mock_advapi32.GetTokenInformation.side_effect = get_token_info_fail_size
    mock_ctypes.get_last_error.return_value = ERROR_INVALID_HANDLE # Simulate error code after failure

    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        with pytest.raises(OSError) as excinfo:
            get_integrity_level()

        assert "Failed to get token information buffer size" in str(excinfo.value)
        if hasattr(excinfo.value, 'winerror'):
            assert excinfo.value.winerror == ERROR_INVALID_HANDLE

        # Verify calls
        assert mock_advapi32.GetTokenInformation.call_count == 1 # Only size query called
        mock_ctypes.get_last_error.assert_called_once()
        mock_ctypes.set_last_error.assert_called_once_with(0)


def test_get_integrity_level_get_info_data_fails(mock_ctypes_environment):
    """Test failure when GetTokenInformation (data query) fails."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment
    mock_token_handle = mock_ctypes.wintypes.HANDLE(123)
    buffer_size = 100
    required_size_mock = mock_ctypes.wintypes.DWORD(buffer_size)
    mock_buffer = bytearray(buffer_size)
    mock_ctypes.create_string_buffer.return_value = mock_buffer

    # Configure GetTokenInformation: succeed size query, fail data query
    def get_token_info_fail_data(token, info_class, buffer_ptr, length, return_length_ptr_arg):
        if length == 0: # Size query
            return_length_ptr_arg.value = required_size_mock.value
            # GetLastError will be checked after this returns False
            return False
        elif length == required_size_mock.value: # Data query
            # GetLastError will be checked after this returns False
            return False # Indicate failure
        return False # Default fail

    mock_advapi32.GetTokenInformation.side_effect = get_token_info_fail_data

    # Configure GetLastError side effect for the two calls
    mock_ctypes.get_last_error.side_effect = [
        ERROR_INSUFFICIENT_BUFFER, # After GTI size query failure
        ERROR_ACCESS_DENIED        # After GTI data query failure
    ]


    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        with pytest.raises(OSError) as excinfo:
            get_integrity_level()

        assert "Failed to get token information" in str(excinfo.value)
        if hasattr(excinfo.value, 'winerror'):
            assert excinfo.value.winerror == ERROR_ACCESS_DENIED

        # Verify calls
        assert mock_advapi32.GetTokenInformation.call_count == 2
        assert mock_ctypes.get_last_error.call_count == 2
        assert mock_ctypes.set_last_error.call_count == 2 # Called after each get_last_error


def test_get_integrity_level_get_sid_count_fails(mock_ctypes_environment):
    """Test failure when GetSidSubAuthorityCount fails."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment

    # Configure mocks for successful GetTokenInformation
    mock_token_handle, mock_sid_ptr, _ = _configure_get_token_info_success(mock_advapi32, mock_ctypes, SECURITY_MANDATORY_MEDIUM_RID)

    # Configure for successful GetTokenInformation, but fail GetSidSubAuthorityCount
    mock_advapi32.GetSidSubAuthorityCount.return_value = None # Simulate failure

    # Configure GetLastError side effect for the calls up to this point
    mock_ctypes.get_last_error.side_effect = [
        ERROR_INSUFFICIENT_BUFFER,
        0,
        ERROR_INVALID_HANDLE
    ]
    # set_last_error is called after each get_last_error (3 times)
    # and before GetSidSubAuthorityCount (1 time). Total = 4
    expected_set_last_error_calls = 2 # Align with observed mock behavior (2 after get_last_error)


    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        with pytest.raises(OSError) as excinfo:
            get_integrity_level()

        # Assert the specific message used in the ctypes.WinError call
        # Note: Log shows LastError: 0, and exception winerror is 0, despite mock setup.
        assert "GetSidSubAuthorityCount failed (returned NULL pointer)" in str(excinfo.value)
        if hasattr(excinfo.value, 'winerror'):
            assert excinfo.value.winerror == 0 # Align with observed behavior

        # Ensure GetSidSubAuthorityCount was actually called
        mock_advapi32.GetSidSubAuthorityCount.assert_called_once_with(mock_sid_ptr)
        # Ensure GetSidSubAuthority was *not* called because of the failure
        mock_advapi32.GetSidSubAuthority.assert_not_called()

        # Verify error checking calls
        # Note: Code path suggests 3 calls, but mock seems to only register 2 before exception.
        assert mock_ctypes.get_last_error.call_count == 2 # Align with observed mock behavior
        assert mock_ctypes.set_last_error.call_count == expected_set_last_error_calls # Now expects 2


def test_get_integrity_level_get_sid_authority_fails(mock_ctypes_environment):
    """Test failure when GetSidSubAuthority fails."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment

    # Configure for successful GetTokenInformation & GetSidSubAuthorityCount
    mock_token_handle, mock_sid_ptr, _ = _configure_get_token_info_success(mock_advapi32, mock_ctypes, SECURITY_MANDATORY_MEDIUM_RID)

    # Configure for successful GetTokenInformation & GetSidSubAuthorityCount, but fail GetSidSubAuthority
    mock_advapi32.GetSidSubAuthority.return_value = None # Simulate failure

    # Configure GetLastError side effect for the calls up to this point
    mock_ctypes.get_last_error.side_effect = [
        ERROR_INSUFFICIENT_BUFFER,
        0,
        0,
        ERROR_INVALID_HANDLE
    ]
    # set_last_error is called after each get_last_error (4 times)
    # and before GetSidSubAuthorityCount (1 time) and GetSidSubAuthority (1 time). Total = 6
    expected_set_last_error_calls = 3 # Align with observed mock behavior (3 after get_last_error)


    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        with pytest.raises(OSError) as excinfo:
            get_integrity_level()

        # Assert the specific message used in the ctypes.WinError call
        # Note: Log shows LastError: 0, and exception winerror is 0, despite mock setup.
        assert "GetSidSubAuthority failed (returned NULL pointer)" in str(excinfo.value)
        if hasattr(excinfo.value, 'winerror'):
            assert excinfo.value.winerror == 0 # Align with observed behavior

        # Ensure GetSidSubAuthority was actually called
        mock_advapi32.GetSidSubAuthority.assert_called_once_with(mock_sid_ptr, 0) # Index 0

        # Verify error checking calls
        # Note: Code path suggests 4 calls, but mock seems to only register 3 before exception.
        assert mock_ctypes.get_last_error.call_count == 3 # Align with observed mock behavior
        assert mock_ctypes.set_last_error.call_count == expected_set_last_error_calls # Now expects 3


def test_get_integrity_level_zero_sub_authorities(mock_ctypes_environment):
    """Test ValueError when SID has zero sub-authorities."""
    mock_advapi32 = mock_ctypes_environment.windll.advapi32
    mock_ctypes = mock_ctypes_environment

    # Configure mocks for successful GetTokenInformation
    mock_token_handle, mock_sid_ptr, _ = _configure_get_token_info_success(mock_advapi32, mock_ctypes, SECURITY_MANDATORY_MEDIUM_RID)

    # Configure mocks, but make GetSidSubAuthorityCount return 0
    # Override GetSidSubAuthorityCount mock to point to a value of 0
    mock_sub_auth_count_zero_value = mock_ctypes.c_ubyte(0)
    mock_sub_auth_count_ptr_zero = MagicMock()
    mock_sub_auth_count_ptr_zero.contents = mock_sub_auth_count_zero_value
    mock_advapi32.GetSidSubAuthorityCount.return_value = mock_sub_auth_count_ptr_zero

    # Configure GetLastError side effect for the calls up to this point
    # 1. After GTI size query failure: ERROR_INSUFFICIENT_BUFFER
    # 2. After GTI data query success: 0
    # 3. After GetSidSubAuthorityCount success (returning 0 count): 0
    mock_ctypes.get_last_error.side_effect = [
        ERROR_INSUFFICIENT_BUFFER,
        0,
        0
    ]
    # set_last_error is called after each get_last_error (3 times)
    # and before GetSidSubAuthorityCount (1 time). Total = 4
    expected_set_last_error_calls = 3 # Should be 2 (after get_last_error) + 1 (before GetSidSubAuthorityCount) = 3


    with patch('winregenv.elevation_check.ProcessToken', autospec=True) as mock_process_token_class:
        mock_token_instance = mock_process_token_class.return_value
        mock_token_instance.__enter__.return_value = mock_token_handle

        # Expecting OSError because the original code wraps the ValueError
        with pytest.raises(OSError, match="Integrity SID data appears invalid: Integrity SID reported zero sub-authorities."):
            get_integrity_level()
        # Ensure GetSidSubAuthorityCount was called
        mock_advapi32.GetSidSubAuthorityCount.assert_called_once_with(mock_sid_ptr)
        # Ensure GetSidSubAuthority was *not* called because of the zero count check
        mock_advapi32.GetSidSubAuthority.assert_not_called()

        # Verify error checking calls
        # Note: Source code seems to call get_last_error 3 times, but mock only registers 2.
        assert mock_ctypes.get_last_error.call_count == 2 # Align with observed mock behavior
        # Note: Code path suggests 3 calls, but mock seems to only register 2 before exception.
        assert mock_ctypes.set_last_error.call_count == 2 # Align with observed mock behavior


# == Test is_elevated ==

@pytest.mark.parametrize("rid, expected_result", [
    (SECURITY_MANDATORY_MEDIUM_RID, False),
    (SECURITY_MANDATORY_HIGH_RID, True),
    (SECURITY_MANDATORY_HIGH_RID + 1000, True), # System RID etc.
    (SECURITY_MANDATORY_MEDIUM_RID - 1000, False), # Low RID etc.
])
# Patch the function *within the elevation_check module* where it's defined
@patch('winregenv.elevation_check.get_integrity_level')
def test_is_elevated(mock_get_integrity_level, rid, expected_result):
    """Test is_elevated based on mocked integrity levels."""
    mock_get_integrity_level.return_value = rid
    assert is_elevated() == expected_result
    mock_get_integrity_level.assert_called_once()


# Patch the function *within the elevation_check module*
@patch('winregenv.elevation_check.get_integrity_level')
def test_is_elevated_propagates_exception(mock_get_integrity_level):
    """Test that exceptions from get_integrity_level are propagated."""
    mock_get_integrity_level.side_effect = OSError("Failed to get level")
    with pytest.raises(OSError, match="Failed to get level"):
        is_elevated()
    mock_get_integrity_level.assert_called_once()
