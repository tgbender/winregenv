import pytest
from unittest.mock import call
import re # Needed for re.escape in pytest.raises match
import winreg # Import winreg directly for constants if needed

import winregenv.registry_errors
# Import the module containing the RegistryKey context manager and exceptions
from winregenv import registry_context_managers

# The mock_winreg fixture is provided by conftest.py in the same directory

def test_registry_key_context_manager_success(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    subkey = r"Environment"
    access = mock_winreg.KEY_READ

    # Reset OpenKey side_effect if it was set by another test/fixture
    mock_winreg.OpenKey.side_effect = None
    # Ensure OpenKey returns a specific mock handle for this test
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1

    with registry_context_managers.RegistryKey(root, subkey, access) as key:
        assert key == mock_winreg.mock_handle_1
        mock_winreg.OpenKey.assert_called_once_with(root, subkey, 0, access)

    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1)


def test_registry_key_context_manager_open_error(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    subkey = r"NonExistentKey"
    access = mock_winreg.KEY_READ
    # Configure OpenKey to raise an OSError instance with the winerror attribute set,
    # mimicking the behavior of the actual winreg module on Windows.
    error_code = 2
    error_message_str = "The system cannot find the file specified."

    # Create the OSError instance and set its winerror attribute
    mock_error = OSError(error_code, error_message_str)
    mock_error.winerror = error_code # This is crucial

    # Set the side_effect to raise the configured OSError instance
    mock_winreg.OpenKey.side_effect = mock_error

    # The expected message includes the WinError details added by _handle_winreg_error
    # Construct the expected full message string
    expected_full_message = f"Registry operation failed on key '{subkey}' (WinError {error_code}: {error_message_str})"

    # Use pytest.raises to assert that the correct exception is raised
    # Use re.escape for the match pattern to handle potential special characters
    with pytest.raises(winregenv.registry_errors.RegistryKeyNotFoundError, match=re.escape(expected_full_message)):
        with registry_context_managers.RegistryKey(root, subkey, access) as key:
            # This code inside the inner 'with' should not be reached
            pass

    mock_winreg.OpenKey.assert_called_once_with(root, subkey, 0, access)
    mock_winreg.CloseKey.assert_not_called() # CloseKey should not be called if OpenKey failed


def test_registry_key_context_manager_error_inside_with(mock_winreg):
    root = mock_winreg.HKEY_CURRENT_USER
    subkey = r"Environment"
    access = mock_winreg.KEY_READ

    # Reset OpenKey side_effect
    mock_winreg.OpenKey.side_effect = None
    # Ensure OpenKey returns a specific mock handle for this test
    mock_winreg.OpenKey.return_value = mock_winreg.mock_handle_1

    class CustomError(Exception):
        pass

    with pytest.raises(CustomError):
        with registry_context_managers.RegistryKey(root, subkey, access) as key:
            assert key == mock_winreg.mock_handle_1
            raise CustomError("Something went wrong")

    mock_winreg.OpenKey.assert_called_once_with(root, subkey, 0, access)
    mock_winreg.CloseKey.assert_called_once_with(mock_winreg.mock_handle_1) # Close should still be called
