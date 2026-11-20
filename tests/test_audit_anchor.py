"""Head anchor: removal of lines from the end of the audit log is detected."""

import json

from aura import audit
from aura.audit import AuditLog


class FakeStore:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value


class BrokenStore:
    def get(self, key):
        raise RuntimeError("no credential backend")

    def set(self, key, value):
        raise RuntimeError("no credential backend")


def _log(tmp_path, store, entries=3):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path, store=store)
    for i in range(entries):
        log.record("ran", n=i)
    return path


def _drop_last(path, n):
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-n]) + "\n", encoding="utf-8")


def test_intact_log_verifies(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store)
    assert audit.verify(path, store=store) == (True, "3 entries, chain intact")


def test_truncation_is_detected(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store, entries=5)
    _drop_last(path, 2)
    good, message = audit.verify(path, store=store)
    assert not good and "2 entries missing from the end" in message
    assert audit.verify(path, store=None)[0]  # the chain alone cannot see it


def test_truncate_then_forge_is_detected(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store, entries=4)
    _drop_last(path, 2)
    forger = AuditLog(path, store=None)  # appends a valid chain from the public tip hash
    forger.record("ran", n="forged-1")
    forger.record("ran", n="forged-2")
    good, message = audit.verify(path, store=store)
    assert not good and "head anchor" in message


def test_deleted_file_is_detected(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store)
    path.unlink()
    good, message = audit.verify(path, store=store)
    assert not good and "missing" in message
    assert audit.verify(tmp_path / "never.jsonl", store=store) == (True, "no audit log yet")


def test_existing_log_without_anchor_is_intact_and_gets_one(tmp_path):
    path = _log(tmp_path, None)  # written before anchors existed
    store = FakeStore()
    good, message = audit.verify(path, store=store)
    assert good and "no head anchor yet" in message
    AuditLog(path, store=store).record("ran", n="next")
    anchor = json.loads(next(iter(store.data.values())))
    assert anchor["count"] == 4
    assert audit.verify(path, store=store) == (True, "4 entries, chain intact")
    _drop_last(path, 1)
    assert not audit.verify(path, store=store)[0]


def test_broken_credential_store_never_breaks_logging(tmp_path):
    path = _log(tmp_path, BrokenStore())
    good, message = audit.verify(path, store=BrokenStore())
    assert good and "head anchor unavailable" in message


def test_file_ahead_of_anchor_is_accepted(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store)
    AuditLog(path, store=BrokenStore()).record("ran", n="anchor write failed")
    assert audit.verify(path, store=store) == (True, "4 entries, chain intact")


def test_edits_are_still_detected(tmp_path):
    store = FakeStore()
    path = _log(tmp_path, store)
    path.write_text(path.read_text(encoding="utf-8").replace('"n": 1', '"n": 9'), encoding="utf-8")
    good, message = audit.verify(path, store=store)
    assert not good and "altered at line 2" in message


def test_anchors_are_per_log_file(tmp_path):
    store = FakeStore()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = _log(tmp_path / "a", store, entries=5)
    second = _log(tmp_path / "b", store, entries=2)
    assert audit.verify(first, store=store)[0] and audit.verify(second, store=store)[0]
    assert len(store.data) == 2


def test_default_store_is_off_during_tests_and_by_switch(monkeypatch):
    assert audit.default_store() is None  # a test run never touches the real credential store
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("AURA_AUDIT_ANCHOR", "off")
    assert audit.default_store() is None
    monkeypatch.delenv("AURA_AUDIT_ANCHOR")
    assert isinstance(audit.default_store(), audit.KeyringStore)


def test_log_asks_the_store_to_load_ahead_of_the_first_record(tmp_path):
    class PreloadingStore(FakeStore):
        preloads = 0

        def preload(self):
            self.preloads += 1

    store = PreloadingStore()
    path = _log(tmp_path, store)
    assert store.preloads == 1  # once, when the log is opened
    assert audit.verify(path, store=store)[0]  # and the anchor is still written with every entry
    assert json.loads(store.data[audit._anchor_key(path)])["count"] == 3


def test_keyring_backend_is_named_on_windows_only_and_never_overrides_the_user(monkeypatch):
    import sys
    import types

    from aura import secrets

    monkeypatch.setitem(sys.modules, "keyring", types.ModuleType("keyring"))
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    secrets.keyring_module()
    assert "PYTHON_KEYRING_BACKEND" not in __import__("os").environ
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "my.own.Backend")
    secrets.keyring_module()
    assert __import__("os").environ["PYTHON_KEYRING_BACKEND"] == "my.own.Backend"
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND")
    secrets.keyring_module()
    assert (
        __import__("os").environ["PYTHON_KEYRING_BACKEND"]
        == "keyring.backends.Windows.WinVaultKeyring"
    )
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND")
