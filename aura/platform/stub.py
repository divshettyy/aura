"""Stand-in platform for non-Windows machines and tests: records calls instead of acting."""
from __future__ import annotations


class StubPlatform:
    name = "stub"

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.volume = 50
        self.locked = False
        self.dialog_answer = False
        self.clipboard = ""
        self.mic = {"name": "stub microphone", "muted": False, "level": 70}
        self.taken_hotkeys: set[str] = set()  # combinations "owned by another program"
        self.dark = False
        self.recycled = 3  # items "in the Recycle Bin"
        self.start_menu = {"claude": "Claude.lnk", "visual studio code": "Code.lnk"}

    def _log(self, *call):
        self.calls.append(call)

    def start_menu_apps(self) -> dict[str, str]:
        return dict(self.start_menu)

    def launch(self, target: str, args: str = "") -> None:
        self._log("launch", target, args)

    def close_process(self, process: str) -> int:
        self._log("close", process)
        return 1

    def open_url(self, url: str, browser: str) -> None:
        self._log("open_url", url, browser)

    def open_path(self, path: str) -> None:
        self._log("open_path", path)

    def get_volume(self) -> int:
        return self.volume

    def set_volume(self, percent: int) -> None:
        self.volume = percent
        self._log("volume", percent)

    def set_mute(self, on: bool) -> None:
        self._log("mute", on)

    def get_brightness(self) -> int:
        return 50

    def set_brightness(self, percent: int) -> None:
        self._log("brightness", percent)

    def media_key(self, action: str) -> None:
        self._log("media", action)

    def lock(self) -> None:
        self._log("lock")

    def is_locked(self) -> bool:
        return self.locked

    def screenshot(self, path: str) -> None:
        self._log("screenshot", path)

    def power(self, action: str) -> None:
        self._log("power", action)

    def battery(self):
        return (80, True)

    def wifi_name(self):
        return "stub-wifi"

    def battery_minutes(self):
        return 135

    def disk_free(self):
        return (120, 475)

    def window(self, action: str) -> None:
        self._log("window", action)

    def get_dark_mode(self) -> bool:
        return self.dark

    def set_dark_mode(self, on: bool) -> None:
        self.dark = on
        self._log("dark_mode", on)

    def recycle_bin_count(self) -> int:
        return self.recycled

    def empty_recycle_bin(self) -> int:
        count, self.recycled = self.recycled, 0
        self._log("empty_recycle_bin", count)
        return count

    def type_text(self, text: str) -> None:
        self._log("type", text)

    def clipboard_get(self) -> str:
        return self.clipboard

    def clipboard_set(self, text: str) -> None:
        self.clipboard = text

    def confirm_dialog(self, text: str) -> bool:
        self._log("dialog", text)
        return self.dialog_answer

    def beep(self, kind: str) -> None:
        pass

    def trash(self, path: str) -> None:
        self._log("trash", path)

    def run_visible(self, argv: list[str]) -> None:
        self._log("run_visible", tuple(argv))

    def microphone(self) -> dict:
        return dict(self.mic)

    def hotkey_available(self, combo: str) -> tuple[bool, str]:
        if combo in self.taken_hotkeys:
            return False, "another program already uses this key combination"
        return True, ""

    def hotkeys(self, bindings: dict, fallbacks: dict | None = None) -> dict:
        result = {}
        for combo in bindings:
            reason = ""
            for candidate in [combo, *(fallbacks or {}).get(combo, [])]:
                if candidate not in self.taken_hotkeys:
                    result[combo] = (candidate, reason)
                    break
                reason = reason or "another program already uses this key combination"
            else:
                result[combo] = (None, reason)
        self._log("hotkeys", tuple(sorted(result.items())))
        return result
