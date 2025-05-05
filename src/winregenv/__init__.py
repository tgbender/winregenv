import sys

# Import the public interface components
from .registry_interface import RegistryRoot
from .registry_errors import (
    RegistryError,
    RegistryKeyNotFoundError,
    RegistryValueNotFoundError,
    RegistryKeyNotEmptyError,
    RegistryPermissionError,
    RegistryExpansionError, # Import the new exception
)
from .registry_types import RegistryValue # noqa: F401 # Imported for __all__ and type hints
from .registry_interface import normalize_root_key # Import the new public function
from .registry_translation import normalize_registry_type # Import the new public function

__all__ = [
    "RegistryRoot", # Add the main interface class
    "RegistryValue",
    "normalize_root_key", # Add normalize_root_key to the public API
    "normalize_registry_type", # Add normalize_registry_type to the public API
    # Add exception classes to the public API
    "RegistryError",
    "RegistryKeyNotFoundError",
    "RegistryValueNotFoundError",
    "RegistryKeyNotEmptyError",
    "RegistryPermissionError",
    "RegistryExpansionError", # Add the new exception to the public API
    "is_elevated", # Add is_elevated to the public API
    "get_integrity_level", # Add get_integrity_level to the public API
    "expand_environment_strings",

    # Add common REG_* constants to __all__ so users don't need to import winreg directly
    "REG_SZ",
    "REG_EXPAND_SZ",
    "REG_BINARY",
    "REG_DWORD",
    "REG_QWORD",
    "REG_MULTI_SZ",
]

if sys.platform != "win32":
    # Raise immediately on import if not on Windows. This prevents importing winreg or ctypes modules below.
    raise NotImplementedError("This module requires Windows APIs and only runs on Windows.")

# Import get_integrity_level here after the platform check
from .elevation_check import is_elevated # noqa: F401 # Imported for __all__
from .elevation_check import get_integrity_level # noqa: F401 # Imported for __all__ # Add get_integrity_level to the public API

# Import expand_environment_strings here after the platform check
from .expand_variable import expand_environment_strings # noqa: F401 # Imported for __all__

# Import common REG_* constants here after the platform check
from .registry_translation import ( # noqa: F401 # Imported for __all__
    REG_SZ, REG_EXPAND_SZ, REG_BINARY, REG_DWORD, REG_QWORD, REG_MULTI_SZ
)

#Version Attribute
__version__ = "0.1.0"