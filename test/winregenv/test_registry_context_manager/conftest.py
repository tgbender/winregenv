import pytest
from unittest.mock import patch, MagicMock, call
import winreg # Import winreg directly for constants if needed, but patch targets the module
import os # Needed for os.path.join in tests
import re # Needed for re.escape in pytest.raises match

# Need to patch the winreg module as it's used within the registry functions
# The patch target needs to be the location where winreg is *used*, not where it's defined.
# In src/winregenv/registry_base.py, winreg is imported directly.
# So the patch target should be 'winregenv.registry_base.winreg'
@pytest.fixture
def mock_winreg(): # Corrected patch target
    # Patch the winreg module as it's imported within src/winregenv/registry_context_managers.py
    with patch('winregenv.registry_context_managers.winreg') as mock:
        # Mock necessary winreg functions and constants
        mock.HKEY_CURRENT_USER = 1 # Example value, actual value doesn't matter for mock
        # Use actual winreg constant values for accuracy in mocks and assertions
        mock.KEY_READ = 0x20019 # Actual value of winreg.KEY_READ
        mock.KEY_WRITE = 0x20006 # Actual value of winreg.KEY_WRITE (includes SET_VALUE, CREATE_SUB_KEY)
        mock.KEY_SET_VALUE = 0x2 # Actual value
        mock.KEY_CREATE_SUB_KEY = 0x4 # Actual value
        mock.KEY_ENUMERATE_SUB_KEYS = 0x8 # Actual value
        mock.KEY_WOW64_32KEY = 0x200 # Actual value for 32-bit view
        mock.REG_SZ = 1 # Example value
        mock.REG_EXPAND_SZ = 2 # Example value
        mock.REG_BINARY = 3 # Example value for the failing test

        # Mock the key object returned by OpenKey and CreateKeyEx
        # These mocks will be used for all handle returns unless side_effect is set
        mock_handle_1 = MagicMock(name="handle1")
        mock_handle_2 = MagicMock(name="handle2")
        mock_handle_3 = MagicMock(name="handle3") # For delete_registry_key check

        # Prevent MagicMock from recording calls to __bool__ which interfere with assert_has_calls
        # when the mock object is used in a 'with' statement.
        # We only care about the winreg API calls (QueryValueEx, SetValueEx, EnumValue, QueryInfoKey, DeleteValue, DeleteKey).
        mock_handle_1.__bool__ = MagicMock(return_value=True)
        mock_handle_2.__bool__ = MagicMock(return_value=True)
        mock_handle_3.__bool__ = MagicMock(return_value=True)

        # --- Configure methods *on the mock handle objects* ---
        # Default QueryValueEx on handle1 (used by get_registry_value)
        # Default: value not found (will be overridden in specific tests)
        error_code_value_not_found = 2
        mock_error_value_not_found = OSError(error_code_value_not_found, "The system cannot find the file specified.")
        mock_error_value_not_found.winerror = error_code_value_not_found
        mock_handle_1.QueryValueEx.side_effect = mock_error_value_not_found

        # Default EnumValue on handle1 (used by list_registry_values)
        # Default: end of enumeration (will be overridden in specific tests)
        error_code_no_more_items = 259
        mock_error_no_more_items = OSError(error_code_no_more_items, "No more data is available.")
        mock_error_no_more_items.winerror = error_code_no_more_items
        mock_handle_1.EnumValue.side_effect = mock_error_no_more_items

        # Default EnumKey on handle1 (used by list_registry_subkeys)
        # Default: end of enumeration (will be overridden in specific tests)
        mock_handle_1.EnumKey.side_effect = mock_error_no_more_items

        # Default QueryInfoKey on handle1 (used by head_registry_key)
        # Default return value (simulate empty key: 0 subkeys, 0 values)
        mock_handle_1.QueryInfoKey.return_value = ("SomeClass", 0, 0, 1234567890.0) # class, num_subkeys, num_values, last_write_time

        # Default SetValueEx on handle1 (used by put_registry_value)
        mock_handle_1.SetValueEx.return_value = None

        # Default DeleteValue on handle1 (used by delete_registry_value)
        # Default: value not found (idempotent)
        mock_handle_1.DeleteValue.side_effect = mock_error_value_not_found

        # Default QueryInfoKey on handle3 (used by delete_registry_key check)
        mock_handle_3.QueryInfoKey.return_value = ("SomeClass", 0, 0, 1234567890.0) # Simulate empty key

        # Default DeleteKey on handle3 (used by delete_registry_key)
        mock_handle_3.DeleteKey.return_value = None

        # Default OpenKey to return mock_handle_1
        mock.OpenKey.return_value = mock_handle_1
        # Default CreateKeyEx to return mock_handle_2
        mock.CreateKeyEx.return_value = mock_handle_2
        mock.CloseKey.return_value = None

        # Store handles for later assertion
        mock.mock_handle_1 = mock_handle_1
        mock.mock_handle_2 = mock_handle_2
        mock.mock_handle_3 = mock_handle_3 # Handle for the key being checked in delete_registry_key

        yield mock
