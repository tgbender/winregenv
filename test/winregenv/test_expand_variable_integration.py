# test/winregenv/test_expand_variable_integration.py

import pytest
import sys
import os

# Import the function under test
from winregenv.expand_variable import expand_environment_strings

# Skip tests if not on Windows
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows API")

# Helper to get expected expanded string using os.environ
# Note: os.path.expandvars handles %VAR% and $VAR (on non-Windows),
# the Windows API only handles %VAR%. We'll rely on os.path.expandvars
# and assume it behaves like the Windows API for %VAR% on Windows.
# This helper is primarily for generating expected results in a platform-agnostic way
# for the test definition, but the test itself calls the Windows-specific function.
def _get_expected_expansion(input_string):
    """Simulates expected expansion using os.environ."""
    return os.path.expandvars(input_string)


@pytest.mark.parametrize("input_string", [
    # Standard variables
    "%TEMP%",
    "%USERNAME%",
    "%SystemRoot%",
    # Multiple variables
    "%SystemRoot%\\System32\\%USERNAME%",
    # Non-existent variables
    "Path to %NON_EXISTENT_VAR%",
    # Mixed content
    "User: %USERNAME%, Temp: %TEMP%",
    # Edge cases
    "",
    "%",  # Should remain unexpanded
    "%%", # Should remain unexpanded
    "abc%", # Should remain unexpanded
    "%VAR", # Should remain unexpanded
    "VAR%", # Should remain unexpanded
    # Long string to test buffer resizing (adjust length as needed, 1500 is > typical initial buffer)
    "%SystemRoot%\\" + "a"*1500 + "\\%TEMP%",
])
def test_expand_environment_strings_success(input_string):
    """Tests successful expansion of various strings."""
    # Calculate the expected output using os.path.expandvars
    expected_output = _get_expected_expansion(input_string)

    # Special case override for "%%" based on observed Windows API behavior
    if input_string == "%%":
        expected_output = "%%" # The Windows API ExpandEnvironmentStrings does not collapse "%%" to "%"
    # Call the function under test which uses the Windows API
    actual_output = expand_environment_strings(input_string)
    assert actual_output == expected_output

@pytest.mark.parametrize("invalid_input", [
    None,
    123,
    b"bytes",
    ["list"],
    {"dict": 1},
])
def test_expand_environment_strings_invalid_input(invalid_input):
    """Tests that non-string inputs raise TypeError."""
    with pytest.raises(TypeError, match="source_string must be a string"):
        expand_environment_strings(invalid_input)

