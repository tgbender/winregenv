"""
Internal module for handling translation between Python data types
and Windows Registry value types (REG_* constants).

This module is intended for internal use within the winregenv package
and does not expose any public API.
"""

import winreg
from typing import Any, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

# --- Internal winreg REG_* constants ---
# These are imported from the standard winreg module and re-exported
# within this internal module for use by other modules in the package.
# They are NOT intended for public use outside this package.
# We use the full names for clarity within this module.
REG_NONE = winreg.REG_NONE
REG_SZ = winreg.REG_SZ
REG_EXPAND_SZ = winreg.REG_EXPAND_SZ
REG_BINARY = winreg.REG_BINARY
REG_DWORD = winreg.REG_DWORD
REG_DWORD_LITTLE_ENDIAN = winreg.REG_DWORD_LITTLE_ENDIAN # Note: Same value as REG_DWORD
REG_DWORD_BIG_ENDIAN = winreg.REG_DWORD_BIG_ENDIAN
REG_LINK = winreg.REG_LINK # Symbolic link target string
REG_MULTI_SZ = winreg.REG_MULTI_SZ # List of strings
REG_RESOURCE_LIST = winreg.REG_RESOURCE_LIST # Hardware resource list
REG_FULL_RESOURCE_DESCRIPTOR = winreg.REG_FULL_RESOURCE_DESCRIPTOR # Hardware resource descriptor
REG_RESOURCE_REQUIREMENTS_LIST = winreg.REG_RESOURCE_REQUIREMENTS_LIST # Hardware resource requirements
REG_QWORD = winreg.REG_QWORD
REG_QWORD_LITTLE_ENDIAN = winreg.REG_QWORD_LITTLE_ENDIAN # Note: Same value as REG_QWORD


# Optional: Create a reverse mapping for display/logging purposes
# IMPORTANT: Since REG_DWORD == REG_DWORD_LITTLE_ENDIAN and REG_QWORD == REG_QWORD_LITTLE_ENDIAN,
# we only include the base names here to ensure consistent name lookup and reverse lookup.
_REG_TYPE_NAMES = {
    REG_NONE: "REG_NONE",
    REG_SZ: "REG_SZ",
    REG_EXPAND_SZ: "REG_EXPAND_SZ",
    REG_BINARY: "REG_BINARY",
    REG_DWORD: "REG_DWORD", # Use base name for value 4
    # REG_DWORD_LITTLE_ENDIAN: "REG_DWORD_LITTLE_ENDIAN", # Excluded due to same value as REG_DWORD
    REG_DWORD_BIG_ENDIAN: "REG_DWORD_BIG_ENDIAN",
    REG_LINK: "REG_LINK",
    REG_MULTI_SZ: "REG_MULTI_SZ",
    REG_RESOURCE_LIST: "REG_RESOURCE_LIST",
    REG_FULL_RESOURCE_DESCRIPTOR: "REG_FULL_RESOURCE_DESCRIPTOR",
    REG_RESOURCE_REQUIREMENTS_LIST: "REG_RESOURCE_REQUIREMENTS_LIST",
    REG_QWORD: "REG_QWORD", # Use base name for value 11
    # REG_QWORD_LITTLE_ENDIAN: "REG_QWORD_LITTLE_ENDIAN", # Excluded due to same value as REG_QWORD
}

def get_reg_type_name(reg_type: int) -> str:
    """Helper to get the string name for a registry type integer."""
    return _REG_TYPE_NAMES.get(reg_type, f"UnknownType({reg_type})")

# Create a reverse mapping for string name to integer type lookup
# This will now correctly map "REG_DWORD" -> 4 and "REG_QWORD" -> 11
_REG_NAME_TO_TYPE = {name: value for value, name in _REG_TYPE_NAMES.items()}

def _normalize_registry_type_input(type_input: int | str) -> int:
    """
    Normalizes a registry type input (int, string name) to its integer value.

    Args:
        type_input (int | str): The registry type specified by the user.
                                 Can be an integer REG_* constant, a string
                                 name (e.g., "REG_SZ"), or a winreg.REG_* object.

    Returns:
        int: The integer value of the registry type.

    Raises:
        TypeError: If the input is not an int or a string.
        ValueError: If the input integer is not a known REG_* type or the
                    string name is not recognized.
    """
    logger.debug("Normalizing registry value type input: %r (type: %s)", type_input, type(type_input))

    if isinstance(type_input, int):
        # Check if the integer corresponds to a known type in our map
        if type_input in _REG_TYPE_NAMES:
            logger.debug("Input is a known integer type: %s", get_reg_type_name(type_input))
            return type_input
        # Handle known types that might have been excluded from _REG_TYPE_NAMES (like LITTLE_ENDIAN)
        elif type_input == REG_DWORD_LITTLE_ENDIAN:
             logger.debug("Input integer %d matches REG_DWORD_LITTLE_ENDIAN, normalizing to REG_DWORD (%d)", type_input, REG_DWORD)
             return REG_DWORD # Normalize to the base type value
        elif type_input == REG_QWORD_LITTLE_ENDIAN:
             logger.debug("Input integer %d matches REG_QWORD_LITTLE_ENDIAN, normalizing to REG_QWORD (%d)", type_input, REG_QWORD)
             return REG_QWORD # Normalize to the base type value
        else:
            # Check against all known winreg constants just in case
            all_known_types = {v for k, v in winreg.__dict__.items() if k.startswith("REG_")}
            if type_input in all_known_types:
                 logger.warning("Input integer %d is a known winreg type but not explicitly handled in _REG_TYPE_NAMES. Returning as is.", type_input)
                 return type_input # Return it if it's valid, though name lookup might fail later
            else:
                 raise ValueError(
                     f"Input integer {type_input} does not correspond to a known "
                     f"Windows registry type (REG_*)."
                 )
    elif isinstance(type_input, str):
        # Look up the string name (case-insensitive lookup, but store uppercase)
        upper_name = type_input.upper()
        if upper_name in _REG_NAME_TO_TYPE:
            reg_type = _REG_NAME_TO_TYPE[upper_name]
            logger.debug("Input string '%s' normalized to integer type: %s", type_input, get_reg_type_name(reg_type))
            return reg_type # Return the integer value
        # Handle LITTLE_ENDIAN string names explicitly if needed, mapping them to base types
        elif upper_name == "REG_DWORD_LITTLE_ENDIAN":
             logger.debug("Input string 'REG_DWORD_LITTLE_ENDIAN' normalized to integer type REG_DWORD (%d)", REG_DWORD)
             return REG_DWORD
        elif upper_name == "REG_QWORD_LITTLE_ENDIAN":
             logger.debug("Input string 'REG_QWORD_LITTLE_ENDIAN' normalized to integer type REG_QWORD (%d)", REG_QWORD)
             return REG_QWORD
        else:
            raise ValueError(
                f"Input string '{type_input}' is not a recognized Windows "
                f"registry type name (e.g., 'REG_SZ', 'REG_DWORD')."
            )
    else:
        raise TypeError(
            f"Registry type input must be an integer or a string name, "
            f"but got type {type(type_input)}."
        )

# Rename the function to the public name
normalize_registry_type = _normalize_registry_type_input

# _infer_registry_type_for_new_value remains internal

def _infer_registry_type_for_new_value(data: Any) -> Tuple[Any, int]:
    """
    Infers the default registry type for new data based on its Python type.

    This function is used when creating a *new* registry value and the user
    has not specified a registry type. It provides sensible defaults.

    Args:
        data: The Python data.

    Returns:
        Tuple[Any, int]: The data (potentially converted if needed for the
                         inferred type, though winreg handles most) and the
                         inferred registry type (REG_* constant).

    Raises:
        TypeError: If the Python data type cannot be mapped to a default
                   registry type.
        ValueError: If the data is out of range for the inferred type
                    (e.g., int too large for DWORD).
    """
    logger.debug("Attempting to infer registry type for data: %r (type: %s)", data, type(data))

    if isinstance(data, str):
        # Default string type for new values is REG_SZ.
        # The decision to use REG_EXPAND_SZ is domain-specific (e.g., environment vars)
        # and should be handled by higher-level logic if needed.
        inferred_type = REG_SZ
        logger.debug("Inferred type REG_SZ for string data.")
        return data, inferred_type

    elif isinstance(data, int):
        # Default integer type for new values is REG_DWORD.
        # Check if it fits in 32 bits. If not, raise an error suggesting QWORD.
        # winreg handles the conversion from Python int to the correct byte representation.
        if not (-2**31 <= data <= 2**32 - 1):
             # Integer is too large for REG_DWORD. User must explicitly specify REG_QWORD.
             raise ValueError(
                 f"Integer data {data} is outside the range for default REG_DWORD "
                 f"(-2^31 to 2^32-1). Specify value_type={get_reg_type_name(REG_QWORD)} if a 64-bit "
                 f"integer is intended."
             )
        inferred_type = REG_DWORD
        logger.debug("Inferred type REG_DWORD for integer data.")
        return data, inferred_type

    elif isinstance(data, bytes):
        inferred_type = REG_BINARY
        logger.debug("Inferred type REG_BINARY for bytes data.")
        return data, inferred_type

    elif isinstance(data, list):
         # Check if it's a list of strings for REG_MULTI_SZ
         if all(isinstance(item, str) for item in data):
              inferred_type = REG_MULTI_SZ
              logger.debug("Inferred type REG_MULTI_SZ for list of strings.")
              # winreg.SetValueEx expects a list of strings for REG_MULTI_SZ
              return data, inferred_type
         else:
              # List contains non-string elements
              raise TypeError(
                  f"Cannot infer registry type for list data containing non-string elements: {data}. "
                  f"Only List[str] is automatically inferred (as REG_MULTI_SZ). Please specify value_type."
              )

    # Add inference for other common types if needed (e.g., float -> REG_BINARY?)
    # For unknown or unhandled Python types, raise an error
    else:
        raise TypeError(
            f"Cannot infer registry type for Python data type: {type(data)}. "
            f"Please specify value_type using a winregenv.REG_* constant."
        )


# _validate_and_convert_data_for_type remains internal

def _validate_and_convert_data_for_type(data: Any, target_type: int) -> Any:
    """
    Validates if Python data is compatible with a specific registry type
    and performs necessary conversions (if any) before writing.

    This function is used when the registry type is known (either specified
    by the user or determined from an existing value).

    Args:
        data: The Python data to write.
        target_type: The target registry type (REG_* constant).

    Returns:
        Any: The data, potentially converted to be compatible with the
             registry type as expected by winreg.SetValueEx.

    Raises:
        TypeError: If data is incompatible with the target_type.
        ValueError: If data is out of range for integer types.
    """
    logger.debug("Validating data %r (type: %s) against target registry type: %s",
                 data, type(data), get_reg_type_name(target_type))

    # winreg.SetValueEx expects specific Python types for specific REG_* types.
    # We validate the Python type here. winreg handles the final binary conversion.

    if target_type in (REG_SZ, REG_EXPAND_SZ, REG_LINK):
        if not isinstance(data, str):
            raise TypeError(
                f"Data must be a string for registry type {get_reg_type_name(target_type)}, "
                f"but got {type(data)}."
            )
        return data # Data is already the correct Python type

    # Handle REG_DWORD and its aliases (REG_DWORD_LITTLE_ENDIAN)
    elif target_type in (REG_DWORD, REG_DWORD_LITTLE_ENDIAN, REG_DWORD_BIG_ENDIAN):
         if not isinstance(data, int):
             raise TypeError(
                 f"Data must be an integer for registry type {get_reg_type_name(target_type)}, "
                 f"but got {type(data)}."
             )
         # Check range for 32-bit int
         if not (-2**31 <= data <= 2**32 - 1):
              raise ValueError(
                  f"Integer data {data} is out of range for a 32-bit registry type "
                  f"({get_reg_type_name(target_type)})."
              )
         return data # Data is already the correct Python type

    # Handle REG_QWORD and its aliases (REG_QWORD_LITTLE_ENDIAN)
    elif target_type in (REG_QWORD, REG_QWORD_LITTLE_ENDIAN):
         if not isinstance(data, int):
             raise TypeError(
                 f"Data must be an integer for registry type {get_reg_type_name(target_type)}, "
                 f"but got {type(data)}."
             )
         # Check range for 64-bit int
         if not (-2**63 <= data <= 2**64 - 1):
              raise ValueError(
                  f"Integer data {data} is out of range for a 64-bit registry type "
                  f"({get_reg_type_name(target_type)})."
              )
         return data # Data is already the correct Python type

    elif target_type == REG_BINARY:
         if not isinstance(data, bytes):
             raise TypeError(
                 f"Data must be bytes for registry type {get_reg_type_name(target_type)}, "
                 f"but got {type(data)}."
             )
         return data # Data is already the correct Python type

    elif target_type == REG_MULTI_SZ:
         if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
              raise TypeError(
                  f"Data must be a list of strings for registry type {get_reg_type_name(target_type)}, "
                  f"but got {type(data)}."
              )
         # winreg.SetValueEx expects a list of strings for REG_MULTI_SZ
         return data

    elif target_type == REG_NONE:
        # REG_NONE data is ignored, but SetValueEx expects None or b''
        if data is not None and data != b'':
             logger.warning(
                 "Data %r provided for REG_NONE type. Data will be ignored by the registry.",
                 data
             )
        # Return None or b'' as expected by SetValueEx for REG_NONE
        return None # winreg.SetValueEx(..., REG_NONE, None) is typical

    # Add validation for other types if necessary (e.g., resource types expect bytes)
    elif target_type in (REG_RESOURCE_LIST, REG_FULL_RESOURCE_DESCRIPTOR, REG_RESOURCE_REQUIREMENTS_LIST):
         if not isinstance(data, bytes):
             raise TypeError(
                 f"Data must be bytes for registry type {get_reg_type_name(target_type)}, "
                 f"but got {type(data)}."
             )
         return data # Data is already the correct Python type

    # For unknown or unhandled target types, raise an error
    else:
         # Use get_reg_type_name which handles unknown integer types gracefully
         type_name = get_reg_type_name(target_type)
         raise TypeError(f"Unsupported or unhandled target registry type: {type_name} ({target_type}).")

# No __all__ list here, as this module is internal.
