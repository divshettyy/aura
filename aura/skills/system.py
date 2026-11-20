"""Apps, sound, screen, power, keyboard and clipboard."""

from __future__ import annotations

import difflib
import re
import time

from ..config import expand
from ..tools import CONFIRM, CRITICAL, Tool, ToolError

PCT = {"type": "integer", "minimum": 0, "maximum": 100}


def _resolve_app(hub, name: str):
    """Only names from the config or the Start Menu can be launched - never a raw path."""
    key = name.lower().strip()
    apps = hub.cfg["apps"]
    if key in apps:
        return key, apps[key]
    menu = hub.platform.start_menu_apps()
    if key in menu:
        return key, {"open": menu[key]}
    close = difflib.get_close_matches(key, list(apps) + list(menu), n=1, cutoff=0.72)
    if not close:
        starts = sorted(n for n in menu if n.startswith(key))
        close = starts[:1]
    if close:
        return close[0], apps.get(close[0]) or {"open": menu[close[0]]}
    raise ToolError(f"I couldn't find an app called {name}")


def open_app(hub, name: str) -> str:
    found, spec = _resolve_app(hub, name)
    hub.platform.launch(spec["open"], spec.get("args", ""))
    hub.state.set("last_app", found)
    return f"Opened {found}"


def close_app(hub, name: str) -> str:
    found, spec = _resolve_app(hub, name)
    if not spec.get("process"):
        raise ToolError(
            f"I don't know which process belongs to {found}; add 'process' for it in the config"
        )
    count = hub.platform.close_process(spec["process"])
    return f"Closed {found}" if count else f"{found} wasn't running"


def list_apps(hub) -> str:
    return "Apps: " + ", ".join(sorted(set(hub.cfg["apps"]) | set(hub.platform.start_menu_apps())))


def volume_set(hub, level: int) -> str:
    hub.platform.set_volume(level)
    return f"Volume {level} percent"


def volume_change(hub, delta: int) -> str:
    return volume_set(hub, max(0, min(100, hub.platform.get_volume() + delta)))


def mute(hub, on: bool) -> str:
    hub.platform.set_mute(on)
    return "Muted" if on else "Unmuted"


def brightness_change(hub, delta: int) -> str:
    return brightness_set(hub, max(0, min(100, hub.platform.get_brightness() + delta)))


def brightness_set(hub, level: int) -> str:
    hub.platform.set_brightness(level)
    return f"Brightness {level} percent"


def media(hub, action: str) -> str:
    hub.platform.media_key(action)
    return "OK"


def lock_screen(hub) -> str:
    hub.platform.lock()
    return "Locked"


def screenshot(hub) -> str:
    folder = expand(hub.cfg["files"]["screenshots_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("screenshot-%Y%m%d-%H%M%S.png")
    hub.platform.screenshot(str(path))
    hub.state.set("last_file", str(path))
    return f"Screenshot saved to {path}"


def system_status(hub, about: str = "all") -> str:
    """Everything, or only the part that was asked about (first, and without the slow CPU sample)."""
    if about == "wifi":
        wifi = re.sub(r"[^\w .-]", "", hub.platform.wifi_name() or "")[:32]
        return f"Connected to Wi-Fi {wifi}" if wifi else "Wi-Fi is not connected"
    if about == "disk":
        disk = hub.platform.disk_free()
        return (
            f"{disk[0]} of {disk[1]} gigabytes free" if disk else "I couldn't read the disk space"
        )
    parts = []
    battery = hub.platform.battery()
    if about == "battery" and not battery:
        return "This computer has no battery"
    if battery:
        left = hub.platform.battery_minutes()
        remaining = (
            f", about {left // 60} hours {left % 60} minutes left"
            if left and not battery[1]
            else ""
        )
        parts.append(
            f"Battery {battery[0]} percent, {'charging' if battery[1] else 'on battery'}{remaining}"
        )
        if about == "battery":
            return parts[0]
    wifi = re.sub(r"[^\w .-]", "", hub.platform.wifi_name() or "")[:32]
    parts.append(f"Wi-Fi {wifi}" if wifi else "Wi-Fi not connected")
    try:
        import psutil

        parts.append(
            f"CPU {round(psutil.cpu_percent(interval=0.2))} percent, memory {round(psutil.virtual_memory().percent)} percent"
        )
    except ImportError:
        pass
    disk = hub.platform.disk_free()
    if disk:
        parts.append(f"Disk {disk[0]} of {disk[1]} gigabytes free")
    parts.append(f"Volume {hub.platform.get_volume()} percent")
    return ". ".join(parts)


WINDOW_DONE = {
    "minimize": "Minimised",
    "maximize": "Maximised",
    "restore": "Restored",
    "show_desktop": "Showing the desktop",
    "snap_left": "Snapped left",
    "snap_right": "Snapped right",
}


def window(hub, action: str) -> str:
    try:
        hub.platform.window(action)
    except OSError:
        raise ToolError("there is no window I can arrange right now") from None
    return WINDOW_DONE[action]


def dark_mode(hub, on: bool) -> str:
    hub.platform.set_dark_mode(on)
    return "Dark mode on" if on else "Light mode on"


def empty_recycle_bin(hub) -> str:
    count = hub.platform.empty_recycle_bin()
    if not count:
        return "The Recycle Bin was already empty"
    return f"Emptied the Recycle Bin: {count} item{'s' if count != 1 else ''} deleted for good"


def power(hub, action: str) -> str:
    hub.platform.power(action)
    return {
        "sleep": "Going to sleep",
        "shutdown": "Shutting down in 30 seconds",
        "restart": "Restarting in 30 seconds",
    }[action]


def type_text(hub, text: str) -> str:
    # Tabs, line breaks and other control characters become spaces: Aura types words, it never
    # presses Enter or Tab, so dictated text cannot submit a form or run a command.
    clean = "".join(ch if ch.isprintable() else " " for ch in text)
    try:
        hub.platform.type_text(clean)
    except OSError:
        # Windows refuses keystrokes sent to a window with higher privileges than Aura.
        raise ToolError(
            "I couldn't type into that window; it may be running as administrator"
        ) from None
    return "Typed"


def clipboard_read(hub) -> str:
    return hub.platform.clipboard_get() or "(clipboard is empty)"


def clipboard_write(hub, text: str) -> str:
    hub.platform.clipboard_set(text)
    return "Copied to clipboard"


def register(reg) -> None:
    S = {"type": "string"}
    reg.add(
        Tool(
            "open_app",
            "Open an installed application by its spoken name.",
            open_app,
            {"name": S},
            ("name",),
        )
    )
    reg.add(
        Tool(
            "close_app",
            "Close a running application.",
            close_app,
            {"name": S},
            ("name",),
            risk=CONFIRM,
            confirm="Close {name}?",
        )
    )
    reg.add(Tool("list_apps", "List the applications that can be opened.", list_apps))
    reg.add(
        Tool("volume_set", "Set speaker volume (0-100).", volume_set, {"level": PCT}, ("level",))
    )
    reg.add(
        Tool(
            "volume_change",
            "Raise or lower volume by a number of points (negative lowers).",
            volume_change,
            {"delta": {"type": "integer", "minimum": -100, "maximum": 100}},
            ("delta",),
        )
    )
    reg.add(
        Tool("mute", "Mute or unmute the speakers.", mute, {"on": {"type": "boolean"}}, ("on",))
    )
    reg.add(
        Tool(
            "brightness_set",
            "Set screen brightness (0-100).",
            brightness_set,
            {"level": PCT},
            ("level",),
        )
    )
    reg.add(
        Tool(
            "brightness_change",
            "Raise or lower brightness by a number of points (negative lowers).",
            brightness_change,
            {"delta": {"type": "integer", "minimum": -100, "maximum": 100}},
            ("delta",),
        )
    )
    reg.add(
        Tool(
            "media",
            "Control media playback.",
            media,
            {"action": {"type": "string", "enum": ["play_pause", "next", "previous", "stop"]}},
            ("action",),
        )
    )
    reg.add(Tool("lock_screen", "Lock the laptop.", lock_screen))
    reg.add(Tool("screenshot", "Take a screenshot and save it.", screenshot))
    reg.add(
        Tool(
            "system_status",
            "Battery (and time left), Wi-Fi, CPU, memory, free disk space and volume; about = one part only.",
            system_status,
            {"about": {"type": "string", "enum": ["all", "battery", "wifi", "disk"]}},
        )
    )
    reg.add(
        Tool(
            "window",
            "Arrange the window in front, or show the desktop.",
            window,
            {"action": {"type": "string", "enum": sorted(WINDOW_DONE)}},
            ("action",),
        )
    )
    reg.add(
        Tool(
            "dark_mode",
            "Switch Windows between dark mode (true) and light mode (false).",
            dark_mode,
            {"on": {"type": "boolean"}},
            ("on",),
        )
    )
    reg.add(
        Tool(
            "empty_recycle_bin",
            "Permanently delete everything in the Recycle Bin.",
            empty_recycle_bin,
            risk=CRITICAL,
            confirm="Permanently delete everything in the Recycle Bin?",
        )
    )
    reg.add(
        Tool(
            "power",
            "Sleep, shut down or restart the laptop.",
            power,
            {"action": {"type": "string", "enum": ["sleep", "shutdown", "restart"]}},
            ("action",),
            risk=CRITICAL,
            confirm="{action} the laptop?",
        )
    )
    reg.add(
        Tool(
            "type_text",
            "Type text into the window that currently has focus (dictation). Cannot press Enter.",
            type_text,
            {"text": S},
            ("text",),
            outward=True,
            confirm="Type this into the current window: {text}",
        )
    )
    reg.add(
        Tool("clipboard_read", "Read the text on the clipboard.", clipboard_read, untrusted=True)
    )
    reg.add(
        Tool(
            "clipboard_write",
            "Put text on the clipboard.",
            clipboard_write,
            {"text": S},
            ("text",),
            outward=True,
            confirm="Copy this to the clipboard: {text}",
        )
    )
