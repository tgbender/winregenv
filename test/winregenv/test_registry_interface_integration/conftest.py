import pytest
from unittest.mock import patch, MagicMock
import time # For sleep in retry
import sys # Import sys for error logging in cleanup
import winreg # For constants used in fixtures and setup
import logging # Import logging
from winregenv.registry_errors import RegistryKeyNotFoundError, RegistryKeyNotEmptyError, RegistryError # Import specific errors
import winregenv.registry_base as registry_base

# --- Fixtures for Mocking Dependencies ---

@pytest.fixture
def temp_reg_key():
    """
    Fixture to create and clean up a temporary registry key under HKCU.
    Yields the full path to the temporary key.
    """
    root = winreg.HKEY_CURRENT_USER
    logger = logging.getLogger(__name__) # Get logger for this module

    # Use a unique name to avoid conflicts
    # Use a fixed path for easier manual cleanup if needed
    temp_path = r"Software\\winregenvtests_integration\\temp_interface_test_fixed"

    try:
        # ensure_registry_key_exists handles CreateKeyEx and closing the handle
        # ensure_registry_key_exists is imported at the top
        registry_base.ensure_registry_key_exists(root, temp_path)

        yield temp_path # Yield the path for the test to use
    finally:
        # Clean up the key and all its contents using registry_base functions
        # These functions only delete empty keys/values, so we must delete contents first.

        # The keys/values that might get created by tests using this fixture are:
        #   HKEY_CURRENT_USER\Software\winregenvtests_integration\temp_interface_test_fixed\TestValue (value)
        #   HKEY_CURRENT_USER\Software\winregenvtests_integration\temp_interface_test_fixed\ValueToDelete (value)
        #   HKEY_CURRENT_USER\Software\winregenvtests_integration\temp_interface_test_fixed\SubkeyToDelete
        #   HKEY_CURRENT_USER\Software\winregenvtests_integration\temp_interface_test_fixed\TestSubkey
        #   HKEY_CURRENT_USER\Software\winregenvtests_integration\temp_interface_test_fixed
        #
        # We clean these up explicitly, starting with values and subkeys under the base key,
        # then deleting the subkeys, and finally deleting the base key itself.

        root = winreg.HKEY_CURRENT_USER
        base_path = r"Software\\winregenvtests_integration\\temp_interface_test_fixed"
        parent_base_path = r"Software\\winregenvtests_integration"
        base_key_name = "temp_interface_test_fixed"

        # 1. Delete known values from the base key
        values_to_delete = ["TestValue", "ValueToDelete"]
        for value_name in values_to_delete:
            try:
                registry_base.delete_registry_value(root, base_path, value_name)
                logger.debug(f"Cleaned up value '{value_name}' from '{base_path}'")
            except RegistryKeyNotFoundError:
                # Key might not exist if test failed early, ignore
                pass
            except Exception as e:
                # Log other errors but continue cleanup
                logger.error(f"Error cleaning up value '{value_name}' from '{base_path}': {e}", exc_info=True)


        # 2. Delete known subkeys from the base key
        subkeys_to_delete = ["TestSubkey", "SubkeyToDelete"]
        for subkey_name in subkeys_to_delete:
            try:
                # delete_registry_key takes parent path and subkey name
                registry_base.delete_registry_key(root, base_path, subkey_name)
                logger.debug(f"Cleaned up subkey '{subkey_name}' from '{base_path}'")
            except RegistryKeyNotFoundError:
                # Subkey might not exist if test failed early, ignore
                pass
            except RegistryKeyNotEmptyError:
                 # Should not happen if values/subkeys were deleted first, but handle defensively
                 logger.warning(f"Subkey '{subkey_name}' under '{base_path}' was not empty during cleanup.")
            except Exception as e:
                # Log other errors but continue cleanup
                logger.error(f"Error cleaning up subkey '{subkey_name}' from '{base_path}': {e}", exc_info=True)


        # 3. Delete the base key itself
        try:
            # delete_registry_key takes parent path and subkey name
            registry_base.delete_registry_key(root, parent_base_path, base_key_name)
            logger.debug(f"Cleaned up base key '{base_path}'")
        except RegistryKeyNotFoundError:
            # Base key might not exist if test failed early, ignore
            pass
        except RegistryKeyNotEmptyError:
             # Should not happen if values/subkeys were deleted first, but handle defensively
             logger.warning(f"Base key '{base_path}' was not empty during cleanup.")
        except Exception as e:
            # Log other errors
            logger.error(f"Error cleaning up base key '{base_path}': {e}", exc_info=True)

        # Optional: Add a small sleep if experiencing issues with handles not being released immediately
        # time.sleep(0.01)
