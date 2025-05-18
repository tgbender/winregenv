# -*- coding: utf-8 -*-
"""
Unit tests for winregenv.winapi.broadcast_setting_change.
"""
import sys
import pytest
from unittest.mock import MagicMock, ANY

import winregenv.winapi as winapi

@pytest.fixture(autouse=True)
def patch_ctypes_and_user32(monkeypatch):
    # Force platform to win32 for these tests
    monkeypatch.setattr(sys, "platform", "win32")
    # Create a fake user32 DLL object
    fake_user32 = MagicMock()
    monkeypatch.setattr(winapi, "user32", fake_user32)
    # Patch ctypes functions used in winapi
    monkeypatch.setattr(winapi.ctypes, "get_last_error", lambda: 0)
    monkeypatch.setattr(winapi.ctypes, "set_last_error", lambda code: None)
    monkeypatch.setattr(winapi.ctypes, "create_unicode_buffer", lambda s: f"BUF<{s}>")
    monkeypatch.setattr(winapi.ctypes, "byref", lambda x: x)
    return fake_user32

def test_success_default_timeout(patch_ctypes_and_user32):
    user32 = patch_ctypes_and_user32
    user32.SendMessageTimeoutW.return_value = 1
    # Call without specifying timeout (uses default)
    winapi.broadcast_setting_change("Env")
    default_timeout = winapi.broadcast_setting_change.__defaults__[1]
    user32.SendMessageTimeoutW.assert_called_once_with(
        winapi.HWND_BROADCAST,
        winapi.WM_SETTINGCHANGE,
        0,
        "BUF<Env>",
        winapi.SMTO_ABORTIFHUNG,
        default_timeout,
        ANY
    )

@pytest.mark.parametrize("timeout_ms", [100, 2500, 5000])
def test_success_custom_timeout(patch_ctypes_and_user32, timeout_ms):
    user32 = patch_ctypes_and_user32
    user32.SendMessageTimeoutW.return_value = 1
    winapi.broadcast_setting_change("Test", timeout_ms=timeout_ms)
    user32.SendMessageTimeoutW.assert_called_once_with(
        winapi.HWND_BROADCAST,
        winapi.WM_SETTINGCHANGE,
        0,
        "BUF<Test>",
        winapi.SMTO_ABORTIFHUNG,
        timeout_ms,
        ANY
    )

def test_lparam_none(patch_ctypes_and_user32):
    user32 = patch_ctypes_and_user32
    user32.SendMessageTimeoutW.return_value = 1
    winapi.broadcast_setting_change(None, timeout_ms=1234)
    user32.SendMessageTimeoutW.assert_called_once_with(
        winapi.HWND_BROADCAST,
        winapi.WM_SETTINGCHANGE,
        0,
        None,
        winapi.SMTO_ABORTIFHUNG,
        1234,
        ANY
    )

@pytest.mark.parametrize("errcode,exc", [
    (winapi.ERROR_TIMEOUT, winapi.MessageTimeoutError),
    (5, OSError),
    (1234, OSError),
])
def test_error_paths(patch_ctypes_and_user32, monkeypatch, errcode, exc):
    user32 = patch_ctypes_and_user32
    user32.SendMessageTimeoutW.return_value = 0
    monkeypatch.setattr(winapi.ctypes, "get_last_error", lambda: errcode)
    with pytest.raises(exc):
        winapi.broadcast_setting_change("Name", timeout_ms=777)
