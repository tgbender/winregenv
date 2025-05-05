import pytest
from unittest.mock import patch, MagicMock
import winreg # For registry type constants
import re # Import the regex module for escaping
import re # Import the regex module for escaping
from winregenv.registry_errors import RegistryExpansionError # Import the specific error

# Assuming registry_types is in src.winregenv
# Corrected imports: removed 'src.' prefix
from winregenv.registry_types import RegistryValue
from winregenv.registry_translation import REG_EXPAND_SZ, REG_SZ, REG_DWORD, REG_BINARY, REG_MULTI_SZ

# --- Test Data ---
TEST_NAME = "TestValue"
TEST_DATA_SZ = "Some String Data"
TEST_DATA_DWORD = 12345
TEST_DATA_BINARY = b'\x01\x02\x03\x04'
TEST_DATA_MULTI_SZ = ["line1", "line2"]
TEST_DATA_EXPAND_SZ = "%SystemRoot%\\System32"
EXPANDED_DATA = "C:\\Windows\\System32" # Example expansion

# --- Fixtures ---

@pytest.fixture
def reg_value_sz():
    """Fixture for a REG_SZ RegistryValue."""
    return RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)

@pytest.fixture
def reg_value_dword():
    """Fixture for a REG_DWORD RegistryValue."""
    return RegistryValue(TEST_NAME, TEST_DATA_DWORD, REG_DWORD)

@pytest.fixture
def reg_value_binary():
    """Fixture for a REG_BINARY RegistryValue."""
    return RegistryValue(TEST_NAME, TEST_DATA_BINARY, REG_BINARY)

@pytest.fixture
def reg_value_multi_sz():
    """Fixture for a REG_MULTI_SZ RegistryValue."""
    return RegistryValue(TEST_NAME, TEST_DATA_MULTI_SZ, REG_MULTI_SZ)

@pytest.fixture
def reg_value_expand_sz():
    """Fixture for a REG_EXPAND_SZ RegistryValue."""
    return RegistryValue(TEST_NAME, TEST_DATA_EXPAND_SZ, REG_EXPAND_SZ)

@pytest.fixture
def reg_value_default():
    """Fixture for a default value (empty name)."""
    return RegistryValue("", TEST_DATA_SZ, REG_SZ)


# --- Test Cases ---

def test_initialization(reg_value_sz):
    """Test basic initialization and attribute storage."""
    assert reg_value_sz._name == TEST_NAME
    assert reg_value_sz._data == TEST_DATA_SZ
    assert reg_value_sz._value_type == REG_SZ

def test_properties(reg_value_dword):
    """Test the name, data, and type properties."""
    assert reg_value_dword.name == TEST_NAME
    assert reg_value_dword.data == TEST_DATA_DWORD
    assert reg_value_dword.type == REG_DWORD

def test_default_value_name(reg_value_default):
    """Test initialization with an empty name for the default value."""
    assert reg_value_default.name == ""
    assert reg_value_default.data == TEST_DATA_SZ
    assert reg_value_default.type == REG_SZ

# --- Test expanded_data ---

# Corrected patch target: removed 'src.' prefix
@patch('winregenv.registry_types.expand_environment_strings', return_value=EXPANDED_DATA)
def test_expanded_data_success(mock_expand, reg_value_expand_sz):
    """Test expanded_data property for REG_EXPAND_SZ type."""
    assert reg_value_expand_sz.expanded_data == EXPANDED_DATA
    mock_expand.assert_called_once_with(TEST_DATA_EXPAND_SZ)

# Corrected patch target: removed 'src.' prefix
@patch('winregenv.registry_types.expand_environment_strings')
def test_expanded_data_non_expand_sz(mock_expand, reg_value_sz):
    """Test expanded_data returns None for non-REG_EXPAND_SZ types."""
    assert reg_value_sz.expanded_data is None
    mock_expand.assert_not_called()

# Corrected patch target: removed 'src.' prefix
@patch('winregenv.registry_types.expand_environment_strings')
def test_expanded_data_non_string_data(mock_expand):
    """Test expanded_data returns None if data is not a string (edge case)."""
    # This shouldn't typically happen if type validation is done elsewhere,
    # but we test the property's robustness.
    value = RegistryValue("NonStringExpand", 123, REG_EXPAND_SZ)
    assert value.expanded_data is None
    mock_expand.assert_not_called()

# Corrected patch target: removed 'src.' prefix
@patch('winregenv.registry_types.expand_environment_strings', side_effect=OSError("Expansion failed"))
def test_expanded_data_expansion_error(mock_expand, reg_value_expand_sz, caplog): # Removed caplog as we now expect an exception
    """Test expanded_data handles errors during expansion and raises RegistryExpansionError."""
    import logging
    caplog.set_level(logging.ERROR) # Set level to ERROR as the code now logs an error

    # Accessing the property should now raise RegistryExpansionError
    # Construct the expected error message string exactly as the code does,
    # then escape the *entire* resulting string for regex matching.
    expected_error_message = f"Failed to expand REG_EXPAND_SZ value '{TEST_NAME}' data {TEST_DATA_EXPAND_SZ!r}"
    expected_match_pattern = re.escape(expected_error_message)

    with pytest.raises(RegistryExpansionError, match=expected_match_pattern):
        _ = reg_value_expand_sz.expanded_data
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR" # Check for ERROR level
    assert f"Failed to expand REG_EXPAND_SZ value '{TEST_NAME}'" in caplog.text
    assert f"{TEST_DATA_EXPAND_SZ!r}" in caplog.text
    assert "Expansion failed" in caplog.text # Check exception info is logged

# --- Test Iteration and Indexing ---

def test_iteration(reg_value_binary):
    """Test iterating over the RegistryValue object."""
    name, data, value_type = reg_value_binary
    assert name == TEST_NAME
    assert data == TEST_DATA_BINARY
    assert value_type == REG_BINARY

def test_indexing(reg_value_multi_sz):
    """Test accessing elements by index."""
    assert reg_value_multi_sz[0] == TEST_NAME
    assert reg_value_multi_sz[1] == tuple(TEST_DATA_MULTI_SZ) # Expect tuple as data is stored internally as tuple
    assert reg_value_multi_sz[2] == REG_MULTI_SZ

def test_indexing_out_of_range(reg_value_sz):
    """Test IndexError for invalid index."""
    with pytest.raises(IndexError, match="RegistryValue index out of range"):
        _ = reg_value_sz[3]
    with pytest.raises(IndexError, match="RegistryValue index out of range"):
        _ = reg_value_sz[-1] # Negative indices are not supported

# --- Test Representations ---

def test_repr(reg_value_sz):
    """Test the __repr__ output."""
    expected_repr = f"RegistryValue(name={TEST_NAME!r}, data={TEST_DATA_SZ!r}, value_type={REG_SZ!r})"
    assert repr(reg_value_sz) == expected_repr

def test_str(reg_value_dword):
    """Test the __str__ output."""
    expected_str = f"'{TEST_NAME}': {TEST_DATA_DWORD} (Type: {REG_DWORD})"
    assert str(reg_value_dword) == expected_str

# --- Test Equality ---

def test_equality_same_object(reg_value_sz):
    """Test equality with itself."""
    assert reg_value_sz == reg_value_sz

def test_equality_identical_values():
    """Test equality between two RegistryValue objects with identical contents."""
    val1 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    val2 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    assert val1 == val2
    assert not (val1 != val2)

def test_inequality_different_name():
    """Test inequality when names differ."""
    val1 = RegistryValue("Name1", TEST_DATA_SZ, REG_SZ)
    val2 = RegistryValue("Name2", TEST_DATA_SZ, REG_SZ)
    assert val1 != val2
    assert not (val1 == val2)

def test_inequality_different_data():
    """Test inequality when data differs."""
    val1 = RegistryValue(TEST_NAME, "Data1", REG_SZ)
    val2 = RegistryValue(TEST_NAME, "Data2", REG_SZ)
    assert val1 != val2
    assert not (val1 == val2)

def test_inequality_different_type():
    """Test inequality when types differ."""
    val1 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    val2 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_EXPAND_SZ)
    assert val1 != val2
    assert not (val1 == val2)

def test_equality_with_tuple(reg_value_binary):
    """Test equality comparison with a tuple (name, data, type)."""
    tuple_equiv = (TEST_NAME, TEST_DATA_BINARY, REG_BINARY)
    assert reg_value_binary == tuple_equiv
    assert not (reg_value_binary != tuple_equiv)

def test_inequality_with_tuple(reg_value_dword):
    """Test inequality comparison with a different tuple."""
    tuple_diff = (TEST_NAME, 99999, REG_DWORD) # Different data
    tuple_diff_type = (TEST_NAME, TEST_DATA_DWORD, REG_SZ) # Different type
    tuple_diff_name = ("OtherName", TEST_DATA_DWORD, REG_DWORD) # Different name
    tuple_wrong_len = (TEST_NAME, TEST_DATA_DWORD) # Wrong length

    assert reg_value_dword != tuple_diff
    assert reg_value_dword != tuple_diff_type
    assert reg_value_dword != tuple_diff_name
    assert reg_value_dword != tuple_wrong_len
    assert not (reg_value_dword == tuple_diff)
    assert not (reg_value_dword == tuple_diff_type)
    assert not (reg_value_dword == tuple_diff_name)
    assert not (reg_value_dword == tuple_wrong_len)


def test_equality_with_other_type(reg_value_sz):
    """Test equality comparison with an unrelated type."""
    assert reg_value_sz != 123
    assert reg_value_sz != "some string"
    assert reg_value_sz != None
    assert not (reg_value_sz == 123)
    assert not (reg_value_sz == "some string")
    assert not (reg_value_sz == None)

# --- Test Hashing ---

def test_hashing_identical_objects():
    """Test that identical objects produce the same hash."""
    val1 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    val2 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    assert hash(val1) == hash(val2)

def test_hashing_different_objects():
    """Test that different objects likely produce different hashes."""
    val1 = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    val2 = RegistryValue(TEST_NAME, TEST_DATA_DWORD, REG_DWORD)
    val3 = RegistryValue("OtherName", TEST_DATA_SZ, REG_SZ)
    # Note: Hash collisions are possible, but unlikely with these simple changes
    assert hash(val1) != hash(val2)
    assert hash(val1) != hash(val3)
    assert hash(val2) != hash(val3)

def test_hashing_in_set(reg_value_sz, reg_value_dword, reg_value_binary):
    """Test using RegistryValue objects in a set."""
    val_sz_copy = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)
    value_set = {reg_value_sz, reg_value_dword, reg_value_binary, val_sz_copy}

    # The set should contain 3 unique items because reg_value_sz and val_sz_copy are equal
    assert len(value_set) == 3
    assert reg_value_sz in value_set
    assert reg_value_dword in value_set
    assert reg_value_binary in value_set
    assert val_sz_copy in value_set # Should be considered the same as reg_value_sz

def test_hashing_as_dict_key(reg_value_sz, reg_value_dword):
    """Test using RegistryValue objects as dictionary keys."""
    value_dict = {
        reg_value_sz: "This is SZ",
        reg_value_dword: "This is DWORD"
    }
    val_sz_copy = RegistryValue(TEST_NAME, TEST_DATA_SZ, REG_SZ)

    assert len(value_dict) == 2
    assert value_dict[reg_value_sz] == "This is SZ"
    assert value_dict[reg_value_dword] == "This is DWORD"
    # Access using an equivalent object
    assert value_dict[val_sz_copy] == "This is SZ"

def test_hashing_multi_sz_data(reg_value_multi_sz):
    """Test that hashing works for RegistryValue with REG_MULTI_SZ data (stored as tuple)."""
    # The internal data for REG_MULTI_SZ is now a tuple, which is hashable.
    # This test verifies that hashing succeeds and the object can be used in hash-based collections.

    # Verify hashing does not raise an error
    try:
        h = hash(reg_value_multi_sz)
        assert isinstance(h, int) # Check that a hash value was returned
    except TypeError:
        pytest.fail("Hashing RegistryValue with REG_MULTI_SZ data raised TypeError unexpectedly.")

    # Verify it can be added to a set
    value_set = {reg_value_multi_sz}
    assert reg_value_multi_sz in value_set

    # Verify it can be used as a dict key
    value_dict = {reg_value_multi_sz: "multi_sz_value"}
    assert reg_value_multi_sz in value_dict
    assert value_dict[reg_value_multi_sz] == "multi_sz_value"

    # Test with an identical object
    val_multi_sz_copy = RegistryValue(TEST_NAME, TEST_DATA_MULTI_SZ, REG_MULTI_SZ)
    assert hash(reg_value_multi_sz) == hash(val_multi_sz_copy)
    assert val_multi_sz_copy in value_set # Should be considered the same in the set
    assert value_dict[val_multi_sz_copy] == "multi_sz_value" # Should be considered the same key
