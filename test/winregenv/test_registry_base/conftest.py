import pytest
from unittest.mock import MagicMock, call
import winreg # Import winreg directly for constants if needed, but patch targets the module
import os # Needed for os.path.join in tests
import re # Needed for re.escape in pytest.raises match

# Need to patch the winreg module as it's used within the registry functions
# The patch target needs to be the location where winreg is *used*, not where it's defined.
# In src/winregenv/registry_base.py, winreg is imported directly.
# In src/winregenv/registry_context_managers.py, winreg is imported directly.
# Since registry_base uses RegistryKey from registry_context_managers,
# we need to patch winreg in *both* modules for tests of registry_base.

@pytest.fixture
def mock_winreg(mocker): # Use the mocker fixture provided by pytest-mock
    # Create a single mock object for winreg
    mock = MagicMock(name='winreg')

    # Apply the mock to both locations where winreg is imported
    # This ensures that both registry_base and registry_context_managers
    # use this mock object when called from within the test scope.
    mocker.patch('winregenv.registry_base.winreg', new=mock)
    mocker.patch('winregenv.registry_context_managers.winreg', new=mock)


    # Configure the single mock object with constants and method behaviors
    # Use actual winreg constant values for accuracy in mocks and assertions
    mock.HKEY_CURRENT_USER = 1 # Example value, actual value doesn't matter for mock
    mock.KEY_READ = winreg.KEY_READ # Use real constants for accuracy
    mock.KEY_WRITE = winreg.KEY_WRITE
    mock.KEY_SET_VALUE = winreg.KEY_SET_VALUE
    mock.KEY_CREATE_SUB_KEY = winreg.KEY_CREATE_SUB_KEY
    mock.KEY_ENUMERATE_SUB_KEYS = winreg.KEY_ENUMERATE_SUB_KEYS
    mock.KEY_WOW64_32KEY = winreg.KEY_WOW64_32KEY
    mock.REG_SZ = winreg.REG_SZ # Use real constants
    mock.REG_EXPAND_SZ = winreg.REG_EXPAND_SZ
    mock.REG_BINARY = winreg.REG_BINARY
    mock.REG_DWORD = winreg.REG_DWORD
    mock.REG_DWORD_BIG_ENDIAN = winreg.REG_DWORD_BIG_ENDIAN
    mock.REG_LINK = winreg.REG_LINK
    mock.REG_MULTI_SZ = winreg.REG_MULTI_SZ
    mock.REG_QWORD = winreg.REG_QWORD
    mock.REG_NONE = winreg.REG_NONE


    # Mock the key object returned by OpenKey and CreateKeyEx
    # These mocks will be used for all handle returns unless side_effect is set
    mock.mock_handle_1 = MagicMock(name="handle1")
    mock.mock_handle_2 = MagicMock(name="handle2")
    mock.mock_handle_3 = MagicMock(name="handle3") # For delete_registry_key check

    # Prevent MagicMock from recording calls to __bool__ which interfere with assert_has_calls
    # when the mock object is used in a 'with' statement.
    # We only care about the winreg API calls (QueryValueEx, SetValueEx, EnumValue, QueryInfoKey, DeleteValue, DeleteKey).
    mock.mock_handle_1.__bool__ = MagicMock(return_value=True)
    mock.mock_handle_2.__bool__ = MagicMock(return_value=True)
    mock.mock_handle_3.__bool__ = MagicMock(return_value=True)

    # --- Configure methods *on the mock handle objects* ---
    # Default QueryValueEx on handle1 (used by get_registry_value)
    # Default: value not found (will be overridden in specific tests)
    error_code_value_not_found = 2
    mock_error_value_not_found = OSError(error_code_value_not_found, "The system cannot find the file specified.")
    mock_error_value_not_found.winerror = error_code_value_not_found
    mock.mock_handle_1.QueryValueEx.side_effect = mock_error_value_not_found

    # Default EnumValue on handle1 (used by list_registry_values)
    # Default: end of enumeration (will be overridden in specific tests)
    error_code_no_more_items = 259
    mock_error_no_more_items = OSError(error_code_no_more_items, "No more data is available.")
    mock_error_no_more_items.winerror = error_code_no_more_items
    mock.mock_handle_1.EnumValue.side_effect = mock_error_no_more_items

    # Default EnumKey on handle1 (used by list_registry_subkeys)
    # Default: end of enumeration (will be overridden in specific tests)
    mock.mock_handle_1.EnumKey.side_effect = mock_error_no_more_items

    # Default QueryInfoKey on handle1 (used by head_registry_key)
    # Default return value (simulate empty key: 0 subkeys, 0 values)
    mock.mock_handle_1.QueryInfoKey.return_value = ("SomeClass", 0, 0, 1234567890.0) # class, num_subkeys, num_values, last_write_time

    # Default SetValueEx on handle1 (used by put_registry_value)
    mock.mock_handle_1.SetValueEx.return_value = None

    # Default DeleteValue on handle1 (used by delete_registry_value)
    # Default: value not found (idempotent)
    mock.mock_handle_1.DeleteValue.side_effect = mock_error_value_not_found

    # Default QueryInfoKey on handle3 (used by delete_registry_key check)
    mock.mock_handle_3.QueryInfoKey.return_value = ("SomeClass", 0, 0, 1234567890.0) # Simulate empty key

    # Default DeleteKey on handle3 (used by delete_registry_key)
    mock.mock_handle_3.DeleteKey.return_value = None

    # Default OpenKey to return mock_handle_1
    mock.OpenKey.return_value = mock.mock_handle_1
    # Default CreateKeyEx to return mock_handle_2
    mock.CreateKeyEx.return_value = mock.mock_handle_2
    mock.CloseKey.return_value = None

    # Store handles on the mock for later assertion if needed (though accessing via mock.method.call_args is often better)
    # mock.mock_handle_1 = mock_handle_1 # Already done above
    # mock.mock_handle_2 = mock_handle_2
    # mock.mock_handle_3 = mock_handle_3

    yield mock # The mock object is yielded by the fixture

    # pytest-mock automatically handles stopping the patches after the test finishes