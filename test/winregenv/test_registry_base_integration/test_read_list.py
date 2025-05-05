# test/winregenv/test_registry_base_integration/test_read_list.py

import pytest
import winreg
import sys
import os
import logging
from datetime import datetime, timezone, timedelta

# Import functions and exceptions from the module under test
from winregenv.registry_base import (
    ensure_registry_key_exists,
    put_registry_value,
    put_registry_subkey,
    get_registry_value,
    list_registry_values,
    list_registry_subkeys,
    head_registry_key,
    delete_registry_value,
    delete_registry_key,
    _join_registry_paths,
)
from winregenv.registry_errors import RegistryKeyNotFoundError, RegistryValueNotFoundError

# Configure logging
log = logging.getLogger(__name__)

# --- Pytest Markers ---
pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows Registry"),
    pytest.mark.xdist_group("registry_integration")
]

# --- Test Data ---
# Use keys/values defined in conftest.py's KNOWN lists
TEST_KEY_REL = "TestReadList"
DEFAULT_VALUE_NAME = ""
DEFAULT_VALUE_DATA = "DefaultReadData"
STRING_VALUE_NAME = "StringValue"
STRING_VALUE_DATA = "String Data"
INT_VALUE_NAME = "IntValue"
INT_VALUE_DATA = 12345
BINARY_VALUE_NAME = "BinaryValue"
BINARY_VALUE_DATA = b'\x01\x02\x03\x00\xff'
SUBKEY_A_NAME = "SubKeyA"
SUBKEY_B_NAME = "SubKeyB"

# --- Helper to Setup Test Key ---
def setup_read_list_key(root_key, base_path):
    """Creates the standard key, values, and subkeys for read/list tests."""
    test_key_full = _join_registry_paths(base_path, TEST_KEY_REL)
    subkey_a_full = _join_registry_paths(test_key_full, SUBKEY_A_NAME)
    subkey_b_full = _join_registry_paths(test_key_full, SUBKEY_B_NAME)

    ensure_registry_key_exists(root_key, test_key_full)
    put_registry_value(root_key, test_key_full, DEFAULT_VALUE_NAME, DEFAULT_VALUE_DATA, winreg.REG_SZ)
    put_registry_value(root_key, test_key_full, STRING_VALUE_NAME, STRING_VALUE_DATA, winreg.REG_SZ)
    put_registry_value(root_key, test_key_full, INT_VALUE_NAME, INT_VALUE_DATA, winreg.REG_DWORD)
    put_registry_value(root_key, test_key_full, BINARY_VALUE_NAME, BINARY_VALUE_DATA, winreg.REG_BINARY)
    ensure_registry_key_exists(root_key, subkey_a_full) # Create subkeys using ensure
    ensure_registry_key_exists(root_key, subkey_b_full)

# --- Test Functions ---

def test_get_registry_value_success(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_full = _join_registry_paths(base_path, TEST_KEY_REL)

    try:
        # Setup
        setup_read_list_key(root_key, base_path)

        # Action & Verification (String)
        value_obj_string = get_registry_value(root_key, test_key_full, STRING_VALUE_NAME)
        assert value_obj_string.data == STRING_VALUE_DATA
        assert value_obj_string.type == winreg.REG_SZ

        # Action & Verification (Integer)
        value_obj_int = get_registry_value(root_key, test_key_full, INT_VALUE_NAME)
        assert value_obj_int.data == INT_VALUE_DATA
        assert value_obj_int.type == winreg.REG_DWORD

        # Action & Verification (Binary)
        value_obj_binary = get_registry_value(root_key, test_key_full, BINARY_VALUE_NAME)
        assert value_obj_binary.data == BINARY_VALUE_DATA
        assert value_obj_binary.type == winreg.REG_BINARY

        # Action & Verification (Default)
        value_obj_default = get_registry_value(root_key, test_key_full, DEFAULT_VALUE_NAME)
        assert value_obj_default.data == DEFAULT_VALUE_DATA
        assert value_obj_default.type == winreg.REG_SZ

    finally:
        # Cleanup handled by fixture teardown as items are in KNOWN lists
        pass


def test_get_registry_value_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForRead")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        get_registry_value(root_key, non_existent_key, "AnyValue")


def test_get_registry_value_value_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_rel = "TestReadList" # Use a key defined in KNOWN lists
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Setup: Ensure key exists but value doesn't
        ensure_registry_key_exists(root_key, test_key_full)
        # Make sure the specific value we test for doesn't exist
        try:
            delete_registry_value(root_key, test_key_full, "NonExistentValue")
        except RegistryValueNotFoundError:
            pass # Expected

        # Action & Verification
        with pytest.raises(RegistryValueNotFoundError):
            get_registry_value(root_key, test_key_full, "NonExistentValue")

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_list_registry_values_success(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_full = _join_registry_paths(base_path, TEST_KEY_REL)

    try:
        # Setup
        setup_read_list_key(root_key, base_path)

        # Action
        values = list_registry_values(root_key, test_key_full)

        # Verification
        # Convert list of tuples to a dict for easier comparison
        values_dict = {name: (data, type) for name, data, type in values}

        assert len(values) == 4 # Default, String, Int, Binary
        assert DEFAULT_VALUE_NAME in values_dict
        assert values_dict[DEFAULT_VALUE_NAME] == (DEFAULT_VALUE_DATA, winreg.REG_SZ)
        assert STRING_VALUE_NAME in values_dict
        assert values_dict[STRING_VALUE_NAME] == (STRING_VALUE_DATA, winreg.REG_SZ)
        assert INT_VALUE_NAME in values_dict
        assert values_dict[INT_VALUE_NAME] == (INT_VALUE_DATA, winreg.REG_DWORD)
        assert BINARY_VALUE_NAME in values_dict
        assert values_dict[BINARY_VALUE_NAME] == (BINARY_VALUE_DATA, winreg.REG_BINARY)

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_list_registry_values_empty_key(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key that's known but ensure it's empty for this test
    test_key_rel = "TestDelete\\EmptyKeyToDelete" # Re-use an empty key definition
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Setup: Ensure the key exists but is empty
        ensure_registry_key_exists(root_key, test_key_full)
        # Explicitly delete potential default value if it exists from previous runs
        try:
            delete_registry_value(root_key, test_key_full, "")
        except RegistryValueNotFoundError: pass

        # Action
        values = list_registry_values(root_key, test_key_full)

        # Verification
        assert values == []

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_list_registry_values_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForListValues")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        list_registry_values(root_key, non_existent_key)


def test_list_registry_subkeys_success(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_full = _join_registry_paths(base_path, TEST_KEY_REL)

    try:
        # Setup
        setup_read_list_key(root_key, base_path) # This creates SubKeyA and SubKeyB

        # Action
        subkeys = list_registry_subkeys(root_key, test_key_full)

        # Verification
        assert sorted(subkeys) == sorted([SUBKEY_A_NAME, SUBKEY_B_NAME])

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_list_registry_subkeys_empty_key(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key that's known but ensure it's empty for this test
    test_key_rel = "TestDelete\\EmptyKeyToDelete" # Re-use an empty key definition
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Setup: Ensure the key exists but has no subkeys
        ensure_registry_key_exists(root_key, test_key_full)
        # Explicitly delete potential subkeys if they exist from previous runs (shouldn't happen with KNOWN list)

        # Action
        subkeys = list_registry_subkeys(root_key, test_key_full)

        # Verification
        assert subkeys == []

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_list_registry_subkeys_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForListSubkeys")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        list_registry_subkeys(root_key, non_existent_key)


def test_head_registry_key_success(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    test_key_full = _join_registry_paths(base_path, TEST_KEY_REL)

    try:
        # Setup: Record time before setup, setup, record time after
        time_before = datetime.now(timezone.utc) - timedelta(seconds=1) # Allow slight clock skew
        setup_read_list_key(root_key, base_path)
        time_after = datetime.now(timezone.utc) + timedelta(seconds=1) # Allow slight clock skew

        # Action
        info = head_registry_key(root_key, test_key_full)

        # Verification
        assert info["num_subkeys"] == 2 # SubKeyA, SubKeyB
        assert info["num_values"] == 4 # Default, String, Int, Binary
        # Removed assertion for 'class_name' as QueryInfoKey does not return it
        assert isinstance(info["last_write_time"], datetime)
        # Check timestamp is within the expected range
        assert time_before <= info["last_write_time"] <= time_after
        # Check timestamp is timezone-aware (UTC)
        assert info["last_write_time"].tzinfo is timezone.utc

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_head_registry_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForHead")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        head_registry_key(root_key, non_existent_key)
