import pytest
from unittest.mock import patch, MagicMock
import time # For sleep in retry
import sys # Import sys for error logging in cleanup
import winreg # For constants used in fixtures and setup

# --- Fixtures for Mocking Dependencies ---

@pytest.fixture
def patched_registry_base_funcs():
    """Mocks the functions imported from registry_base into registry_interface."""
    # Define the functions imported and used by RegistryRoot methods
    functions_to_patch = {
        'put_registry_value': None, # Default return value
        'put_registry_subkey': None,
        'get_registry_value': ("mock_data", winreg.REG_SZ),
        'list_registry_values': [],
        'list_registry_subkeys': [],
        'head_registry_key': {"num_subkeys": 0, "num_values": 0, "last_write_time": MagicMock()},
        'delete_registry_value': None,
        'delete_registry_key': None,
        # Note: ensure_registry_key_exists is NOT directly called by RegistryRoot methods,
        # but by the registry_base functions themselves. We only mock the direct calls.
    }
    mocks = {}
    patchers = []
    try:
        for func_name, default_return in functions_to_patch.items():
            # Patch the function name where it's looked up (in registry_interface)
            target = f'winregenv.registry_interface.{func_name}'
            patcher = patch(target, autospec=True)
            mock_func = patcher.start()
            # Set default return value if specified
            if default_return is not None:
                # Special case for head_registry_key which returns a mutable dict
                if func_name == 'head_registry_key':
                    mock_func.return_value = default_return.copy() # Return a copy
                else:
                    mock_func.return_value = default_return
            mocks[func_name] = mock_func
            patchers.append(patcher)
        yield mocks # Yield the dictionary of mocks
    finally:
        for patcher in patchers:
            patcher.stop()

@pytest.fixture
def patched_registry_translation_funcs():
    """Mocks the functions imported from registry_translation into registry_interface."""
    # Define the functions imported and used by RegistryRoot methods
    functions_to_patch = {
        '_normalize_registry_type_input': lambda x: x, # Default: return input
        '_infer_registry_type_for_new_value': lambda data: (data, winreg.REG_SZ), # Default: REG_SZ
        '_validate_and_convert_data_for_type': lambda data, type: data, # Default: return data
    }
    mocks = {}
    patchers = []
    try:
        for func_name, default_side_effect in functions_to_patch.items():
            # Patch the function name where it's looked up (in registry_interface)
            target = f'winregenv.registry_interface.{func_name}'
            patcher = patch(target, autospec=True)
            mock_func = patcher.start()
            mock_func.side_effect = default_side_effect # Set default side_effect
            mocks[func_name] = mock_func
            patchers.append(patcher)
        yield mocks # Yield the dictionary of mocks
    finally:
        for patcher in patchers:
            patcher.stop()


@pytest.fixture(autouse=True) # autouse=True applies this patch to all tests in this directory
def mock_elevation_check():
    """Mocks the elevation_check module."""
    # Patch the is_elevated function specifically
    with patch('winregenv.registry_interface.is_elevated') as mock_is_elevated:
        # Default is_elevated to True, override in specific tests
        mock_is_elevated.return_value = True
        yield mock_is_elevated

