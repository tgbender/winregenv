import pytest
import winreg
from unittest.mock import call

from winregenv.registry_interface import RegistryRoot
from winregenv.registry_errors import RegistryPermissionError

# Fixtures like patched_registry_base_funcs, patched_registry_translation_funcs,
# and mock_elevation_check are automatically available from conftest.py

# --- Test Cases for Read-Only Mode ---

def test_init_elevation_required_read_only_success(mock_elevation_check):
    """
    Verify that initializing RegistryRoot with read_only=True on an elevation-required
    key succeeds even if the process is not elevated.
    """
    # Mock is_elevated to return False
    mock_elevation_check.return_value = False
    root_hklm = winreg.HKEY_LOCAL_MACHINE

    # Should NOT raise RegistryPermissionError when read_only=True
    instance = RegistryRoot(root_hklm, read_only=True)

    # Assert that the elevation check was skipped because read_only was True
    mock_elevation_check.assert_not_called()
    assert instance.root_key == root_hklm
    assert instance._read_only is True

def test_init_non_elevation_required_read_only_success(mock_elevation_check):
    """
    Verify that initializing RegistryRoot with read_only=True on a non-elevation-required
    key succeeds (same as non-read-only).
    """
    # Mock is_elevated (value doesn't matter, shouldn't be called)
    mock_elevation_check.return_value = False # Or True
    root_hkcu = winreg.HKEY_CURRENT_USER

    # Should not raise and should not call is_elevated
    instance = RegistryRoot(root_hkcu, read_only=True)

    mock_elevation_check.assert_not_called()
    assert instance.root_key == root_hkcu
    assert instance._read_only is True


@pytest.mark.parametrize("method_name, args", [
    ('put_registry_value', ('some\\key', 'some_value', 'data')),
    ('put_registry_subkey', ('some\\key', 'new_subkey')),
    ('delete_registry_value', ('some\\key', 'value_to_delete')),
    ('delete_registry_key', ('key_to_delete',)),
])
def test_write_delete_methods_raise_permission_error_in_read_only(
    method_name, args, patched_registry_base_funcs
):
    """
    Verify that write/delete methods raise RegistryPermissionError when in read-only mode
    and do NOT call the underlying registry_base functions.
    """
    # Create a read-only instance (root key doesn't strictly matter for this check)
    instance = RegistryRoot(winreg.HKEY_CURRENT_USER, read_only=True)

    # Get the method from the instance
    method_to_test = getattr(instance, method_name)

    # Action & Assertion: Should raise RegistryPermissionError
    with pytest.raises(RegistryPermissionError, match="Cannot perform write/delete operation in read-only mode."):
        method_to_test(*args)

    # Assert that the corresponding registry_base function was NOT called
    # The mock names match the method names
    mock_func = patched_registry_base_funcs[method_name]
    mock_func.assert_not_called()


@pytest.mark.parametrize("method_name, args", [
    ('get_registry_value', ('some\\key', 'some_value')),
    ('list_registry_values', ('some\\key',)),
    ('list_registry_subkeys', ('some\\key',)),
    ('head_registry_key', ('some\\key',)),
])
def test_read_list_methods_allowed_in_read_only(method_name, args, patched_registry_base_funcs):
    """
    Verify that read/list methods do NOT raise an error in read-only mode
    and DO call the underlying registry_base functions.
    """
    instance = RegistryRoot(winreg.HKEY_CURRENT_USER, read_only=True)
    method_to_test = getattr(instance, method_name)

    # Action: Call the method. Should not raise RegistryPermissionError from RegistryRoot.
    # Any permission error would come from the underlying winreg call, translated by _handle_winreg_error.
    # Since our mock doesn't raise, this call should succeed.
    method_to_test(*args)

    # Assert that the corresponding registry_base function WAS called
    mock_func = patched_registry_base_funcs[method_name]
    mock_func.assert_called_once()
