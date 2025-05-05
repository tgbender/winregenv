import pytest
from unittest.mock import call
import winreg # For constants
# Fixtures are now in conftest.py

import re # Import re for regex matching
# Import the class and exceptions to test
from winregenv.registry_interface import RegistryRoot
from winregenv.registry_errors import RegistryError, RegistryKeyNotFoundError, RegistryValueNotFoundError, \
    RegistryKeyNotEmptyError, RegistryPermissionError

# Import internal helpers/modules that RegistryRoot uses and we will mock
from winregenv import registry_base
from winregenv import registry_translation
from winregenv import elevation_check

# --- Test Cases ---

def test_init_valid_root_keys(mock_elevation_check):
    # Test integer root key
    root_int = winreg.HKEY_CURRENT_USER
    instance_int = RegistryRoot(root_int)
    assert instance_int.root_key == root_int
    assert instance_int.root_prefix is None
    assert instance_int._access_32bit_view is False

    # Test string root key (common name)
    root_str_hkcu = "HKCU"
    instance_str_hkcu = RegistryRoot(root_str_hkcu)
    assert instance_str_hkcu.root_key == winreg.HKEY_CURRENT_USER

    # Test string root key (full name)
    root_str_hklm = "HKEY_LOCAL_MACHINE"
    # Mock is_elevated is not called during init anymore
    instance_str_hklm = RegistryRoot(root_str_hklm)
    assert instance_str_hklm.root_key == winreg.HKEY_LOCAL_MACHINE


def test_init_invalid_root_keys():
    with pytest.raises(ValueError, match="Unknown root key: BADKEY"):
        RegistryRoot("BADKEY")

    with pytest.raises(TypeError, match="Root key must be an integer or string"):
        RegistryRoot(123.45)


def test_init_parameters_stored():
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    view_32bit = True
    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    assert instance.root_key == root
    assert instance.root_prefix == prefix
    assert instance._access_32bit_view == view_32bit


def test_init_elevation_check_required_success(mock_elevation_check):
    # Mock is_elevated to return True (fixture default)
    root_hklm = winreg.HKEY_LOCAL_MACHINE

    # Should not raise
    instance = RegistryRoot(root_hklm)

    # Elevation check is now lazy, not in __init__
    assert instance.root_key == root_hklm


def test_init_elevation_check_not_required(mock_elevation_check):
    # Mock is_elevated (value doesn't matter)
    mock_elevation_check.return_value = False # Or True

    root_hkcu = winreg.HKEY_CURRENT_USER

    # Should not raise and should not call is_elevated
    instance = RegistryRoot(root_hkcu)

    mock_elevation_check.assert_not_called()
    assert instance.root_key == root_hkcu


# --- Test Delegation to registry_base Functions ---

def test_put_registry_value_delegates_correctly(patched_registry_base_funcs, patched_registry_translation_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    value_name = "MyValue"
    value_data = "Some Data"
    explicit_type = winreg.REG_EXPAND_SZ # Test with explicit type
    view_32bit = True

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    # Configure mocks for translation
    patched_registry_translation_funcs['_normalize_registry_type_input'].side_effect = None # Clear default side_effect
    patched_registry_translation_funcs['_normalize_registry_type_input'].return_value = explicit_type
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].side_effect = None # Clear default side_effect
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].return_value = value_data # Assume no conversion needed

    # Action
    instance.put_registry_value(key_path, value_name, value_data, value_type=explicit_type)

    # Assertions
    patched_registry_translation_funcs['_normalize_registry_type_input'].assert_called_once_with(explicit_type)
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].assert_called_once_with(value_data, explicit_type)
    patched_registry_translation_funcs['_infer_registry_type_for_new_value'].assert_not_called() # Explicit type given

    patched_registry_base_funcs['put_registry_value'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        value_name=value_name,
        value_data=value_data,
        value_type=explicit_type,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

def test_put_registry_value_delegates_with_inferred_type(patched_registry_base_funcs, patched_registry_translation_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    value_name = "MyValue"
    value_data = 12345 # Integer data
    inferred_type = winreg.REG_DWORD
    view_32bit = False

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    # Configure mocks for translation (inference path)
    patched_registry_translation_funcs['_infer_registry_type_for_new_value'].side_effect = None # Clear default side_effect
    patched_registry_translation_funcs['_infer_registry_type_for_new_value'].return_value = (value_data, inferred_type)
    # These should not be called when type is None
    patched_registry_translation_funcs['_normalize_registry_type_input'].assert_not_called()
    patched_registry_translation_funcs['_validate_and_convert_data_for_type'].assert_not_called()

    # Action
    instance.put_registry_value(key_path, value_name, value_data, value_type=None) # value_type is None

    # Assertions
    patched_registry_translation_funcs['_infer_registry_type_for_new_value'].assert_called_once_with(value_data)

    patched_registry_base_funcs['put_registry_value'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        value_name=value_name,
        value_data=value_data,
        value_type=inferred_type, # Should use the inferred type
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )


def test_get_registry_value_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    value_name = "MyValue"
    view_32bit = True

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    # Action
    instance.get_registry_value(key_path, value_name)

    # Assertions
    patched_registry_base_funcs['get_registry_value'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        value_name=value_name,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

def test_delete_registry_value_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    value_name = "ToDelete"
    view_32bit = True

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    # Action
    instance.delete_registry_value(key_path, value_name)

    # Assertions
    patched_registry_base_funcs['delete_registry_value'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        value_name=value_name,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )
def test_delete_registry_key_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"KeyToDelete"
    view_32bit = False

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    # Action
    instance.delete_registry_key(key_path)

    # Assertions
    patched_registry_base_funcs['delete_registry_key'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

# Add similar delegation tests for other methods:
# put_registry_subkey, list_registry_values, list_registry_subkeys, head_registry_key
# Example for put_registry_subkey:
def test_put_registry_subkey_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"ParentKey"
    subkey_name = "NewChild"
    view_32bit = True

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    instance.put_registry_subkey(key_path, subkey_name)

    patched_registry_base_funcs['put_registry_subkey'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        subkey_name=subkey_name,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

# Example for list_registry_values:
def test_list_registry_values_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    view_32bit = False

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    instance.list_registry_values(key_path)

    patched_registry_base_funcs['list_registry_values'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

# Example for list_registry_subkeys:
def test_list_registry_subkeys_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"ParentKey"
    view_32bit = True

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    instance.list_registry_subkeys(key_path)

    patched_registry_base_funcs['list_registry_subkeys'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )

# Example for head_registry_key:
def test_head_registry_key_delegates_correctly(patched_registry_base_funcs):
    root = winreg.HKEY_CURRENT_USER
    prefix = r"Software\MyApp"
    key_path = r"Settings"
    view_32bit = False

    instance = RegistryRoot(root, root_prefix=prefix, access_32bit_view=view_32bit)

    instance.head_registry_key(key_path)

    patched_registry_base_funcs['head_registry_key'].assert_called_once_with(
        root_key=root,
        key_path=key_path,
        root_prefix=prefix,
        access_32bit_view=view_32bit
    )
