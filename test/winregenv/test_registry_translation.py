import pytest
import winreg # Import for constants
import logging # Import the logging module

# Import the internal module under test
from winregenv import registry_translation as rt

# --- Tests for get_reg_type_name ---

@pytest.mark.parametrize("reg_type, expected_name", [
    (rt.REG_SZ, "REG_SZ"),
    (rt.REG_EXPAND_SZ, "REG_EXPAND_SZ"),
    (rt.REG_BINARY, "REG_BINARY"),
    (rt.REG_DWORD, "REG_DWORD"),
    (rt.REG_DWORD_BIG_ENDIAN, "REG_DWORD_BIG_ENDIAN"),
    (rt.REG_LINK, "REG_LINK"),
    (rt.REG_MULTI_SZ, "REG_MULTI_SZ"),
    (rt.REG_QWORD, "REG_QWORD"),
    (rt.REG_NONE, "REG_NONE"),
    (rt.REG_RESOURCE_LIST, "REG_RESOURCE_LIST"),
    (rt.REG_FULL_RESOURCE_DESCRIPTOR, "REG_FULL_RESOURCE_DESCRIPTOR"),
    (rt.REG_RESOURCE_REQUIREMENTS_LIST, "REG_RESOURCE_REQUIREMENTS_LIST"),
    (999, "UnknownType(999)"), # Test unknown type
])
def test_get_reg_type_name(reg_type, expected_name):
    """Tests that get_reg_type_name returns the correct string representation."""
    assert rt.get_reg_type_name(reg_type) == expected_name

# --- Tests for _normalize_registry_type_input ---

@pytest.mark.parametrize("type_input, expected_output", [
    (rt.REG_SZ, rt.REG_SZ),
    (rt.REG_DWORD, rt.REG_DWORD),
    (rt.REG_QWORD, rt.REG_QWORD),
    ("REG_SZ", rt.REG_SZ),
    ("reg_sz", rt.REG_SZ), # Case-insensitive string
    ("REG_EXPAND_SZ", rt.REG_EXPAND_SZ),
    ("REG_BINARY", rt.REG_BINARY),
    ("REG_DWORD", rt.REG_DWORD),
    ("REG_MULTI_SZ", rt.REG_MULTI_SZ),
    ("REG_QWORD", rt.REG_QWORD),
    ("REG_NONE", rt.REG_NONE),
])
def test_normalize_registry_type_input_valid(type_input, expected_output):
    """Tests valid integer and string inputs for normalization."""
    assert rt.normalize_registry_type(type_input) == expected_output

@pytest.mark.parametrize("invalid_input, expected_exception, match_pattern", [
    (999, ValueError, "Input integer 999 does not correspond to a known"),
    ("REG_INVALID", ValueError, "Input string 'REG_INVALID' is not a recognized"),
    (None, TypeError, "Registry type input must be an integer or a string name"),
    (1.0, TypeError, "Registry type input must be an integer or a string name"),
    ([], TypeError, "Registry type input must be an integer or a string name"),
])
def test_normalize_registry_type_input_invalid(invalid_input, expected_exception, match_pattern):
    """Tests invalid inputs that should raise exceptions."""
    with pytest.raises(expected_exception, match=match_pattern): # Corrected function name
        rt.normalize_registry_type(invalid_input)

# --- Tests for _infer_registry_type_for_new_value ---

@pytest.mark.parametrize("data, expected_data, expected_type", [
    ("test string", "test string", rt.REG_SZ),
    (12345, 12345, rt.REG_DWORD),
    (0, 0, rt.REG_DWORD),
    (2**32 - 1, 2**32 - 1, rt.REG_DWORD), # Max unsigned 32-bit
    (-2**31, -2**31, rt.REG_DWORD),      # Min signed 32-bit
    (b'\x01\x02\x03', b'\x01\x02\x03', rt.REG_BINARY),
    (["a", "b", "c"], ["a", "b", "c"], rt.REG_MULTI_SZ),
    ([], [], rt.REG_MULTI_SZ), # Empty list is valid MULTI_SZ
])
def test_infer_registry_type_success(data, expected_data, expected_type):
    """Tests successful inference of registry types from Python data."""
    inferred_data, inferred_type = rt._infer_registry_type_for_new_value(data)
    assert inferred_data == expected_data
    assert inferred_type == expected_type

@pytest.mark.parametrize("invalid_data, expected_exception, match_pattern", [
    (2**32, ValueError, "Integer data .* is outside the range for default REG_DWORD"), # Too large for DWORD
    (-2**31 - 1, ValueError, "Integer data .* is outside the range for default REG_DWORD"), # Too small for DWORD
    ([1, 2, 3], TypeError, "Cannot infer registry type for list data containing non-string elements"),
    ({"a": 1}, TypeError, "Cannot infer registry type for Python data type: <class 'dict'>"),
    (None, TypeError, "Cannot infer registry type for Python data type: <class 'NoneType'>"),
    (1.5, TypeError, "Cannot infer registry type for Python data type: <class 'float'>"),
])
def test_infer_registry_type_failure(invalid_data, expected_exception, match_pattern):
    """Tests data types that cannot be automatically inferred or are invalid."""
    with pytest.raises(expected_exception, match=match_pattern):
        rt._infer_registry_type_for_new_value(invalid_data)

# --- Tests for _validate_and_convert_data_for_type ---

@pytest.mark.parametrize("data, target_type, expected_output", [
    # String types
    ("hello", rt.REG_SZ, "hello"),
    ("world", rt.REG_EXPAND_SZ, "world"),
    ("link_target", rt.REG_LINK, "link_target"),
    # DWORD types
    (100, rt.REG_DWORD, 100),
    (0, rt.REG_DWORD_LITTLE_ENDIAN, 0),
    (2**32 - 1, rt.REG_DWORD_BIG_ENDIAN, 2**32 - 1),
    (-2**31, rt.REG_DWORD, -2**31),
    # QWORD types
    (2**32, rt.REG_QWORD, 2**32), # Value too big for DWORD, okay for QWORD
    (2**64 - 1, rt.REG_QWORD_LITTLE_ENDIAN, 2**64 - 1),
    (-2**63, rt.REG_QWORD, -2**63),
    (0, rt.REG_QWORD, 0),
    # Binary type
    (b'\xde\xad\xbe\xef', rt.REG_BINARY, b'\xde\xad\xbe\xef'),
    (b'', rt.REG_BINARY, b''),
    # Multi-String type
    (["one", "two", "three"], rt.REG_MULTI_SZ, ["one", "two", "three"]),
    ([], rt.REG_MULTI_SZ, []),
    # None type
    (None, rt.REG_NONE, None),
    (b'', rt.REG_NONE, None), # Also accept b'' for REG_NONE
    ("ignored", rt.REG_NONE, None), # Data is ignored, should return None
    (123, rt.REG_NONE, None), # Data is ignored, should return None
    # Resource types (expect bytes)
    (b'\x01\x00\x00\x00', rt.REG_RESOURCE_LIST, b'\x01\x00\x00\x00'),
    (b'\x02\x00', rt.REG_FULL_RESOURCE_DESCRIPTOR, b'\x02\x00'),
    (b'\x03', rt.REG_RESOURCE_REQUIREMENTS_LIST, b'\x03'),
])
def test_validate_and_convert_data_success(data, target_type, expected_output):
    """Tests successful validation and conversion for various types."""
    # Use caplog to check for warnings with REG_NONE
    result = rt._validate_and_convert_data_for_type(data, target_type)
    assert result == expected_output


@pytest.mark.parametrize("data, target_type, expected_exception, match_pattern", [
    # Type mismatches
    (123, rt.REG_SZ, TypeError, "Data must be a string for registry type REG_SZ"),
    ("abc", rt.REG_DWORD, TypeError, "Data must be an integer for registry type REG_DWORD"),
    (123, rt.REG_BINARY, TypeError, "Data must be bytes for registry type REG_BINARY"),
    (b"abc", rt.REG_MULTI_SZ, TypeError, "Data must be a list of strings for registry type REG_MULTI_SZ"),
    ([1, 2], rt.REG_MULTI_SZ, TypeError, "Data must be a list of strings for registry type REG_MULTI_SZ"),
    ("abc", rt.REG_RESOURCE_LIST, TypeError, "Data must be bytes for registry type REG_RESOURCE_LIST"),
    # Value range errors
    (2**32, rt.REG_DWORD, ValueError, "Integer data .* is out of range for a 32-bit registry type"),
    (-2**31 - 1, rt.REG_DWORD_BIG_ENDIAN, ValueError, "Integer data .* is out of range for a 32-bit registry type"),
    (2**64, rt.REG_QWORD, ValueError, "Integer data .* is out of range for a 64-bit registry type"),
    (-2**63 - 1, rt.REG_QWORD_LITTLE_ENDIAN, ValueError, "Integer data .* is out of range for a 64-bit registry type"),
    # Unsupported target type
    ("abc", 999, TypeError, "Unsupported or unhandled target registry type: UnknownType\\(999\\)"),
])
def test_validate_and_convert_data_failure(data, target_type, expected_exception, match_pattern):
    """Tests validation failures due to type mismatch or value range errors."""
    with pytest.raises(expected_exception, match=match_pattern):
        rt._validate_and_convert_data_for_type(data, target_type)

def test_validate_and_convert_data_reg_none_warning(caplog):
    """Tests that a warning is logged when data is provided for REG_NONE."""
    with caplog.at_level(logging.WARNING):
        result = rt._validate_and_convert_data_for_type("some data", rt.REG_NONE)
    assert result is None # Should still return None
    assert len(caplog.records) == 1
    assert "Data 'some data' provided for REG_NONE type" in caplog.text
    assert "Data will be ignored by the registry" in caplog.text

    # Test with bytes data too
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result = rt._validate_and_convert_data_for_type(b"bytes data", rt.REG_NONE)
    assert result is None
    assert len(caplog.records) == 1
    assert "Data b'bytes data' provided for REG_NONE type" in caplog.text

    # Test with None or b'', should not warn
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result_none = rt._validate_and_convert_data_for_type(None, rt.REG_NONE)
        result_bytes = rt._validate_and_convert_data_for_type(b'', rt.REG_NONE)
    assert result_none is None
    assert result_bytes is None
    assert len(caplog.records) == 0 # No warnings expected
