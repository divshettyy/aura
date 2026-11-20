"""Tamper-evident audit log: each line carries the hash of the line before it.

The chain alone cannot show that lines were cut off the end (what is left is still a valid
chain), so the entry count and the newest hash - the "head anchor" - are also kept outside the
file, in the system credential store. `verify` compares the file against that anchor.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

GENESIS = "0" * 64
_DEFAULT = object()  # "use the system credential store"; pass store=None to run without an anchor


def _digest(prev: str, body: dict) -> str:
    payload = prev + json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class KeyringStore:
    """Head anchors in the OS credential store (Windows Credential Manager). get/set may raise."""

    SERVICE = "Aura"

    def preload(self) -> None:
        """Load the credential-store library in the background (it takes most of a second)."""
        from . import secrets

        secrets.preload()

    def get(self, key: str) -> str | None:
        from . import secrets

        return secrets.keyring_module().get_password(self.SERVICE, key)

    def set(self, key: str, value: str) -> None:
        from . import secrets

        secrets.keyring_module().set_password(self.SERVICE, key, value)


def default_store():
    """The credential store, or None when anchoring is switched off (AURA_AUDIT_ANCHOR=off) or a
    test run is in progress (tests must never write to the real credential store)."""
    if os.environ.get("AURA_AUDIT_ANCHOR", "").lower() in ("off", "0", "no", "false"):
        return None
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return KeyringStore()


def _anchor_key(path: Path) -> str:
    """One anchor per log file, so a second Aura home never overwrites the first one's anchor."""
    try:
        full = str(Path(path).resolve())
    except OSError:
        full = str(Path(path).absolute())
    return "audit-head-" + hashlib.sha256(os.path.normcase(full).encode("utf-8")).hexdigest()[:16]


def _read_anchor(store, path: Path) -> tuple[str, int, str]:
    """Returns (state, count, tip); state is 'ok', 'none' (nothing stored yet) or 'unavailable'."""
    if store is None:
        return "unavailable", 0, ""
    try:
        raw = store.get(_anchor_key(path))
    except Exception:
        return "unavailable", 0, ""
    if not raw:
        return "none", 0, ""
    try:
        data = json.loads(raw)
        return "ok", int(data["count"]), str(data["tip"])
    except (ValueError, KeyError, TypeError):
        return "unavailable", 0, ""


class AuditLog:
    def __init__(self, path: Path, store=_DEFAULT) -> None:
        self.path = path
        self._store = default_store() if store is _DEFAULT else store
        self._lock = threading.Lock()
        self._last = GENESIS
        self._count = 0
        preload = getattr(self._store, "preload", None)
        if preload is not None:  # the first record then finds the credential store already loaded
            preload()
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    self._last = json.loads(line)["hash"]
                    self._count += 1
                except (ValueError, KeyError, TypeError):
                    # A half-written line (crash or power loss mid-append) must not stop Aura
                    # from starting. The chain continues from the last good entry;
                    # `aura audit verify` still reports the damaged line.
                    continue

    def record(self, kind: str, **data) -> None:
        body = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, "data": data}
        with self._lock:
            entry = dict(body, prev=self._last, hash=_digest(self._last, body))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())  # keep a crash from leaving a half-written line
            self._last = entry["hash"]
            self._count += 1
            self._write_anchor()

    def _write_anchor(self) -> None:
        """Best effort: a missing or failing credential store must never stop Aura from logging."""
        if self._store is None:
            return
        try:
            self._store.set(
                _anchor_key(self.path), json.dumps({"count": self._count, "tip": self._last})
            )
        except Exception:
            pass


def verify(path: Path, store=_DEFAULT) -> tuple[bool, str]:
    """Returns (ok, message). Detects edited, removed or reordered lines, and - when the head
    anchor is available - lines removed from the end."""
    store = default_store() if store is _DEFAULT else store
    state, anchor_count, anchor_tip = _read_anchor(store, path)
    if not path.exists():
        if state == "ok" and anchor_count > 0:
            return False, f"audit log file is missing, but {anchor_count} entries were recorded"
        return True, "no audit log yet"
    prev, hashes = GENESIS, []
    for number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            body = {k: entry[k] for k in ("ts", "kind", "data")}
            intact = entry["prev"] == prev and entry["hash"] == _digest(prev, body)
        except (ValueError, KeyError, TypeError):
            intact = False
        if not intact:
            return False, f"audit log was altered at line {number}"
        prev = entry["hash"]
        hashes.append(prev)
    count = len(hashes)
    if state == "unavailable":
        return (
            True,
            f"{count} entries, chain intact (head anchor unavailable: removal from the end is not checked)",
        )
    if state == "none":
        return (
            True,
            f"{count} entries, chain intact (no head anchor yet: it is created with the next entry)",
        )
    if count < anchor_count:
        missing = anchor_count - count
        return (
            False,
            f"audit log was truncated: {missing} {'entry' if missing == 1 else 'entries'} missing from the end",
        )
    # The file may be ahead of the anchor (an anchor write failed or was interrupted); the entry
    # the anchor points at must still be the one that was recorded.
    if anchor_count > 0 and hashes[anchor_count - 1] != anchor_tip:
        return (
            False,
            f"audit log does not match its head anchor at entry {anchor_count} (the end was replaced)",
        )
    return True, f"{count} entries, chain intact"
