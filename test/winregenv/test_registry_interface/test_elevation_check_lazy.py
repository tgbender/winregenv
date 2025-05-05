import pytest
import winreg # For constants
import re # Import re for regex matching

# Import the class and exceptions to test
from winregenv.registry_interface import RegistryRoot
from winregenv.registry_errors import RegistryPermissionError

# Fixtures like mock_elevation_check, patched_registry_base_funcs,
# and patched_registry_translation_funcs are provided by conftest.py

# --- Tests for Lazy Elevation Check on Sensitive Keys (Write/Delete) ---

def test_write_elevation_check_required_success(patched_registry_base_funcs, patched_registry_translation_funcs, mock_elevation_check):
    """Test write operation on sensitive key when process is elevated."""
    # Mock is_elevated to return True
    mock_elevation_check.return_value = True

    root = winreg.HKEY_LOCAL_MACHINE # Sensitive key
    instance = RegistryRoot(root)

    # Configure mocks for translation (minimal setup needed as we only check flow)
    patched_registry_translation_funcs['_normalize_registry_type_input'].return_value = winreg.REG_SZ
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].return_value = "data"

    # Action: Call a write method
    instance.put_registry_value("Key", "Value", "Data", value_type=winreg.REG_SZ)

    # Assertions: is_elevated should have been called once
    mock_elevation_check.assert_called_once()
    # And the underlying base function should have been called
    patched_registry_base_funcs['put_registry_value'].assert_called_once()


def test_write_elevation_check_required_failure(patched_registry_base_funcs, patched_registry_translation_funcs, mock_elevation_check):
    """Test write operation on sensitive key when process is NOT elevated."""
    # Mock is_elevated to return False
    mock_elevation_check.return_value = False

    root = winreg.HKEY_LOCAL_MACHINE # Sensitive key
    instance = RegistryRoot(root)

    # Configure mocks for translation (they shouldn't be reached if error is raised first)
    patched_registry_translation_funcs['_normalize_registry_type_input'].return_value = winreg.REG_SZ
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].return_value = "data"

    # Action: Call a write method and expect an error
    with pytest.raises(RegistryPermissionError, match=re.escape(f"Write/delete operation on root key 'HKEY_LOCAL_MACHINE' ({root}) typically requires elevated (administrator) privileges, but the current process is not elevated.")):
        instance.put_registry_value("Key", "Value", "Data", value_type=winreg.REG_SZ)

    # Assertions: is_elevated should have been called once
    mock_elevation_check.assert_called_once()
    # And the underlying base function should NOT have been called
    patched_registry_base_funcs['put_registry_value'].assert_not_called()


def test_delete_elevation_check_required_success(patched_registry_base_funcs, mock_elevation_check):
    """Test delete operation on sensitive key when process is elevated."""
    mock_elevation_check.return_value = True
    root = winreg.HKEY_LOCAL_MACHINE
    instance = RegistryRoot(root)

    instance.delete_registry_value("Key", "Value")

    mock_elevation_check.assert_called_once()
    patched_registry_base_funcs['delete_registry_value'].assert_called_once()


def test_delete_elevation_check_required_failure(patched_registry_base_funcs, mock_elevation_check):
    """Test delete operation on sensitive key when process is NOT elevated."""
    mock_elevation_check.return_value = False
    root = winreg.HKEY_LOCAL_MACHINE
    instance = RegistryRoot(root)

    with pytest.raises(RegistryPermissionError, match=re.escape(f"Write/delete operation on root key 'HKEY_LOCAL_MACHINE' ({root}) typically requires elevated (administrator) privileges, but the current process is not elevated.")):
        instance.delete_registry_value("Key", "Value")

    mock_elevation_check.assert_called_once()
    patched_registry_base_funcs['delete_registry_value'].assert_not_called()


def test_write_delete_elevation_check_is_cached(patched_registry_base_funcs, patched_registry_translation_funcs, mock_elevation_check):
    """Test that elevation check is cached after the first write/delete operation."""
    mock_elevation_check.return_value = True # Assume elevated
    root = winreg.HKEY_LOCAL_MACHINE
    instance = RegistryRoot(root)

    # Configure mocks for translation (minimal setup needed)
    patched_registry_translation_funcs['_normalize_registry_type_input'].return_value = winreg.REG_SZ
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].return_value = "data"

    # First write operation should trigger the check
    instance.put_registry_value("Key", "Value1", "Data1", value_type=winreg.REG_SZ)
    mock_elevation_check.assert_called_once()

    # Second write operation should NOT trigger the check again
    instance.put_registry_value("Key", "Value2", "Data2", value_type=winreg.REG_SZ)
    mock_elevation_check.assert_called_once() # Still only called once

    # Delete operation should also use the cache
    instance.delete_registry_value("Key", "Value1")
    mock_elevation_check.assert_called_once() # Still only called once

    # Read operation should not trigger the check
    instance.get_registry_value("Key", "Value2") # get_registry_value is a read operation
    mock_elevation_check.assert_called_once() # Still only called once


def test_write_delete_elevation_check_ignored_when_flag_set(patched_registry_base_funcs, patched_registry_translation_funcs, mock_elevation_check):
    """Test that elevation check is skipped when ignore_elevation_check=True."""
    mock_elevation_check.return_value = False # Assume NOT elevated
    root = winreg.HKEY_LOCAL_MACHINE
    # Initialize with ignore_elevation_check=True
    instance = RegistryRoot(root, ignore_elevation_check=True)

    # Configure mocks for translation (minimal setup needed)
    patched_registry_translation_funcs['_normalize_registry_type_input'].return_value = winreg.REG_SZ
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].return_value = "data"

    # Write operation should NOT trigger the check and should NOT raise error
    instance.put_registry_value("Key", "Value", "Data", value_type=winreg.REG_SZ)
    mock_elevation_check.assert_not_called()
    patched_registry_base_funcs['put_registry_value'].assert_called_once()

    # Reset mock call count for clarity on the next operation
    mock_elevation_check.reset_mock()
    patched_registry_base_funcs['put_registry_value'].reset_mock()

    # Delete operation should NOT trigger the check and should NOT raise error
    instance.delete_registry_key("KeyToDelete")
    mock_elevation_check.assert_not_called()
    patched_registry_base_funcs['delete_registry_key'].assert_called_once()


def test_write_delete_elevation_check_oserror_handling(patched_registry_base_funcs, patched_registry_translation_funcs, mock_elevation_check):
    """Test that OSError during elevation check is handled and re-raised."""
    # Mock is_elevated to raise OSError
    mock_elevation_check.side_effect = OSError("Simulated OS error")

    root = winreg.HKEY_LOCAL_MACHINE # Sensitive key
    instance = RegistryRoot(root)

    # Attempting a write operation should catch the OSError and raise RegistryPermissionError
    with pytest.raises(RegistryPermissionError, match=re.escape(f"Failed to determine process elevation status required for write/delete operations on root key 'HKEY_LOCAL_MACHINE' ({root}). Underlying check failed: Simulated OS error")):
        instance.put_registry_value("Key", "Value", "Data", value_type=winreg.REG_SZ)

    # is_elevated should have been called once
    mock_elevation_check.assert_called_once()
    # Underlying base function should NOT have been called
    patched_registry_base_funcs['put_registry_value'].assert_not_called()
