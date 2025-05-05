import pytest
import os # Needed for os.path.join in tests

# Import the module containing the helper function
from winregenv import registry_base

# The mock_winreg fixture is provided by conftest.py in the same directory
# (though not needed for this specific test)

def test__join_registry_paths():
    assert registry_base._join_registry_paths("", "") == ""
    assert registry_base._join_registry_paths("Prefix", "") == "Prefix"
    assert registry_base._join_registry_paths("", "Path") == "Path"
    assert registry_base._join_registry_paths("Prefix", "Path") == os.path.join("Prefix", "Path").replace('/', '\\')
    assert registry_base._join_registry_paths("Prefix\\Sub", "Path\\To\\Key") == os.path.join("Prefix\\Sub", "Path\\To\\Key").replace('/', '\\')
    assert registry_base._join_registry_paths("Prefix/Sub", "Path/To/Key") == os.path.join("Prefix/Sub", "Path/To/Key").replace('/', '\\') # Handles forward slashes
