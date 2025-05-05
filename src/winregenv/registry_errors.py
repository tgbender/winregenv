from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Define custom exceptions
class RegistryError(Exception):
    """Base exception for all registry errors in this module."""
    def __init__(self, message: str, winerror: Optional[int] = None, strerror: Optional[str] = None):
        super().__init__(message)
        self.winerror = winerror
        self.strerror = strerror

    def __str__(self) -> str:
        """Return the primary message associated with this error."""
        return self.args[0] if self.args else self.__class__.__name__


class RegistryKeyNotFoundError(RegistryError, LookupError):
    """Raised when a specified registry key path does not exist."""
    # No change needed, inherits __init__ from RegistryError
    pass


class RegistryValueNotFoundError(RegistryError, LookupError):
    """Raised when a specified registry value name does not exist within a key."""
    pass


class RegistryKeyNotEmptyError(RegistryError):
    """Raised when attempting to delete a registry key that has subkeys or values."""
    pass


class RegistryPermissionError(RegistryError, PermissionError):
    """Raised when a registry operation is denied due to insufficient privileges."""
    pass

# Map common WindowsError codes to custom exceptions
# This list is not exhaustive but covers common scenarios
_ERROR_MAP = {
    2: RegistryKeyNotFoundError, # ERROR_FILE_NOT_FOUND (used for keys/values)
    5: RegistryPermissionError,  # ERROR_ACCESS_DENIED
    183: RegistryError,          # ERROR_ALREADY_EXISTS (might need more specific handling if used)
    206: RegistryError,          # ERROR_FILENAME_EXCED_RANGE (path too long)
    247: RegistryKeyNotEmptyError, # ERROR_DIR_NOT_EMPTY (used for keys, though our check prevents this)
    # Add other relevant codes as needed
}


def _handle_winreg_error(e: OSError, path: str, name: Optional[str] = None):
    """Translate a Windows OSError into a custom RegistryError.

    Args:
        e (OSError): The original exception raised by a winreg call.
        path (str): The registry key path involved.
        name (Optional[str]): The registry value name, if applicable.

    Raises:
        RegistryError or subclass: The mapped exception wrapping original winerror.
    """
    # On Windows, OSErrors originating from winreg calls are WindowsErrors,
    # which have the winerror attribute.
    err_code = getattr(e, 'winerror', None) # Safely get winerror, default to None
    # Use the mapped exception type, default to RegistryError
    custom_exception_type = _ERROR_MAP.get(err_code, RegistryError)

    message = f"Registry operation failed on key '{path}'"
    if name is not None:
        message += f", value '{name}'"
    # Include winerror and strerror in the message for quick debugging
    if err_code is not None:
         message += f" (WinError {err_code}: {e.strerror})"
    elif e.strerror:
         message += f" ({e.strerror})"

    if custom_exception_type is RegistryKeyNotEmptyError:
         # Check if the path is already in the message to avoid duplication
         if path not in message:
             message = f"Registry key '{path}' is not empty. " + message

    # If the caught exception is already a specific RegistryError subclass,
    # re-raise it directly instead of wrapping it in a potentially less specific one.
    # This handles cases where _handle_winreg_error is called with an exception
    # that was already translated upstream (e.g., from RegistryKey.__enter__).
    if isinstance(e, RegistryError):
         # Preserve winerror if it wasn’t set yet
         if e.winerror is None and err_code is not None:
             e.winerror = err_code
         # Re‑raise the existing RegistryError without wrapping it again
         raise

    # DEBUG: log how we're mapping the WinError to a custom exception
    logger.debug(
        "Mapping WinError %s (%r) for key '%s'%s → %s",
        err_code,
        e.strerror,
        path,
        (f", value '{name}'" if name else ""),
        custom_exception_type.__name__
    )
    raise custom_exception_type(message, winerror=err_code, strerror=e.strerror) from e

class RegistryExpansionError(RegistryError):
    """Raised when expanding a REG_EXPAND_SZ value fails."""
    pass
