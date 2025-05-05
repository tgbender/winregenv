import pytest
from unittest.mock import call
import winreg # Needed for WindowsError (though we'll mock OSError with winerror)
import os # Needed for os.path.join in tests
import re # Needed for re.escape in pytest.raises match
from datetime import datetime, timezone # Needed for head_registry_key timestamp conversion and UTC

import winregenv.registry_errors
# Import the module containing the functions to test
from winregenv import registry_base

# The mock_winreg fixture is provided by conftest.py in the same directory

def test_get_registry_value_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software\MyApp"
    key_path = r"Settings"
    value_name = "MyValue"
    expected_data = "Some Data"
    expected_type = mock_winreg.REG_SZ
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure QueryValueEx to return the desired value
    mock_winreg.QueryValueEx.return_value = (expected_data, expected_type)

    value_obj = registry_base.get_registry_value(root, key_path, value_name, root_prefix=root_prefix)

    assert value_obj.data == expected_data
    assert value_obj.type == expected_type

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryValueEx was called on the handle
    mock_winreg.QueryValueEx.assert_called_once_with(mock_winreg.mock_handle_1, value_name)
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_get_registry_value_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    value_name = "MyValue"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to fail with ERROR_FILE_NOT_FOUND (2)
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.OpenKey.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(f"Registry operation failed on key '{full_path}'")):
        registry_base.get_registry_value(root, key_path, value_name, root_prefix=root_prefix)

    # Verify OpenKey was called and failed
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    mock_winreg.QueryValueEx.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()


def test_get_registry_value_value_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"ExistingKey"
    value_name = "NonExistentValue"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to succeed
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure QueryValueEx to fail with ERROR_FILE_NOT_FOUND (2)
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.QueryValueEx.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryValueNotFoundError, match=re.escape(f"Registry value '{value_name}' not found in key '{full_path}'.")):
        registry_base.get_registry_value(root, key_path, value_name, root_prefix=root_prefix)

    # Verify OpenKey was called and succeeded
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryValueEx was called and failed
    mock_winreg.QueryValueEx.assert_called_once_with(mock_winreg.mock_handle_1, value_name)
    # Verify handle was closed by the context manager
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_values_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp\Settings"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure mock errors
    error_code_no_more_items = 259
    error_message_str_no_more_items = "No more data is available."
    mock_error_no_more_items = OSError(error_code_no_more_items, error_message_str_no_more_items)
    mock_error_no_more_items.winerror = error_code_no_more_items

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure EnumValue for all values (including default)
    mock_winreg.EnumValue.side_effect = [
        ("", "DefaultValue", mock_winreg.REG_SZ), # Default value comes first in enumeration
        ("Value1", "Data1", mock_winreg.REG_SZ),
        ("Value2", 123, mock_winreg.REG_DWORD),
        mock_error_no_more_items # End of enumeration
    ]

    expected_values = [
        ("", "DefaultValue", mock_winreg.REG_SZ),
        ("Value1", "Data1", mock_winreg.REG_SZ),
        ("Value2", 123, mock_winreg.REG_DWORD),
    ]

    values = registry_base.list_registry_values(root, key_path, root_prefix=root_prefix)

    assert values == expected_values

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryValueEx was NOT called
    mock_winreg.QueryValueEx.assert_not_called()
    # Verify EnumValue was called until the end
    assert mock_winreg.EnumValue.call_count == 4 # Called thrice for values, once to get the end error
    mock_winreg.EnumValue.assert_has_calls([
        call(mock_winreg.mock_handle_1, 0), # Default value
        call(mock_winreg.mock_handle_1, 1), # Value1
        call(mock_winreg.mock_handle_1, 2), # Value2
        call(mock_winreg.mock_handle_1, 3), # Error trigger
    ])
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_values_no_default_value(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp\Settings"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure mock errors
    error_code_no_more_items = 259
    error_message_str_no_more_items = "No more data is available."
    mock_error_no_more_items = OSError(error_code_no_more_items, error_message_str_no_more_items)
    mock_error_no_more_items.winerror = error_code_no_more_items

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure EnumValue for named values (no default value in enumeration)
    mock_winreg.EnumValue.side_effect = [
        ("Value1", "Data1", mock_winreg.REG_SZ),
        mock_error_no_more_items # End of enumeration
    ]

    expected_values = [
        ("Value1", "Data1", mock_winreg.REG_SZ),
    ]

    values = registry_base.list_registry_values(root, key_path, root_prefix=root_prefix)

    assert values == expected_values

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryValueEx was NOT called
    mock_winreg.QueryValueEx.assert_not_called()
    assert mock_winreg.EnumValue.call_count == 2
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_values_empty_key(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"EmptyKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure mock error
    error_code_no_more_items = 259
    error_message_str_no_more_items = "No more data is available."
    mock_error_no_more_items = OSError(error_code_no_more_items, error_message_str_no_more_items)
    mock_error_no_more_items.winerror = error_code_no_more_items

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure EnumValue for named values (no named values)
    mock_winreg.EnumValue.side_effect = mock_error_no_more_items

    expected_values = [] # Should return empty list

    values = registry_base.list_registry_values(root, key_path, root_prefix=root_prefix)

    assert values == expected_values

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryValueEx was NOT called
    mock_winreg.QueryValueEx.assert_not_called()
    assert mock_winreg.EnumValue.call_count == 1 # Called once, gets end error immediately
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_values_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to fail with ERROR_FILE_NOT_FOUND (2)
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.OpenKey.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(f"Registry operation failed on key '{full_path}'")):
        registry_base.list_registry_values(root, key_path, root_prefix=root_prefix)

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    mock_winreg.QueryValueEx.assert_not_called()
    mock_winreg.EnumValue.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()


def test_list_registry_subkeys_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure mock error
    error_code_no_more_items = 259
    error_message_str_no_more_items = "No more data is available."
    mock_error_no_more_items = OSError(error_code_no_more_items, error_message_str_no_more_items)
    mock_error_no_more_items.winerror = error_code_no_more_items

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure EnumKey for subkeys
    mock_winreg.EnumKey.side_effect = [
        "Subkey1",
        "Subkey2",
        mock_error_no_more_items # End of enumeration
    ]

    expected_subkeys = ["Subkey1", "Subkey2"]

    subkeys = registry_base.list_registry_subkeys(root, key_path, root_prefix=root_prefix)

    assert subkeys == expected_subkeys

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_ENUMERATE_SUB_KEYS)
    # Verify EnumKey was called until the end
    assert mock_winreg.EnumKey.call_count == 3 # Called twice for names, once to get the end error
    mock_winreg.EnumKey.assert_has_calls([
        call(mock_winreg.mock_handle_1, 0),
        call(mock_winreg.mock_handle_1, 1),
        call(mock_winreg.mock_handle_1, 2),
    ])
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_subkeys_empty_key(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"EmptyKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure mock error
    error_code_no_more_items = 259
    error_message_str_no_more_items = "No more data is available."
    mock_error_no_more_items = OSError(error_code_no_more_items, error_message_str_no_more_items)
    mock_error_no_more_items.winerror = error_code_no_more_items

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure EnumKey for subkeys (no subkeys)
    mock_winreg.EnumKey.side_effect = mock_error_no_more_items

    expected_subkeys = [] # Should return empty list

    subkeys = registry_base.list_registry_subkeys(root, key_path, root_prefix=root_prefix)

    assert subkeys == expected_subkeys

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_ENUMERATE_SUB_KEYS)
    assert mock_winreg.EnumKey.call_count == 1 # Called once, gets end error immediately
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_list_registry_subkeys_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to fail with ERROR_FILE_NOT_FOUND (2)
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.OpenKey.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(f"Registry operation failed on key '{full_path}'")):
        registry_base.list_registry_subkeys(root, key_path, root_prefix=root_prefix)

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_ENUMERATE_SUB_KEYS)
    mock_winreg.EnumKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()


def test_head_registry_key_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"MyApp\Settings"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Mock OpenKey for the RegistryKey context manager
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1
    # Configure QueryInfoKey return value (using a FILETIME integer)
    # winreg.QueryInfoKey returns (num_subkeys, num_values, last_write_time_ft)
    mock_winreg.QueryInfoKey.return_value = (5, 10, 133485408000000000) # 133485408000000000 corresponds to 2024-01-01 00:00:00 UTC

    # Expected datetime object (UTC)
    expected_metadata = {
        "num_subkeys": 5,
        "num_values": 10,
        "last_write_time": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }

    metadata = registry_base.head_registry_key(root, key_path, root_prefix=root_prefix)

    assert metadata == expected_metadata

    # Verify RegistryKey context manager was used with the full path
    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    # Verify QueryInfoKey was called on the handle
    mock_winreg.QueryInfoKey.assert_called_once_with(mock_winreg.mock_handle_1)
    # Verify handle was closed
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_head_registry_key_key_not_found(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    root_prefix = r"Software"
    key_path = r"NonExistentKey"
    full_path = os.path.join(root_prefix, key_path).replace('/', '\\')

    # Configure OpenKey to fail with ERROR_FILE_NOT_FOUND (2)
    error_code = 2
    error_message_str = "The system cannot find the file specified."
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code
    mock_winreg.OpenKey.side_effect = mock_error

    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(f"Registry operation failed on key '{full_path}'")):
        registry_base.head_registry_key(root, key_path, root_prefix=root_prefix)

    mock_winreg.OpenKey.assert_called_once_with(root, full_path, 0, mock_winreg.KEY_READ)
    mock_winreg.QueryInfoKey.assert_not_called()
    mock_winreg.CloseKey.assert_not_called()
