"""Hotkey fallback and microphone health: failures must be reported, never silent."""
import sys

import pytest

from aura import __main__ as cli
from aura.platform.stub import StubPlatform


class _Hub:
    def __init__(self, talk="ctrl+alt+space", mute="ctrl+alt+m"):
        self.platform = StubPlatform()
        self.cfg = {"voice": {"hotkey_talk": talk, "hotkey_mute": mute}}


def test_configured_hotkeys_are_used_when_free():
    talk, mute, notes = cli._start_hotkeys(_Hub(), lambda: None, lambda: None)
    assert (talk, mute, notes) == ("ctrl+alt+space", "ctrl+alt+m", [])


def test_taken_hotkey_falls_back_and_says_so():
    hub = _Hub()
    hub.platform.taken_hotkeys = {"ctrl+alt+space"}
    talk, mute, notes = cli._start_hotkeys(hub, lambda: None, lambda: None)
    assert talk == cli.HOTKEY_FALLBACKS["hotkey_talk"][0]
    assert mute == "ctrl+alt+m"
    assert len(notes) == 1 and "ctrl+alt+space is unavailable" in notes[0] and talk in notes[0]
    assert "another program" in notes[0]


def test_no_free_hotkey_is_reported_not_hidden():
    hub = _Hub()
    hub.platform.taken_hotkeys = {"ctrl+alt+space", *cli.HOTKEY_FALLBACKS["hotkey_talk"]}
    talk, mute, notes = cli._start_hotkeys(hub, lambda: None, lambda: None)
    assert talk is None and mute == "ctrl+alt+m"
    assert notes and notes[0].startswith("WARNING") and "voice.hotkey_talk" in notes[0]


def test_fallback_never_steals_the_other_configured_hotkey():
    hub = _Hub(talk="ctrl+alt+space", mute="ctrl+alt+j")  # mute sits on talk's first fallback
    hub.platform.taken_hotkeys = {"ctrl+alt+space"}
    talk, mute, _ = cli._start_hotkeys(hub, lambda: None, lambda: None)
    assert mute == "ctrl+alt+j" and talk not in (None, "ctrl+alt+j")


def test_muted_microphone_is_a_failure():
    good, text = cli._microphone_verdict({"name": "Microphone Array (Intel® Smart Sound)", "muted": True, "level": 70})
    assert not good and "MUTED" in text and "Intel® Smart Sound" in text


def test_zero_level_microphone_is_a_failure():
    good, text = cli._microphone_verdict({"name": "Mic", "muted": False, "level": 0})
    assert not good and "0 percent" in text


def test_healthy_microphone_shows_full_name():
    name = "Microphone Array (Intel® Smart Sound Technology for Digital Microphones)"
    good, text = cli._microphone_verdict({"name": name, "muted": False, "level": 70})
    assert good and name in text and "�" not in text


def test_unknown_microphone_state_does_not_fail():
    class Broken:
        def microphone(self):
            raise OSError("no audio service")

    assert cli._microphone_info(Broken()) is None
    assert cli._microphone_verdict(None) == (True, "")


def test_silent_recording_warns_and_real_signal_does_not():
    assert "silent" in cli._signal_warning(0) and "silent" in cli._signal_warning(2)
    assert cli._signal_warning(40) == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows hotkey parsing")
def test_windows_hotkey_parsing():
    from aura.platform.windows import WindowsPlatform

    parse = WindowsPlatform._parse_hotkey
    assert parse("ctrl+alt+space") == (0x4000 | 0x2 | 0x1, 0x20)
    assert parse("Ctrl+Alt+M") == (0x4000 | 0x2 | 0x1, 0x4D)
    assert parse("ctrl+alt+f9") == (0x4000 | 0x2 | 0x1, 0x78)
    with pytest.raises(ValueError):
        parse("ctrl+alt+spacebar")
    with pytest.raises(ValueError):
        parse("hyper+a")


def test_once_does_not_keep_a_spare_claude_warm(hub, monkeypatch, capsys):
    """A single request has nothing to warm up for; a spare would only delay the exit."""
    import types

    from aura import __main__ as cli
    from aura import hub as hub_module
    from aura.brain import llm

    seen = {}

    def choose(h):
        seen["keep_warm"] = h.cfg["brain"]["keep_warm"]
        return None, "none"

    monkeypatch.setattr(hub_module, "Hub", lambda: hub)
    monkeypatch.setattr(llm, "choose", choose)
    monkeypatch.setattr(cli, "_logging", lambda console: None)
    cli.cmd_once(types.SimpleNamespace(words=["what", "time", "is", "it"]))
    assert seen["keep_warm"] is False
    assert capsys.readouterr().out.strip()

    hub.cfg["brain"]["keep_warm"] = True
    cli._text_hub()                                  # text mode has later requests: stays warm
    assert seen["keep_warm"] is True
