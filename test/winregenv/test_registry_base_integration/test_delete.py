# test/winregenv/test_registry_base_integration/test_delete.py

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
    head_registry_key,
    _join_registry_paths,
)
from winregenv.registry_errors import RegistryKeyNotFoundError, RegistryValueNotFoundError, RegistryKeyNotEmptyError, \
    RegistryPermissionError

# Configure logging
log = logging.getLogger(__name__)

# --- Pytest Markers ---
pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows Registry"),
    pytest.mark.xdist_group("registry_integration")
]

# --- Test Functions ---

def test_delete_registry_value_success(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key/value defined in KNOWN lists
    test_key_rel = "TestDelete\\KeyWithValues"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    value_name = "ValueToDelete1"
    value_data = "DataToDelete"

    try:
        # Setup
        ensure_registry_key_exists(root_key, test_key_full)
        put_registry_value(root_key, test_key_full, value_name, value_data, winreg.REG_SZ)

        # Pre-verify value exists
        get_registry_value(root_key, test_key_full, value_name)

        # Action
        delete_registry_value(root_key, test_key_full, value_name)

        # Verification: Value should now be gone
        with pytest.raises(RegistryValueNotFoundError):
            get_registry_value(root_key, test_key_full, value_name)

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_delete_registry_value_value_not_found_idempotent(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN lists
    test_key_rel = "TestDelete\\KeyWithValues"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    value_name = "ValueThatNeverExisted"

    try:
        # Setup: Ensure key exists, ensure value does NOT exist
        ensure_registry_key_exists(root_key, test_key_full)
        try:
            delete_registry_value(root_key, test_key_full, value_name)
        except RegistryValueNotFoundError: pass # Ensure it's gone

        # Action: Delete non-existent value (should not raise error)
        delete_registry_value(root_key, test_key_full, value_name)

        # Verification: Check it still doesn't exist
        with pytest.raises(RegistryValueNotFoundError):
            get_registry_value(root_key, test_key_full, value_name)

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_delete_registry_value_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForDeleteValue")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        delete_registry_value(root_key, non_existent_key, "AnyValue")


def test_delete_registry_key_success_empty(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN lists
    test_key_rel = "TestDelete\\EmptyKeyToDelete"
    test_key_full = _join_registry_paths(base_path, test_key_rel)

    try:
        # Setup: Ensure the key exists and is empty
        ensure_registry_key_exists(root_key, test_key_full)
        # Verify it's empty (head_registry_key is useful here)
        info = head_registry_key(root_key, test_key_full)
        assert info["num_subkeys"] == 0
        assert info["num_values"] == 0 # Assumes no default value was set

        # Action
        delete_registry_key(root_key, test_key_full)

        # Verification: Key should be gone
        with pytest.raises(RegistryKeyNotFoundError):
            head_registry_key(root_key, test_key_full)

    finally:
        # Cleanup: Key should already be deleted by the test.
        # Fixture teardown will handle cases where the test failed before deletion.
        pass


def test_delete_registry_key_fails_if_has_values(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use a key defined in KNOWN lists
    test_key_rel = "TestDelete\\KeyWithValues"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    value_name = "ValueToDelete2" # Use the other value defined for this key

    try:
        # Setup: Ensure key exists and has at least one value
        ensure_registry_key_exists(root_key, test_key_full)
        put_registry_value(root_key, test_key_full, value_name, "SomeData", winreg.REG_SZ)

        # Action & Verification
        with pytest.raises(RegistryKeyNotEmptyError):
            delete_registry_key(root_key, test_key_full)

        # Post-verify key still exists
        head_registry_key(root_key, test_key_full)

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_delete_registry_key_fails_if_has_subkeys(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    # Use keys defined in KNOWN lists
    test_key_rel = "TestDelete\\KeyWithSubkeys"
    test_key_full = _join_registry_paths(base_path, test_key_rel)
    subkey_rel = "ChildKey" # Relative to test_key_rel
    subkey_full = _join_registry_paths(test_key_full, subkey_rel)

    try:
        # Setup: Ensure parent and child key exist
        ensure_registry_key_exists(root_key, test_key_full)
        ensure_registry_key_exists(root_key, subkey_full)

        # Action & Verification
        with pytest.raises(RegistryKeyNotEmptyError):
            delete_registry_key(root_key, test_key_full)

        # Post-verify key still exists
        head_registry_key(root_key, test_key_full)

    finally:
        # Cleanup handled by fixture teardown
        pass


def test_delete_registry_key_key_not_found(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base
    non_existent_key = _join_registry_paths(base_path, "NonExistentKeyForDeleteKey")

    # Action & Verification
    with pytest.raises(RegistryKeyNotFoundError):
        delete_registry_key(root_key, non_existent_key)


def test_delete_registry_key_value_error_on_root(real_registry_test_key_base):
    root_key, base_path = real_registry_test_key_base

    # Action & Verification: Trying to delete the base path itself (which is not empty)
    # This should raise RegistryKeyNotEmptyError, not ValueError.
    with pytest.raises(RegistryKeyNotEmptyError):
        delete_registry_key(root_key, base_path) # Deleting the base path used by tests

    # Action & Verification: Trying to delete "" relative to base path (which is base_path)
    # This also attempts to delete the non-empty base_path.
    with pytest.raises(RegistryKeyNotEmptyError):
         delete_registry_key(root_key, "", root_prefix=base_path) # This resolves to full_path=base_path


def test_delete_registry_key_value_error_on_actual_root(real_registry_test_key_base):
    """Verify ValueError is raised when attempting to delete the actual root key."""
    root_key, _ = real_registry_test_key_base # We only need the root_key handle

    # Action & Verification: Trying to delete the actual root key (full_path is "")
    with pytest.raises(ValueError):
        delete_registry_key(root_key, "", root_prefix="") # This resolves to full_path=""

    # Also test the explicit case where key_path is the root_prefix and root_prefix is ""
    with pytest.raises(ValueError):
        delete_registry_key(root_key, "", root_prefix="")

    # Test deleting the root_key handle itself (should also hit the ValueError check)
    with pytest.raises(ValueError):
        delete_registry_key(root_key, "", root_prefix="")


def test_delete_registry_key_deletes_child_correctly(real_registry_test_key_base):
    """Verify that delete_registry_key correctly identifies parent and child."""
    root_key, base_path = real_registry_test_key_base
    # Use keys defined in KNOWN lists
    parent_key_rel = "TestDelete\\KeyToDeleteParent"
    parent_key_full = _join_registry_paths(base_path, parent_key_rel)
    child_key_name = "ChildKeyToDelete" # Name of the key to delete
    child_key_full = _join_registry_paths(parent_key_full, child_key_name) # Full path to child

    try:
        # Setup: Create parent and the empty child key to delete
        ensure_registry_key_exists(root_key, parent_key_full)
        ensure_registry_key_exists(root_key, child_key_full)

        # Pre-verify child exists
        head_registry_key(root_key, child_key_full)

        # Action: Delete the child key using its full path
        delete_registry_key(root_key, child_key_full)

        # Verification: Child key should be gone
        with pytest.raises(RegistryKeyNotFoundError):
            head_registry_key(root_key, child_key_full)

        # Verification: Parent key should still exist
        head_registry_key(root_key, parent_key_full)

    finally:
        # Cleanup handled by fixture teardown (parent and child are in KNOWN lists)
        pass
