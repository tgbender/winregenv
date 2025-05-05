# test/winregenv/test_registry_base_integration/test_create_update.py

import pytest
import winreg
import sys
import os
import logging

# Import functions and exceptions from the module under test
from winregenv.registry_base import (
    ensure_registry_key_exists,
    put_registry_value,
    put_registry_subkey,
    get_registry_value,
    delete_registry_value,
    delete_registry_key,
    list_registry_subkeys,
    # Import if you plan specific permission tests
    _join_registry_paths,
)
from winregenv.registry_errors import RegistryKeyNotFoundError, RegistryValueNotFoundError, RegistryPermissionError

# Configure logging
log = logging.getLogger(__name__)

# --- Pytest Markers ---
# Skip all tests in this module if not on Windows
# Group tests to ensure sequential execution because they share the registry state
pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows Registry"),
    pytest.mark.xdist_group("registry_integration") # Ensures sequential execution
]

# --- Test Functions ---

def test_ensure_registry_key_exists_creates_new(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_rel = "TestCreateUpdate\\EnsureNew"
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Action
        ensure_registry_key_exists(root_key, test_key_full)

        # Verification: Try opening the key (will raise error if it doesn't exist)
        # Use winreg directly for verification to avoid circular dependency on tested code if possible
        handle = winreg.OpenKey(root_key, test_key_full, 0, winreg.KEY_READ)
        winreg.CloseKey(handle)
        assert True # If OpenKey succeeded, the key exists

    finally:
        # Cleanup
        # The fixture's final cleanup will handle this key as it's in KNOWN_TEST_KEYS
        pass


def test_ensure_registry_key_exists_does_nothing_if_exists(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_rel = "TestCreateUpdate\\EnsureExisting"
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Setup: Create the key first
        ensure_registry_key_exists(root_key, test_key_full)

        # Action: Call ensure again
        ensure_registry_key_exists(root_key, test_key_full)

        # Verification: Key should still exist
        handle = winreg.OpenKey(root_key, test_key_full, 0, winreg.KEY_READ)
        winreg.CloseKey(handle)
        assert True

    finally:
        # Cleanup
        # The fixture's final cleanup will handle this key as it's in KNOWN_TEST_KEYS
        pass


def test_put_registry_value_creates_key_and_sets_value(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_rel = "TestCreateUpdate\\PutNewKey"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    value_name = "NewValue"
    value_data = "TestData"
    value_type = winreg.REG_SZ

    try:
        # Action
        put_registry_value(root_key, test_key_full, value_name, value_data, value_type)

        # Verification: Use get_registry_value (part of the module, but essential for verification)
        read_value_obj = get_registry_value(root_key, test_key_full, value_name) # Get the RegistryValue object
        assert read_value_obj.data == value_data
        assert read_value_obj.type == value_type

    finally:
        # Cleanup: Handled by fixture teardown as key and value are in KNOWN lists
        pass


def test_put_registry_value_updates_existing_value(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN_TEST_KEYS for easier cleanup tracking
    test_key_rel = "TestCreateUpdate"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    # Use a value defined in KNOWN_TEST_VALUES
    value_name = "ValueToOverwrite"
    initial_data = "Initial"
    updated_data = "Updated"
    value_type = winreg.REG_SZ

    try:
        # Setup: Ensure key exists and set initial value
        ensure_registry_key_exists(root_key, test_key_full)
        put_registry_value(root_key, test_key_full, value_name, initial_data, value_type)

        # Action: Update the value
        put_registry_value(root_key, test_key_full, value_name, updated_data, value_type)

        # Verification
        read_value_obj = get_registry_value(root_key, test_key_full, value_name) # Get the RegistryValue object
        assert read_value_obj.data == updated_data # Access data attribute
        assert read_value_obj.type == value_type

    finally:
        # Cleanup: Value will be cleaned by the fixture's final cleanup
        # as it's in KNOWN_TEST_VALUES. No specific cleanup needed here.
        pass


def test_put_registry_value_sets_default_value(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN_TEST_KEYS
    test_key_rel = "TestCreateUpdate"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    value_name = "" # Default value
    value_data = "DefaultData"
    value_type = winreg.REG_SZ

    try:
        # Setup: Ensure key exists
        ensure_registry_key_exists(root_key, test_key_full)

        # Action
        put_registry_value(root_key, test_key_full, value_name, value_data, value_type)

        # Verification
        read_value_obj = get_registry_value(root_key, test_key_full, value_name) # Get the RegistryValue object
        assert read_value_obj.data == value_data # Access data attribute
        assert read_value_obj.type == value_type

    finally:
        # Cleanup: Value will be cleaned by the fixture's final cleanup
        pass


def test_put_registry_subkey_creates_new_subkey(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN_TEST_KEYS
    parent_key_rel = "TestCreateUpdate"
    parent_key_full = _join_registry_paths(base_path, parent_key_rel)
    # Use a subkey defined in KNOWN_TEST_KEYS
    subkey_name = "SubKey1"
    subkey_full = _join_registry_paths(parent_key_full, subkey_name)

    try:
        # Setup: Ensure parent key exists
        ensure_registry_key_exists(root_key, parent_key_full)

        # Action
        put_registry_subkey(root_key, parent_key_full, subkey_name)

        # Verification: Check if the subkey exists by trying to open it
        handle = winreg.OpenKey(root_key, subkey_full, 0, winreg.KEY_READ)
        winreg.CloseKey(handle)
        assert True # If OpenKey succeeded

    finally:
        # Cleanup: Subkey will be cleaned by the fixture's final cleanup
        pass
