import pytest
from unittest.mock import call
import winreg # Needed for WindowsError (though we'll mock OSError with winerror)
import os # Needed for os.path.join in tests
import re # Needed for re.escape in pytest.raises match

import winregenv.registry_errors
# Import the module containing the functions to test
from winregenv import registry_base

# The mock_winreg fixture is provided by conftest.py in the same directory

def test_ensure_registry_key_exists_creates(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\NewApp"
    key_path = r"Settings"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure CreateKeyEx to simulate success
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2

    registry_base.ensure_registry_key_exists(root, key_path, root_prefix=root_prefix)

    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)


def test_ensure_registry_key_exists_already_exists(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"ExistingApp"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure CreateKeyEx to simulate opening an existing key (doesn't raise error)
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2

    registry_base.ensure_registry_key_exists(root, key_path, root_prefix=root_prefix)

    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)


def test_ensure_registry_key_exists_root_prefix_only(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = "" # Refers to the root_prefix itself
    full_path = root_prefix # Should just be the prefix

    # Configure CreateKeyEx to simulate success
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2

    registry_base.ensure_registry_key_exists(root, key_path, root_prefix=root_prefix)

    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)


def test_ensure_registry_key_exists_root_key_only(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = ""
    key_path = "" # Refers to the root key itself

    registry_base.ensure_registry_key_exists(root, key_path, root_prefix=root_prefix)

    # No winreg calls should be made for the root key
    mock_winreg.CreateKeyEx.assert_not_called()
    mock_winreg.OpenKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()


def test_ensure_registry_key_exists_permission_denied(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"Restricted"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure CreateKeyEx to fail with ERROR_ACCESS_DENIED (5)
    error_code = 5
    error_message_str = "Access is denied."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.CreateKeyEx.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryPermissionError) as excinfo:
        registry_base.ensure_registry_key_exists(root, key_path, root_prefix=root_prefix)

    # Assert on the attributes of the caught exception, which are populated by _handle_winreg_error
    assert excinfo.value.winerror == error_code
    assert excinfo.value.strerror == error_message_str
    # The first argument to the exception constructor is the formatted message
    expected_message_arg = f"Registry operation failed on key '{full_path}' (WinError {error_code}: {error_message_str})"
    assert excinfo.value.args[0] == expected_message_arg

    # Verify CreateKeyEx was called and failed
    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    # CloseKey should not have been called as CreateKeyEx failed before returning a handle
    mock_winreg.CloseKey.assert_not_called()


def test_put_registry_value_creates_key_and_sets_value(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\NewApp"
    key_path = r"Settings"
    value_name = "MyValue"
    value_data = "Some Data"
    value_type = mock_winreg.REG_SZ
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock CreateKeyEx for ensure_registry_key_exists
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2
    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1

    registry_base.put_registry_value(root, key_path, value_name, value_data, value_type, root_prefix=root_prefix)

    # Verify ensure_registry_key_exists was called with the full path
    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    # Removed: mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    # Verify SetValueEx was called on the handle from the context manager
    mock_winreg.SetValueEx.assert_called_once_with(
        mock_winreg.mock_handle_1,
        value_name,
        0,
        value_type,
        value_data
    )
    # Verify the handle from OpenKey was closed by the context manager
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_2), # From ensure_registry_key_exists
        call(mock_winreg.mock_handle_1),     # From RegistryKey context manager
    ])
    assert mock_winreg.CloseKey.call_count == 2


def test_put_registry_value_sets_value_existing_key(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"ExistingApp"
    value_name = "MyValue"
    value_data = "Some Data"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock CreateKeyEx for ensure_registry_key_exists (simulates opening existing)
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2
    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1

    registry_base.put_registry_value(root, key_path, value_name, value_data, value_type=mock_winreg.REG_SZ, root_prefix=root_prefix) # Pass explicit type

    # Verify ensure_registry_key_exists was called
    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    # Removed: mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)

    # Verify RegistryKey context manager was used
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    # Verify SetValueEx was called with default type (REG_SZ for string)
    mock_winreg.SetValueEx.assert_called_once_with(
        mock_winreg.mock_handle_1,
        value_name,
        0,
        mock_winreg.REG_SZ,
        value_data
    )
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_2),
        call(mock_winreg.mock_handle_1),
    ])
    assert mock_winreg.CloseKey.call_count == 2


def test_put_registry_value_permission_denied_set_value(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"ExistingApp"
    value_name = "MyValue"
    value_data = "Some Data"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock CreateKeyEx for ensure_registry_key_exists (simulates opening existing)
    mock_winreg.CreateKeyEx.return_value = mock_winreg.mock_handle_2
    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure SetValueEx to fail with ERROR_ACCESS_DENIED (5)
    error_code = 5
    error_message_str = "Access is denied."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.SetValueEx.side_effect = mock_error

    # The expected message includes the WinError details added by _handle_winreg_error.
    # Use direct string comparison instead of regex match for clarity on failure.
    expected_full_message = f"Registry operation failed on key '{full_path}', value '{value_name}' (WinError {error_code}: {error_message_str})"
    with pytest.raises(winregenv.registry_errors.RegistryPermissionError) as excinfo: # Pass explicit type
        registry_base.put_registry_value(root, key_path, value_name, value_data, value_type=mock_winreg.REG_SZ, root_prefix=root_prefix)

    # Verify ensure_registry_key_exists was called and succeeded
    mock_winreg.CreateKeyEx.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_WRITE)
    # Removed: mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_2)

    # Verify RegistryKey context manager was used
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_SET_VALUE)
    # Verify SetValueEx was called and failed
    mock_winreg.SetValueEx.assert_called_once_with(
        mock_winreg.mock_handle_1,
        value_name,
        0,
        mock_winreg.REG_SZ,
        value_data
    )
    # Verify the handle from OpenKey was closed by the context manager despite the error
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_2),
        call(mock_winreg.mock_handle_1),
    ])
    assert mock_winreg.CloseKey.call_count == 2


def test_put_registry_subkey_creates_key(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp"
    subkey_name = "NewSubkey"
    full_parent_path = os.path.join(root_prefix, key_path).replace('/', '\\')
    full_subkey_path = os.path.join(full_parent_path, subkey_name).replace('/', '\\')

    # Mock CreateKeyEx for ensure_registry_key_exists (simulates opening parent)
    # Mock CreateKeyEx again for the actual subkey creation
    mock_winreg.CreateKeyEx.side_effect = [
        mock_winreg.mock_handle_2, # For ensure_registry_key_exists
        mock_winreg.mock_handle_1  # For the actual put_registry_subkey call
    ]

    registry_base.put_registry_subkey(root, key_path, subkey_name, root_prefix=root_prefix)

    # Verify ensure_registry_key_exists was called for the parent
    mock_winreg.CreateKeyEx.assert_has_calls([
        call(root, full_parent_path, 0, mock_winreg.KEY_WRITE),
    ])
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_2), # Close handle from ensure_registry_key_exists
    ])

    # Verify CreateKeyEx was called for the new subkey
    mock_winreg.CreateKeyEx.assert_has_calls([
        call(root, full_subkey_path, 0, mock_winreg.KEY_WRITE),
    ])
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_1), # Close handle from put_registry_subkey
    ])
    assert mock_winreg.CreateKeyEx.call_count == 2
    assert mock_winreg.CloseKey.call_count == 2


def test_put_registry_subkey_permission_denied_create(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp"
    subkey_name = "NewSubkey"
    full_parent_path = os.path.join(root_prefix, key_path).replace('/', '\\')
    full_subkey_path = os.path.join(full_parent_path, subkey_name).replace('/', '\\')

    # Configure the second CreateKeyEx call (for the subkey) to fail
    error_code = 5
    error_message_str = "Access is denied."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code

    # Mock CreateKeyEx side_effect list
    mock_winreg.CreateKeyEx.side_effect = [
        mock_winreg.mock_handle_2, # For ensure_registry_key_exists (success)
        mock_error # For the actual put_registry_subkey call (fail)
    ]

    # The expected message includes the WinError details added by _handle_winreg_error.
    # Use direct string comparison instead of regex match for clarity on failure.
    expected_full_message = f"Registry operation failed on key '{full_subkey_path}' (WinError {error_code}: {error_message_str})"
    with pytest.raises(winregenv.registry_errors.RegistryPermissionError) as excinfo:
        registry_base.put_registry_subkey(root, key_path, subkey_name, root_prefix=root_prefix)

    # Verify ensure_registry_key_exists was called and succeeded
    mock_winreg.CreateKeyEx.assert_has_calls([
        call(root, full_parent_path, 0, mock_winreg.KEY_WRITE),
    ])
    mock_winreg.CloseKey.assert_has_calls([
        call(mock_winreg.mock_handle_2),
    ])

    # Verify CreateKeyEx was called for the new subkey and failed
    mock_winreg.CreateKeyEx.assert_has_calls([
        call(root, full_subkey_path, 0, mock_winreg.KEY_WRITE),
    ])
    assert mock_winreg.CreateKeyEx.call_count == 2
    # Only the first handle should have been closed
    assert mock_winreg.CloseKey.call_count == 1
