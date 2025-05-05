"""
Custom data structures for representing Windows Registry data.

This module defines classes used to encapsulate data retrieved from the
registry, providing a more structured and type-hintable alternative
to raw tuples or dictionaries.
"""

from typing import Any, Tuple, Optional
import winreg # Needed for type hints like winreg.REG_SZ

from .expand_variable import expand_environment_strings # Import the expansion function # noqa: F401 # Imported for use in expanded_data property
from .registry_translation import REG_EXPAND_SZ, REG_MULTI_SZ, get_reg_type_name # Import constants and helper
import logging

logger = logging.getLogger(__name__)

class RegistryValue:
    """
    Represents a registry value with its name, data, and type.

    This class provides attribute access (value.name, value.data, value.type),
    supports tuple unpacking (name, data, value_type = value), and
    supports index access (value[0], value[1], value[2]) for backward
    compatibility with code that previously expected a tuple.
    It also provides an `expanded_data` property for REG_EXPAND_SZ values.
    """
    def __init__(self, name: str, data: Any, value_type: int):
        """
        Initializes a RegistryValue instance.

        Args:
            name (str): The name of the registry value ("" for the default value).
            data (Any): The data stored in the value.
            value_type (int): The registry data type (e.g., winreg.REG_SZ). For REG_MULTI_SZ, a list
                              of strings is accepted, but the
                              data is stored internally and returned by the .data property as a
                              original list input is accepted and the .data
                              property returns the internal tuple.
        """
        self._name = name
        self._value_type = value_type

        # Store REG_MULTI_SZ data as a tuple internally for hashability
        # This ensures the RegistryValue object is hashable, as tuples are immutable.
        if value_type == REG_MULTI_SZ and isinstance(data, list):
            # Ensure all elements are strings, though validation should handle this earlier
            self._data = tuple(data)
        else:
            self._data = data # Assign original data for other types

    @property
    def name(self) -> str:
        """The name of the registry value ("" for the default value)."""
        return self._name

    @property
    def data(self) -> Any:
        """
        The data stored in the registry value.

        For REG_MULTI_SZ values, this property returns the data as a tuple of
        strings (even if a list was provided during initialization). This is
        done to ensure the RegistryValue object remains hashable.
        """
        # Return the internally stored data (which is a tuple for REG_MULTI_SZ)
        return self._data

    @property
    def type(self) -> int:
        """The registry data type (e.g., winreg.REG_SZ)."""
        return self._value_type

    @property
    def type_name(self) -> str:
        """The string name of the registry data type (e.g., "REG_SZ")."""
        return get_reg_type_name(self._value_type)

    @property
    def expanded_data(self) -> Optional[str]:
        """
        Returns the expanded string data if the value type is REG_EXPAND_SZ and data is a string.

        Uses the Windows API ExpandEnvironmentStringsW to replace environment
        variable references (like %VAR%) with their current values.

        Returns:
            str: The expanded string if the value type is REG_EXPAND_SZ
                 and the data is a string.

            Optional[str]: The expanded string if the value type is REG_EXPAND_SZ
                           and the data is a string. Returns None for all other
                           registry types or if the data is not a string.
        """
        # Expansion is only applicable and meaningful for REG_EXPAND_SZ type
        if self._value_type == REG_EXPAND_SZ and isinstance(self._data, str):
            # Call the utility function to perform the actual expansion
            from .registry_errors import RegistryExpansionError # Import locally to avoid circular dependency
            try:
                # expand_environment_strings raises OSError (ctypes.WinError) on failure
                return expand_environment_strings(self._data)
            except OSError as e:
                # Catch specific OSError from the expansion function
                # Wrap the OSError in a custom exception for consistency
                logger.error(
                    f"Failed to expand REG_EXPAND_SZ value '{self._name}' data {self._data!r}: {e}",
                    exc_info=True
                )
                # Raise the custom error, chaining the original exception
                raise RegistryExpansionError(
                    f"Failed to expand REG_EXPAND_SZ value '{self._name}' data {self._data!r}"
                ) from e

        # For any other type, expansion is not applicable in this context
        return None

    def __iter__(self):
        """
        Supports tuple unpacking (name, data, value_type = value).
        Yields name, then data, then value_type.
        """
        yield self._name
        yield self._data
        yield self._value_type

    def __getitem__(self, key: int):
        """
        Supports index access [0] for name, [1] for data, [2] for type.

        Args:
            key (int): The index (0, 1, or 2).

        Returns:
            Any: The requested attribute (name, data, or type).

        Raises:
            IndexError: If the index is out of range.
        """
        if key == 0:
            return self._name
        elif key == 1:
            return self._data
        elif key == 2:
            return self._value_type
        else:
            raise IndexError("RegistryValue index out of range (expected 0, 1, or 2)")

    def __repr__(self):
        """Provides a developer-friendly string representation."""
        return f"RegistryValue(name={self._name!r}, data={self._data!r}, value_type={self._value_type!r})"

    def __str__(self):
        """Provides a user-friendly string representation."""
        # Simple string representation, could be enhanced
        return f"'{self._name}': {self._data} (Type: {self._value_type})"


    def __eq__(self, other):
        """
        Compares this RegistryValue object to another object.
        Allows comparison with another RegistryValue or a tuple (name, data, type).
        """
        if isinstance(other, RegistryValue):
            # Compare internal data representation
            return (self._name == other.name and
                    self._data == other.data and
                    self._value_type == other.type)
        # Allow comparison with a tuple (name, data, type) for backward compatibility
        # Need to handle the case where self._data is a tuple (for MULTI_SZ)
        # but the tuple being compared against has a list for data.
        # Note: self._data is already a tuple if it was REG_MULTI_SZ list input
        if isinstance(other, tuple) and len(other) == 3:
            if self._value_type == REG_MULTI_SZ and isinstance(other[1], list):
             # Compare the tuple data with the list data by converting the list to a tuple
             return (self._name == other[0] and self._data == tuple(other[1]) and self._value_type == other[2])
            return (self._name == other[0] and self._data == other[1] and self._value_type == other[2])
        return NotImplemented

    def __hash__(self):
        """
        Enables hashing, allowing RegistryValue objects to be used in sets or as dictionary keys.
        Hashing is based on the immutable attributes (name, data, type).
        Note: Hashing mutable data types (like lists or dicts in self._data) will raise an error.
        REG_MULTI_SZ data, which is a list of strings from winreg, is converted
        to a tuple internally to make it hashable.
        """ # Use a tuple of the immutable attributes for hashing
        # self._data is already the tuple if it was REG_MULTI_SZ list input
        # If self._data is still a list (e.g., if the type wasn't REG_MULTI_SZ
        # but the input data was a list), hashing will fail as expected.
        # The validation/inference logic should prevent this for types other than MULTI_SZ.

        return hash((self._name, self._data, self._value_type))
