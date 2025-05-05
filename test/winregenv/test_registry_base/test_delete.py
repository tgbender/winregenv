import pytest
from unittest.mock import call
import winreg # Needed for WindowsError/OSError constants if used directly
import os # Needed for os.path.join in tests
import re # Needed for re.escape in pytest.raises match

import winregenv.registry_errors
# Import the module containing the functions to test
from winregenv import registry_base

# The mock_winreg fixture is provided by conftest.py in the same directory

# Helper function to create and raise an OSError with winerror attribute
def _raise_os_error(error_code, error_message_str):
    mock_error = OSError(error_code, error_message_str)
    # Ensure winerror is set, as winreg functions typically raise
    # WindowsError (an alias for OSError on modern Python) with this attribute.
    mock_error.winerror = error_code
    raise mock_error

# NOTE: Removed _raise_windows_error helper as _raise_os_error is sufficient
# and more consistent with modern Python exception handling.


def test_delete_registry_value_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp\Settings"
    value_name = "ValueToDelete"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure DeleteValue to succeed (default mock behavior is to raise ERROR_FILE_NOT_FOUND,
    # but the function handles that silently. We need to ensure it *doesn't* raise other errors).
    # Let's explicitly set side_effect to None to simulate successful deletion.
    mock_winreg.DeleteValue.side_effect = None

    registry_base.delete_registry_value(root, key_path, value_name, root_prefix=root_prefix)

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    # Verify DeleteValue was called on the handle
    mock_winreg.DeleteValue.assert_called_once_with(mock_winreg.mock_handle_1, value_name)
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_delete_registry_value_value_not_found_idempotent(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp\Settings"
    value_name = "NonExistentValue"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure DeleteValue to fail with ERROR_FILE_NOT_FOUND (2) - this should be caught and ignored
    # Use the _raise_os_error helper to raise OSError with winerror=2
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_winreg.DeleteValue.side_effect = lambda *args, **kwargs: _raise_os_error(error_code, error_message_str)

    # This call should now succeed without raising an exception
    registry_base.delete_registry_value(root, key_path, value_name, root_prefix=root_prefix) # Should not raise

    # Verify OpenKey was called
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    # Verify DeleteValue was called and raised the expected error (which was handled)
    mock_winreg.DeleteValue.assert_called_once_with(mock_winreg.mock_handle_1, value_name)
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_delete_registry_value_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    value_name = "AnyValue"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to fail with ERROR_FILE_NOT_FOUND (2)
    # Use the helper to raise OSError with winerror=2
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_winreg.OpenKey.side_effect = lambda *args, **kwargs: _raise_os_error(error_code, error_message_str)

    # The expected message includes the WinError details added by _handle_winreg_error
    # The expected message includes the WinError details added by _handle_winreg_error
    expected_full_message = f"Registry operation failed on key '{full_path}' (WinError {error_code}: {error_message_str})"

    # This should now raise the correct specific exception
    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(expected_full_message)):
        registry_base.delete_registry_value(root, key_path, value_name, root_prefix=root_prefix)

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    mock_winreg.DeleteValue.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()


def test_delete_registry_key_success_empty(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"EmptyKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')
    parent_full_path = root_prefix
    subkey_name = key_path

    # Configure OpenKey side_effect for the two OpenKey calls:
    # 1. Open the key to be deleted (for QueryInfoKey check) -> returns mock_handle_3
    # 2. Open the parent key (for DeleteKey) -> returns mock_handle_1
    mock_winreg.OpenKey.side_effect = [
        mock_winreg.mock_handle_3, # For the key being deleted (check)
        mock_winreg.mock_handle_1  # For the parent key (delete)
    ]

    # Configure QueryInfoKey to report 0 subkeys and 0 values (empty)
    # Corrected mock return value to 3 elements
    mock_winreg.QueryInfoKey.return_value = (0, 0, 12345678901234567) # num_subkeys, num_values, last_write_time_ft

    # Configure DeleteKey to succeed
    mock_winreg.DeleteKey.return_value = None

    registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check)
    mock_winreg.OpenKey.assert_has_calls([
        call(root, full_path, 0, mock_winreg.KEY_READ),
    ])
    # Verify QueryInfoKey was called on the handle from the first OpenKey
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_3)
    # Verify the handle from the first OpenKey was closed
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_3),
    ])

    # Verify the second OpenKey call (for the parent key deletion)
    mock_winreg.OpenKey.assert_has_calls([
        call(root, parent_full_path, 0, mock_winreg.KEY_CREATE_SUB_KEY),
    ])
    # Verify DeleteKey was called on the handle from the second OpenKey with the subkey name
    mock_winreg.DeleteKey.assert_called_once_with(mock_winreg.mock_handle_1, subkey_name)
    # Verify the handle from the second OpenKey was closed
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_1),
    ])

    assert mock_winreg.OpenKey.call_count == 2
    assert mock_winreg.CloseKey.call_count == 2
    assert mock_winreg.DeleteKey.call_count == 1


def test_delete_registry_key_fails_if_has_subkeys(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"KeyWithSubkeys"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey for the initial check to succeed
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_3

    # Configure QueryInfoKey to report subkeys > 0
    # Corrected mock return value to 3 elements
    mock_winreg.QueryInfoKey.return_value = (1, 0, 12345678901234567) # num_subkeys, num_values, last_write_time_ft

    # The expected message includes the key path and details about why it's not empty
    expected_full_message = f"Registry key '{full_path}' is not empty (contains 1 subkeys and 0 values). Cannot delete non-empty keys."

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotEmptyError, match=re.escape(expected_full_message)):
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check)
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryInfoKey was called
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_3)
    # Verify the handle was closed by the context manager
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_3)

    # No second OpenKey or DeleteKey calls should be made
    assert mock_winreg.OpenKey.call_count == 1
    mock_winreg.DeleteKey.assert_not_called()


def test_delete_registry_key_fails_if_has_values(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"KeyWithValues"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey for the initial check to succeed
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_3

    # Configure QueryInfoKey to report values > 0
    # Corrected mock return value to 3 elements
    mock_winreg.QueryInfoKey.return_value = (0, 1, 12345678901234567) # num_subkeys, num_values, last_write_time_ft

    # The expected message includes the key path and details about why it's not empty
    expected_full_message = f"Registry key '{full_path}' is not empty (contains 0 subkeys and 1 values). Cannot delete non-empty keys."

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotEmptyError, match=re.escape(expected_full_message)):
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check)
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryInfoKey was called
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_3)
    # Verify the handle was closed by the context manager
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_3)

    # No second OpenKey or DeleteKey calls should be made
    assert mock_winreg.OpenKey.call_count == 1
    mock_winreg.DeleteKey.assert_not_called()


def test_delete_registry_key_fails_if_has_subkeys_and_values(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"KeyWithBoth"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey for the initial check to succeed
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_3

    # Configure QueryInfoKey to report subkeys > 0 and values > 0
    # Corrected mock return value to 3 elements
    mock_winreg.QueryInfoKey.return_value = (2, 3, 12345678901234567) # num_subkeys, num_values, last_write_time_ft

    # The expected message includes the key path and details about why it's not empty
    expected_full_message = f"Registry key '{full_path}' is not empty (contains 2 subkeys and 3 values). Cannot delete non-empty keys."

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotEmptyError, match=re.escape(expected_full_message)):
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check)
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryInfoKey was called
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_3)
    # Verify the handle was closed by the context manager
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_3)

    # No second OpenKey or DeleteKey calls should be made
    assert mock_winreg.OpenKey.call_count == 1
    mock_winreg.DeleteKey.assert_not_called()


def test_delete_registry_key_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey for the initial check to fail with ERROR_FILE_NOT_FOUND (2)
    # Use the helper to raise OSError with winerror=2
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_winreg.OpenKey.side_effect = lambda *args, **kwargs: _raise_os_error(error_code, error_message_str)

    # The expected message includes the WinError details added by _handle_winreg_error
    expected_full_message = f"Registry operation failed on key '{full_path}' (WinError {error_code}: {error_message_str})"

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(expected_full_message)):
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check) was made and failed
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    mock_winreg.QueryInfoKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()
    mock_winreg.DeleteKey.assert_not_called()


def test_delete_registry_key_permission_denied_check(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"RestrictedKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey for the initial check to fail with ERROR_ACCESS_DENIED (5)
    # Use the helper to raise OSError with winerror=5
    error_code = 5
    error_message_str = "Access is denied."
    mock_winreg.OpenKey.side_effect = lambda *args, **kwargs: _raise_os_error(error_code, error_message_str)

    # The expected message includes the WinError details added by _handle_winreg_error.
    # Use direct string comparison instead of regex match for clarity on failure.
    expected_full_message = f"Registry operation failed on key '{full_path}' (WinError {error_code}: {error_message_str})"

    with pytest.raises(winregenv.registry_errors.RegistryPermissionError) as excinfo:
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check) was made and failed
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    mock_winreg.QueryInfoKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()
    mock_winreg.DeleteKey.assert_not_called()


def test_delete_registry_key_permission_denied_delete(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"EmptyKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')
    parent_full_path = root_prefix
    subkey_name = key_path

    # Create the specific error instance to be raised by the second OpenKey call
    error_code = 5
    error_message_str = "Access is denied."
    mock_permission_error = OSError(error_code, error_message_str)
    mock_permission_error.winerror = error_code

    # Configure OpenKey side_effect for the two OpenKey calls:
    # 1. Open the key to be deleted (for QueryInfoKey check) -> returns mock_handle_3 (success)
    # 2. Open the parent key (for DeleteKey) -> raises the pre-defined OSError
    mock_winreg.OpenKey.side_effect = [
        mock_winreg.mock_handle_3, # For the key being deleted (check)
        mock_permission_error      # For the parent key (delete)
    ]

    # Configure QueryInfoKey to report 0 subkeys and 0 values (empty)
    # Corrected mock return value to 3 elements
    mock_winreg.QueryInfoKey.return_value = (0, 0, 12345678901234567) # num_subkeys, num_values, last_write_time_ft

    # The expected message includes the WinError details added by _handle_winreg_error.
    # Note: The error originates from opening the *parent* key
    # Use direct string comparison instead of regex match for clarity on failure.
    expected_full_message = f"Registry operation failed on key '{parent_full_path}' (WinError {error_code}: {error_message_str})"

    # This should now raise the correct specific exception and message
    with pytest.raises(winregenv.registry_errors.RegistryPermissionError) as excinfo:
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    # Verify the first OpenKey call (for the check)
    mock_winreg.OpenKey.assert_has_calls([
        call(root, full_path, 0, mock_winreg.KEY_READ),
    ])
    # Verify QueryInfoKey was called
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_3)
    # Verify the handle was closed
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_3),
    ])

    # Verify the second OpenKey call (for the parent key deletion) was made and failed
    mock_winreg.OpenKey.assert_has_calls([
        call(root, parent_full_path, 0, mock_winreg.KEY_CREATE_SUB_KEY),
    ])
    mock_winreg.DeleteKey.assert_not_called() # DeleteKey should not be reached

    assert mock_winreg.OpenKey.call_count == 2
    assert mock_winreg.CloseKey.call_count == 1 # Only the first handle was closed


def test_delete_registry_key_value_error_on_root(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = ""
    key_path = "" # Attempting to delete the root

    with pytest.raises(ValueError, match="Cannot delete the root registry key."):
        registry_base.delete_registry_key(root, key_path, root_prefix=root_prefix)

    mock_winreg.OpenKey.assert_not_called()
    mock_winreg.QueryInfoKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()
    mock_winreg.DeleteKey.assert_not_called()
