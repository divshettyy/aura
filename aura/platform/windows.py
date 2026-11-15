"""Windows implementation. Uses only documented Win32 / shell calls; nothing here needs admin."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)

VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, INPUT_KEYBOARD = 0x0002, 0x0004, 1
ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):  # present so the union has the size Windows expects
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
user32.MessageBoxW.restype = ctypes.c_int
# Handles and ULONG_PTR are pointer-sized: declare them so nothing is truncated to 32 bits on x64.
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.restype = wintypes.BOOL
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
user32.keybd_event.restype = None
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int  # BOOL that is -1 on error, so it must stay signed
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ULONG_PTR)]
user32.SendMessageTimeoutW.restype = ULONG_PTR

shell32 = ctypes.WinDLL("shell32", use_last_error=True)


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


shell32.SHQueryRecycleBinW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_SHQUERYRBINFO)]
shell32.SHQueryRecycleBinW.restype = ctypes.c_long  # HRESULT
shell32.SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
shell32.SHEmptyRecycleBinW.restype = ctypes.c_long  # HRESULT

SHOW = {"minimize": 6, "maximize": 3, "restore": 9}                      # SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE
WIN_KEYS = {"show_desktop": 0x44, "snap_left": 0x25, "snap_right": 0x27}  # Win+D, Win+Left, Win+Right
THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


class WindowsPlatform:
    name = "windows"

    # apps -------------------------------------------------------------
    def start_menu_apps(self) -> dict[str, str]:
        """Shortcut name -> .lnk path, from the per-user and all-users Start Menu."""
        found: dict[str, str] = {}
        for var in ("PROGRAMDATA", "APPDATA"):
            root = Path(os.environ.get(var, "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            if root.is_dir():
                for link in root.rglob("*.lnk"):
                    name = link.stem.lower()
                    if "uninstall" not in name:
                        found[name] = str(link)
        return found

    def launch(self, target: str, args: str = "") -> None:
        os.startfile(target, arguments=args) if args else os.startfile(target)

    def close_process(self, process: str) -> int:
        import psutil

        closed = 0
        for proc in psutil.process_iter(["name"]):
            if (proc.info["name"] or "").lower() == process.lower():
                try:
                    proc.terminate()  # asks the app to exit; unsaved-work prompts still appear for most apps
                    closed += 1
                except psutil.Error:
                    pass
        return closed

    def open_url(self, url: str, browser: str) -> None:
        if browser == "edge":
            # the URL is passed as a single quoted argument straight to Edge, not through a shell
            try:
                os.startfile("msedge", arguments=f'"{url}"')
                return
            except OSError:
                pass  # Edge missing or renamed: use the default browser instead
        if not webbrowser.open(url):
            raise OSError("no web browser could be started")

    def open_path(self, path: str) -> None:
        os.startfile(path)

    # audio / display --------------------------------------------------
    def _endpoint(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        device = AudioUtilities.GetSpeakers()
        endpoint = getattr(device, "EndpointVolume", None)  # newer pycaw
        if endpoint is None:
            iface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            endpoint = ctypes.cast(iface, ctypes.POINTER(IAudioEndpointVolume))
        return endpoint

    def get_volume(self) -> int:
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, percent: int) -> None:
        self._endpoint().SetMasterVolumeLevelScalar(max(0, min(100, percent)) / 100, None)

    def set_mute(self, on: bool) -> None:
        self._endpoint().SetMute(1 if on else 0, None)

    def microphone(self) -> dict:
        """The default recording device as Windows sees it: {"name", "muted", "level"} (level 0-100).
        Read-only: Aura reports a muted microphone, it never unmutes one. Raises if there is none."""
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        device = AudioUtilities.GetMicrophone()
        if device is None:
            raise OSError("Windows has no default recording device")
        iface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        endpoint = ctypes.cast(iface, ctypes.POINTER(IAudioEndpointVolume))
        try:
            name = AudioUtilities.CreateDevice(device).FriendlyName or "microphone"
        except Exception:
            name = "microphone"
        return {"name": name, "muted": bool(endpoint.GetMute()),
                "level": round(endpoint.GetMasterVolumeLevelScalar() * 100)}

    def get_brightness(self) -> int:
        import screen_brightness_control as sbc

        levels = sbc.get_brightness()
        return int(levels[0] if isinstance(levels, (list, tuple)) else levels)

    def set_brightness(self, percent: int) -> None:
        import screen_brightness_control as sbc

        sbc.set_brightness(max(0, min(100, percent)))

    def media_key(self, action: str) -> None:
        vk = VK[action]
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    # session ----------------------------------------------------------
    def lock(self) -> None:
        user32.LockWorkStation()

    def is_locked(self) -> bool:
        # While locked, the input desktop is the secure desktop and cannot be opened.
        handle = user32.OpenInputDesktop(0, False, 0x0100)
        if not handle:
            return True
        user32.CloseDesktop(handle)
        return False

    def screenshot(self, path: str) -> None:
        from PIL import ImageGrab

        ImageGrab.grab(all_screens=True).save(path)

    def power(self, action: str) -> None:
        quiet = subprocess.CREATE_NO_WINDOW  # no console flash
        if action == "sleep":
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], creationflags=quiet)
        elif action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "30"], creationflags=quiet)  # 30 s grace; "shutdown /a" cancels
        elif action == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "30"], creationflags=quiet)
        else:
            raise ValueError(action)

    def battery(self):
        import psutil

        b = psutil.sensors_battery()
        return (round(b.percent), bool(b.power_plugged)) if b else None

    def wifi_name(self):
        try:
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True,
                                 timeout=5, creationflags=subprocess.CREATE_NO_WINDOW).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        for line in out.splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "SSID":
                return value.strip() or None
        return None

    def battery_minutes(self):
        """Minutes of battery left, or None when plugged in or Windows has no estimate yet."""
        import psutil

        b = psutil.sensors_battery()
        if not b or b.power_plugged or b.secsleft is None or b.secsleft < 0:
            return None
        return int(b.secsleft // 60)

    def disk_free(self):
        """(free, total) of the system drive in whole gigabytes."""
        try:
            usage = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        except OSError:
            return None
        return (usage.free // 2**30, usage.total // 2**30)

    # windows / appearance ---------------------------------------------
    def window(self, action: str) -> None:
        """Arranges the foreground window, or sends one fixed Windows-key shortcut. The shortcut is
        chosen from WIN_KEYS by name; no key code ever comes from a request."""
        if action in SHOW:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                raise OSError("no foreground window")
            user32.ShowWindow(hwnd, SHOW[action])
            return
        vk, win = WIN_KEYS[action], 0x5B  # VK_LWIN
        user32.keybd_event(win, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(win, 0, KEYEVENTF_KEYUP, 0)

    def get_dark_mode(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_KEY) as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except OSError:
            return False

    def set_dark_mode(self, on: bool) -> None:
        """Per-user setting, the same two values the Settings app writes; no admin needed."""
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, THEME_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0 if on else 1)
        result = ULONG_PTR(0)  # tell running programs the colours changed: HWND_BROADCAST, WM_SETTINGCHANGE
        user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet", 0x0002, 200, ctypes.byref(result))

    def recycle_bin_count(self) -> int:
        info = _SHQUERYRBINFO(cbSize=ctypes.sizeof(_SHQUERYRBINFO))
        if shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
            raise OSError("Windows would not report on the Recycle Bin")
        return int(info.i64NumItems)

    def empty_recycle_bin(self) -> int:
        """Empties every drive's Recycle Bin; returns how many items were deleted."""
        count = self.recycle_bin_count()
        if count:
            # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND: Aura's own dialog already asked
            if shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4) != 0:
                raise OSError("Windows could not empty the Recycle Bin")
        return count

    # input / clipboard ------------------------------------------------
    def type_text(self, text: str) -> None:
        """Types into the focused window as Unicode characters. Never sends Enter or shortcuts."""
        units = text.encode("utf-16-le")
        for i in range(0, len(units), 2):
            code = int.from_bytes(units[i:i + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                event = _INPUT(type=INPUT_KEYBOARD)
                event.u.ki = _KEYBDINPUT(0, code, flags, 0, 0)
                sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT))
                if sent != 1:  # UIPI blocks input to an elevated focused window; don't claim success
                    raise OSError("keystroke was blocked (the focused window may be running as administrator)")

    def clipboard_get(self) -> str:
        import pyperclip

        return pyperclip.paste() or ""

    def clipboard_set(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)

    # human-presence confirmation -------------------------------------
    def confirm_dialog(self, text: str) -> bool:
        MB_YESNO, MB_ICONWARNING, MB_DEFBUTTON2 = 0x4, 0x30, 0x100
        MB_SYSTEMMODAL, MB_SETFOREGROUND = 0x1000, 0x10000
        flags = MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_SYSTEMMODAL | MB_SETFOREGROUND
        return user32.MessageBoxW(None, text, "Aura - confirm this action", flags) == 6  # IDYES

    def beep(self, kind: str) -> None:
        import winsound

        tones = {"wake": [(880, 90)], "done": [(660, 70)], "error": [(330, 160)], "off": [(520, 80), (390, 120)]}
        for freq, ms in tones.get(kind, []):
            winsound.Beep(freq, ms)

    def trash(self, path: str) -> None:
        from send2trash import send2trash

        send2trash(path)

    def run_visible(self, argv: list[str]) -> None:
        subprocess.Popen(argv, creationflags=subprocess.CREATE_NEW_CONSOLE)

    # global hotkeys ---------------------------------------------------
    @staticmethod
    def _parse_hotkey(combo: str) -> tuple[int, int]:
        """'ctrl+alt+space' -> (modifier flags, virtual key). Raises ValueError for an unknown key."""
        mods = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
        keys = {"space": 0x20, **{f"f{n}": 0x6F + n for n in range(1, 13)}}
        *modifiers, key = [part.strip() for part in combo.lower().split("+")]
        flags = 0x4000  # MOD_NOREPEAT
        for m in modifiers:
            if m not in mods:
                raise ValueError(f"unknown modifier '{m}' in hotkey '{combo}'")
            flags |= mods[m]
        if key in keys:
            return flags, keys[key]
        if len(key) == 1 and key.isalnum():
            return flags, ord(key.upper())
        raise ValueError(f"unknown key '{key}' in hotkey '{combo}'")

    @staticmethod
    def _hotkey_error(code: int) -> str:
        if code == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
            return "another program already uses this key combination"
        return f"Windows refused it (error {code})"

    def hotkey_available(self, combo: str) -> tuple[bool, str]:
        """Can this combination be registered right now? (Registers and releases it at once.)"""
        try:
            flags, vk = self._parse_hotkey(combo)
        except ValueError as exc:
            return False, str(exc)
        if user32.RegisterHotKey(None, 0x3FFF, flags, vk):
            user32.UnregisterHotKey(None, 0x3FFF)
            return True, ""
        return False, self._hotkey_error(ctypes.get_last_error())

    def hotkeys(self, bindings: dict, fallbacks: dict | None = None) -> dict:
        """bindings: {"ctrl+alt+m": callback}; fallbacks: {"ctrl+alt+m": ["ctrl+alt+f10", ...]} are
        tried in order when the configured combination cannot be registered (Windows gives a
        combination to one program only). Runs a message loop on its own thread.

        Returns {configured combination: (combination in use or None, reason it was not the
        configured one)} so the caller can tell the user what actually works."""
        fallbacks = fallbacks or {}
        result: dict = {}
        registered = threading.Event()

        def loop() -> None:
            callbacks = {}
            for index, (combo, callback) in enumerate(bindings.items(), 1):
                reason = ""
                for candidate in [combo, *fallbacks.get(combo, [])]:
                    try:
                        flags, vk = self._parse_hotkey(candidate)
                    except ValueError as exc:
                        reason = reason or str(exc)
                        continue
                    if user32.RegisterHotKey(None, index, flags, vk):
                        callbacks[index] = callback
                        result[combo] = (candidate, reason)
                        break
                    reason = reason or self._hotkey_error(ctypes.get_last_error())
                else:
                    result[combo] = (None, reason)
            registered.set()
            msg = wintypes.MSG()
            errors = 0
            while True:
                got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if got == 0:  # WM_QUIT
                    break
                if got == -1:  # GetMessage error: back off, and give up if it persists
                    errors += 1                 # (don't busy-spin a core on a stuck message pump)
                    if errors > 20:
                        break
                    time.sleep(0.1)
                    continue
                errors = 0
                if msg.message == 0x0312 and msg.wParam in callbacks:  # WM_HOTKEY
                    threading.Thread(target=callbacks[msg.wParam], daemon=True).start()

        threading.Thread(target=loop, name="aura-hotkeys", daemon=True).start()
        registered.wait(timeout=3)
        return {combo: result.get(combo, (None, "registration did not finish")) for combo in bindings}
