import pytest
import sys
import winreg
from unittest.mock import patch

from winregenv.registry_interface import RegistryRoot
from winregenv.registry_errors import RegistryPermissionError, RegistryKeyNotFoundError

# Fixtures like temp_reg_key and mock_elevation_check are available from conftest.py

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows API")

# --- Integration Tests for Read-Only Mode ---

@patch('winregenv.registry_interface.is_elevated', return_value=False)
def test_integration_init_hklm_read_only_success_not_elevated(mock_is_elevated):
    """
    Verify that initializing RegistryRoot for HKLM with read_only=True succeeds
    even when the process is not elevated (integration test).
    """
    # This should not raise RegistryPermissionError
    try:
        instance = RegistryRoot(winreg.HKEY_LOCAL_MACHINE, read_only=True)
        assert instance.root_key == winreg.HKEY_LOCAL_MACHINE
        assert instance._read_only is True
    except RegistryPermissionError:
        pytest.fail("Initializing HKLM with read_only=True failed unexpectedly when not elevated.")
    except Exception as e:
        pytest.fail(f"Initializing HKLM with read_only=True raised unexpected exception: {type(e).__name__}: {e}")

    # Note: We don't assert mock_is_elevated was called here, as the unit test covers that the check is skipped.
    # This test focuses on the real-world outcome of the init call.


def test_integration_read_methods_allowed_in_read_only(temp_reg_key):
    """
    Verify that read/list methods work correctly on a read_only=True instance
    when the user has permissions (integration test).
    """
    root = winreg.HKEY_CURRENT_USER
    key_path = temp_reg_key
    value_name = "TestValue"
    value_data = "TestData"

    # Use a non-read-only instance to write data first
    write_instance = RegistryRoot(root)
    write_instance.put_registry_value(key_path, value_name, value_data, value_type=winreg.REG_SZ)
    write_instance.put_registry_subkey(key_path, "TestSubkey")

    # Create a read-only instance
    read_only_instance = RegistryRoot(root, read_only=True)

    # Test get_registry_value
    value_obj = read_only_instance.get_registry_value(key_path, value_name) # Get the RegistryValue object
    assert value_obj.data == value_data # Access data attribute
    assert value_obj.type == winreg.REG_SZ

    # Test list_registry_values
    values = read_only_instance.list_registry_values(key_path)
    # Find the value we wrote (handle default value if present)
    test_value_found = any(name == value_name and data == value_data and reg_type == winreg.REG_SZ for name, data, reg_type in values)
    assert test_value_found

    # Test list_registry_subkeys
    subkeys = read_only_instance.list_registry_subkeys(key_path)
    assert "TestSubkey" in subkeys

    # Test head_registry_key
    metadata = read_only_instance.head_registry_key(key_path)
    assert metadata['num_subkeys'] >= 1 # May have default subkeys depending on OS
    assert metadata['num_values'] >= 1 # May have default values depending on OS
    assert 'last_write_time' in metadata


def test_integration_write_delete_methods_blocked_in_read_only(temp_reg_key):
    """
    Verify that write/delete methods raise RegistryPermissionError on a read_only=True
    instance, even if the user has permissions (integration test).
    """
    root = winreg.HKEY_CURRENT_USER
    key_path = temp_reg_key
    value_name = "ValueToDelete"
    subkey_name = "SubkeyToDelete"

    # Use a non-read-only instance to create items first
    write_instance = RegistryRoot(root)
    write_instance.put_registry_value(key_path, value_name, "dummy", value_type=winreg.REG_SZ)
    write_instance.put_registry_subkey(key_path, subkey_name)

    # Create a read-only instance
    read_only_instance = RegistryRoot(root, read_only=True)

    # Test put_registry_value is blocked
    with pytest.raises(RegistryPermissionError, match="Cannot perform write/delete operation in read-only mode."):
        read_only_instance.put_registry_value(key_path, "NewValue", "NewData")

    # Test put_registry_subkey is blocked
    with pytest.raises(RegistryPermissionError, match="Cannot perform write/delete operation in read-only mode."):
        read_only_instance.put_registry_subkey(key_path, "AnotherSubkey")

    # Test delete_registry_value is blocked
    with pytest.raises(RegistryPermissionError, match="Cannot perform write/delete operation in read-only mode."):
        read_only_instance.delete_registry_value(key_path, value_name)

    # Test delete_registry_key is blocked
    # Note: We can't delete the root temp_reg_key itself easily here, test deleting a subkey
    with pytest.raises(RegistryPermissionError, match="Cannot perform write/delete operation in read-only mode."):
        read_only_instance.delete_registry_key(f"{key_path}\\{subkey_name}")

    # Clean up the key and its contents using the write instance

