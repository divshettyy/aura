"""Secrets live in the OS credential store (Windows Credential Manager), never in files."""
from __future__ import annotations

import os
import sys
import threading

SERVICE = "Aura"
_preload: threading.Thread | None = None
_preload_lock = threading.Lock()


def keyring_module():
    """The keyring library, loaded on first use: importing it and finding its back-end takes
    most of a second, which is why nothing imports it at the top of a file.

    On Windows the back-end is named up front (the one keyring picks by itself, Windows
    Credential Manager), which skips its search through every installed back-end. A
    PYTHON_KEYRING_BACKEND the user has set is left alone."""
    if sys.platform == "win32":
        os.environ.setdefault("PYTHON_KEYRING_BACKEND", "keyring.backends.Windows.WinVaultKeyring")
    import keyring

    return keyring


def preload() -> None:
    """Start loading the credential store in the background, so the first request does not wait
    for it. Safe to call more than once; a failure here is reported later, by whoever uses it."""
    global _preload

    def work() -> None:
        try:
            keyring_module().get_keyring()
        except Exception:
            pass

    with _preload_lock:
        if _preload is None:
            _preload = threading.Thread(target=work, name="aura-keyring-preload", daemon=True)
            _preload.start()


def get(name: str) -> str | None:
    try:
        return keyring_module().get_password(SERVICE, name)
    except Exception:
        return None


def put(name: str, value: str) -> None:
    keyring_module().set_password(SERVICE, name, value)


def delete(name: str) -> None:
    try:
        keyring_module().delete_password(SERVICE, name)
    except Exception:
        pass
