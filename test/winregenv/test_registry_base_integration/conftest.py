# test/winregenv/test_registry_base_integration/conftest.py

import pytest
import winreg
import sys
import os
import logging
from typing import List, Tuple

# Import functions and exceptions from the module under test
from winregenv.registry_base import (
    ensure_registry_key_exists,
    put_registry_value,
    get_registry_value,
    delete_registry_value,
    delete_registry_key,
    _join_registry_paths,
)
from winregenv.registry_errors import RegistryError, RegistryKeyNotFoundError, RegistryValueNotFoundError, \
    RegistryKeyNotEmptyError, RegistryPermissionError

# Configure logging for cleanup warnings
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

# --- Constants ---
INTEGRATION_TEST_BASE_PATH = r"Software\winregenvtests_integration" # Use a distinct name

# Define known keys and values used across different integration tests.
# Tests MUST add any keys/values they create to these lists.
# Keys should be relative to INTEGRATION_TEST_BASE_PATH.
KNOWN_TEST_KEYS: List[str] = [
    "__VerificationKey__", # Used by the fixture setup
    "TestCreateUpdate",
    "TestCreateUpdate\\SubKey1",
    "TestCreateUpdate\\EnsureNew", # Added for test_ensure_registry_key_exists_creates_new
    "TestCreateUpdate\\EnsureExisting", # Added for test_ensure_registry_key_exists_does_nothing_if_exists
    "TestCreateUpdate\\PutNewKey", # Added for test_put_registry_value_creates_key_and_sets_value
    "TestReadList",
    "TestReadList\\SubKeyA",
    "TestReadList\\SubKeyB",
    "TestDelete",
    "TestDelete\\EmptyKeyToDelete",
    "TestDelete\\KeyWithValues",
    "TestDelete\\KeyWithSubkeys",
    "TestDelete\\KeyWithSubkeys\\ChildKey",
    "TestDelete\\KeyToDeleteParent", # Parent for testing delete of its child
    "TestDelete\\KeyToDeleteParent\\ChildKeyToDelete",
]

# Define known values used across different integration tests.
# Values are tuples of (relative_key_path, value_name).
# Use "" for the default value name. Use "" for the key_path if the value is directly under the base path.
KNOWN_TEST_VALUES: List[Tuple[str, str]] = [
    ("", "__VerificationValue__"), # Used by the fixture setup
    ("TestCreateUpdate", "Value1"),
    ("TestCreateUpdate", "ValueToOverwrite"),
    ("TestCreateUpdate", ""), # Default value test
    ("TestCreateUpdate\\PutNewKey", "NewValue"), # Added for test_put_registry_value_creates_key_and_sets_value
    ("TestReadList", "StringValue"),
    ("TestReadList", "IntValue"),
    ("TestReadList", "BinaryValue"),
    ("TestReadList", ""), # Default value
    ("TestDelete\\KeyWithValues", "ValueToDelete1"),
    ("TestDelete\\KeyWithValues", "ValueToDelete2"),
]

# --- Helper Functions ---

def _initial_cleanup_known_keys_values(root_key: int, base_path: str, known_keys: List[str], known_values: List[Tuple[str, str]]):
    """
    Attempts to clean up known registry keys and values under the base path.
    Handles expected errors gracefully (Not Found). Logs warnings for unexpected states (Not Empty).
    This function does NOT perform recursive deletion.
    """
    log.info(f"Starting cleanup under HKEY_CURRENT_USER\\{base_path}")

    # 1. Delete known values first
    # Iterate in reverse order of creation possibility (though order doesn't strictly matter for values)
    for key_rel_path, value_name in reversed(known_values):
        full_key_path = _join_registry_paths(base_path, key_rel_path)
        try:
            log.debug(f"Attempting to delete value: '{value_name}' in '{full_key_path}'")
            delete_registry_value(root_key, full_key_path, value_name)
            log.debug(f"Successfully deleted value: '{value_name}' in '{full_key_path}'")
        except (RegistryValueNotFoundError, RegistryKeyNotFoundError):
            # Expected if the value or its parent key doesn't exist (already cleaned up or never created)
            log.debug(f"Value '{value_name}' in '{full_key_path}' not found (or key missing), skipping deletion.")
            pass
        except RegistryPermissionError:
            log.warning(f"Permission error deleting value '{value_name}' in '{full_key_path}'. Manual cleanup might be needed.")
        except Exception as e:
            log.warning(f"Unexpected error deleting value '{value_name}' in '{full_key_path}': {e}")

    # 2. Delete known keys (only if they are empty)
    # Iterate in reverse order of creation possibility (deeper keys first)
    for key_rel_path in sorted(known_keys, key=len, reverse=True):
        full_key_path = _join_registry_paths(base_path, key_rel_path)
        try:
            log.debug(f"Attempting to delete key: '{full_key_path}'")
            delete_registry_key(root_key, full_key_path)
            log.debug(f"Successfully deleted key: '{full_key_path}'")
        except RegistryKeyNotFoundError:
            # Expected if the key doesn't exist
            log.debug(f"Key '{full_key_path}' not found, skipping deletion.")
            pass
        except RegistryKeyNotEmptyError:
            # This indicates a potential problem - a previous test might have failed
            # or created unexpected items without adding them to KNOWN lists.
            log.warning(f"Key '{full_key_path}' is not empty and cannot be deleted by cleanup. Manual cleanup might be needed.")
        except RegistryPermissionError:
            log.warning(f"Permission error deleting key '{full_key_path}'. Manual cleanup might be needed.")
        except ValueError as e: # Catch attempt to delete root
             log.warning(f"Skipping deletion attempt due to ValueError (likely trying to delete base path itself): {e}")
        except Exception as e:
            log.warning(f"Unexpected error deleting key '{full_key_path}': {e}")

    log.info(f"Finished cleanup under HKEY_CURRENT_USER\\{base_path}")


# --- Main Fixture ---

@pytest.fixture(scope="session")
def real_registry_test_key_base(request):
    """
    Provides access to the real Windows Registry under a dedicated test key (HKCU\\Software\\winregenvtests_integration).

    Performs initial cleanup, verifies basic registry operations are possible,
    and performs final cleanup. Skips all tests using this fixture if the
    initial verification fails.
    """
    if sys.platform != "win32":
        pytest.skip("Windows Registry integration tests require Windows.")

    root_key = winreg.HKEY_CURRENT_USER
    base_path = INTEGRATION_TEST_BASE_PATH
    verification_key_rel = "__VerificationKey__"
    verification_key_full = _join_registry_paths(base_path, verification_key_rel)
    verification_value_name = "__VerificationValue__"
    verification_value_data = "VerifyData"

    # --- Initial Cleanup ---
    # Run cleanup first to remove leftovers from previous failed runs
    _initial_cleanup_known_keys_values(root_key, base_path, KNOWN_TEST_KEYS, KNOWN_TEST_VALUES)

    # --- Setup and Verification ---
    try:
        log.info(f"Setting up and verifying registry access under HKCU\\{base_path}")
        # 1. Ensure the base key exists
        ensure_registry_key_exists(root_key, base_path)
        log.debug(f"Base key HKCU\\{base_path} ensured.")

        # 2. Create a verification key and value
        put_registry_value(root_key, verification_key_full, verification_value_name, verification_value_data, winreg.REG_SZ)
        log.debug(f"Verification value '{verification_value_name}' set in '{verification_key_full}'.")

        # 3. Read back the verification value
        read_value_obj = get_registry_value(root_key, verification_key_full, verification_value_name)
        assert read_value_obj.data == verification_value_data
        assert read_value_obj.type == winreg.REG_SZ
        log.debug(f"Verification value read back successfully.")

        # 4. Delete the verification value
        delete_registry_value(root_key, verification_key_full, verification_value_name)
        log.debug(f"Verification value deleted.")

        # 5. Verify the value is gone (optional but good practice)
        with pytest.raises(RegistryValueNotFoundError):
            get_registry_value(root_key, verification_key_full, verification_value_name)
        log.debug(f"Verified verification value is gone.")

        # 6. Delete the verification key
        delete_registry_key(root_key, verification_key_full)
        log.debug(f"Verification key deleted.")

        # 7. Verify the key is gone (optional but good practice)
        with pytest.raises(RegistryKeyNotFoundError):
             # Attempt to access the deleted key, e.g., by trying to get a value
             get_registry_value(root_key, verification_key_full, "any_value")
        log.debug(f"Verified verification key is gone.")

        log.info(f"Registry access verified successfully.")

    except Exception as e:
        log.error(f"FATAL: Initial registry verification failed under HKCU\\{base_path}: {e}", exc_info=True)
        # Attempt cleanup of verification items even if verification failed mid-way
        log.warning("Attempting cleanup after verification failure...")
        try:
            delete_registry_value(root_key, verification_key_full, verification_value_name)
        except Exception: pass # Ignore cleanup errors here
        try:
            delete_registry_key(root_key, verification_key_full)
        except Exception: pass # Ignore cleanup errors here
        log.warning("Cleanup attempt finished.")
        # Fail the fixture setup - this skips all tests using this fixture
        pytest.fail(f"Registry verification failed under HKCU\\{base_path}. Cannot proceed with integration tests. Error: {e}")

    # --- Yield to Tests ---
    yield root_key, base_path

    # --- Final Teardown ---
    log.info(f"Performing final cleanup for HKCU\\{base_path}")
    _initial_cleanup_known_keys_values(root_key, base_path, KNOWN_TEST_KEYS, KNOWN_TEST_VALUES)
    log.info(f"Final cleanup finished.")
