# Modified for Grok Local Bridge: DPAPI primitives only, explicit paths required.
# SPDX-FileCopyrightText: 2026 Tkkdy
# SPDX-License-Identifier: MIT
"""Fail-closed HTTP Bearer authentication and Windows CurrentUser DPAPI storage."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import re
import secrets
import sys
import os
import tempfile
import time

_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


class CredentialError(ValueError):
    pass


def validate_token(token):
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise CredentialError("MCP credential is missing or invalid; service remains closed.")
    return token


def _dpapi(data, *, protect):
    if sys.platform != "win32":
        raise CredentialError("Windows CurrentUser DPAPI is required.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    result = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        # UI_FORBIDDEN only; never LOCAL_MACHINE (which would allow other users).
        if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise CredentialError("MCP credential protection failed; service remains closed.")
        return ctypes.string_at(result.data, result.size)
    finally:
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel.LocalFree(result.data)
        ctypes.memset(buffer, 0, len(data))


def load_credential(path):
    try:
        path = Path(path)
        with path.open("rb") as file:
            ciphertext = file.read(16385)
        if not ciphertext or len(ciphertext) > 16384:
            raise CredentialError("Invalid credential file.")
        return validate_token(_dpapi(ciphertext, protect=False).decode("ascii"))
    except Exception:
        raise CredentialError("MCP credential unavailable for this Windows user; service remains closed.") from None


def provision_credential(path):
    path = Path(path)
    if path.exists():
        load_credential(path)  # Validate, never overwrite or silently rotate.
        return
    ciphertext = _dpapi(secrets.token_urlsafe(32).encode("ascii"), protect=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(ciphertext)


def rotate_credential(path):
    path = Path(path)
    load_credential(path)  # Rotation requires a valid existing credential.
    ciphertext = _dpapi(secrets.token_urlsafe(32).encode("ascii"), protect=True)
    fd, temporary = tempfile.mkstemp(prefix=".token-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(ciphertext); file.flush(); os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
