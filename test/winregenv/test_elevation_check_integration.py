# -*- coding: utf-8 -*-
"""
Integration tests for the elevation_check module.

These tests run the actual Windows API calls to verify basic functionality
and return types, without mocking ctypes.
"""

import pytest
import sys

# --- Platform Skip ---
# Skip all tests in this module if not on Windows
if sys.platform != "win32":
    pytest.skip("Skipping elevation_check integration tests on non-Windows platforms", allow_module_level=True)
else:
    # Import the module under test only if on Windows
    # This import should now get the module using the *real* ctypes
    # because the mocking fixture in test_elevation_check.py cleans up.
    from winregenv import elevation_check

# --- Test Cases ---

def test_elevation_check_integration_basic():
    """
    Tests that get_integrity_level and is_elevated run without error
    and return values of the expected types.

    This test does NOT assert a specific integrity level or elevation status,
    as that depends on how the test runner is invoked (standard user vs. admin).
    It verifies that the underlying Windows API calls can be made successfully
    and the functions process the results into the expected Python types.
    """
    print("\n--- Running Elevation Check Integration Test ---") # Add some output for clarity

    # Test get_integrity_level
    try:
        integrity_level = elevation_check.get_integrity_level()
        print(f"get_integrity_level returned: {integrity_level} (type: {type(integrity_level).__name__})")
        assert isinstance(integrity_level, int)
        # Optionally, check if it's within a reasonable range of known RIDs
        # This is a soft check, not a strict assertion of a specific level
        # Check if it's one of the known RIDs or at least non-negative
        assert integrity_level >= elevation_check.SECURITY_MANDATORY_UNTRUSTED_RID

    except Exception as e:
        # Use pytest.fail to indicate a test failure with a clear message
        pytest.fail(f"get_integrity_level raised an unexpected exception: {e}")

    # Test is_elevated
    try:
        elevated_status = elevation_check.is_elevated()
        print(f"is_elevated returned: {elevated_status} (type: {type(elevated_status).__name__})")
        assert isinstance(elevated_status, bool)

    except Exception as e:
         pytest.fail(f"is_elevated raised an unexpected exception: {e}")

    print("--- Elevation Check Integration Test Passed ---")

# You could add more integration tests here if there were other scenarios
# to test without mocking, but for this simple module, one basic test
# covering both functions is likely sufficient.
