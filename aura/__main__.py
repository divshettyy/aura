"""Command line: aura run | text | once | doctor | config | secret | audit"""

from __future__ import annotations

import argparse
import getpass
import logging
import logging.handlers
import sys

from . import __version__, audit, config, secrets
from .config import IS_WINDOWS

USER_CONFIG_TEMPLATE = """# Your Aura settings. Only what you put here overrides the defaults.
# See every option with:  aura config --defaults
#
# Examples (remove the leading "# " to use one):
#
# voice:
#   wake_threshold: 0.6
#
# brain:
#   claude_command: [wsl, -d, kali-linux, --, bash, -lic]   # Claude Code installed inside Kali
#
# sites:
#   muse: {url: "https://www.themuse.com"}
#
# apps:
#   vs code: {open: code, process: Code.exe}
#
# routines:
#   study time:
#     - tool: volume_set
#       args: {level: 10}
#     - tool: open_site
#       args: {name: youtube}
"""


def _logging(console: bool) -> None:
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            config.data_dir() / "aura.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    ]
    if console and sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def _single_instance():
    """Hold an exclusive lock so two Auras never fight over the microphone."""
    handle = open(config.data_dir() / "aura.lock", "w")
    try:
        if IS_WINDOWS:
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("Aura is already running.")
    return handle


def _hub(keep_warm: bool = True):
    from .brain import llm
    from .hub import Hub

    hub = Hub()
    problems = hub.automation.problems()
    if problems:
        sys.exit("Your config has problems:\n  - " + "\n  - ".join(problems))
    if not keep_warm:
        # A single request has no later request to warm up for: a spare Claude would be started
        # for nothing and then waited on while Aura exits.
        hub.cfg["brain"]["keep_warm"] = False
    hub.brain, description = llm.choose(hub)
    return hub, description


# Windows gives a key combination to one program only. When the configured one is taken,
# these are tried in order and the one in use is announced.
HOTKEY_FALLBACKS = {
    "hotkey_talk": ["ctrl+alt+j", "ctrl+shift+space", "ctrl+alt+f9"],
    "hotkey_mute": ["ctrl+alt+shift+m", "ctrl+alt+f10"],
}


def _start_hotkeys(hub, on_talk, on_mute) -> tuple[str | None, str | None, list[str]]:
    """Registers the talk and mute hotkeys. Returns (talk combination in use or None,
    mute combination in use or None, lines to show the user about anything that changed)."""
    voice = hub.cfg["voice"]
    wanted = {
        "hotkey_talk": str(voice["hotkey_talk"]).lower(),
        "hotkey_mute": str(voice["hotkey_mute"]).lower(),
    }
    outcome = (
        hub.platform.hotkeys(
            {wanted["hotkey_talk"]: on_talk, wanted["hotkey_mute"]: on_mute},
            {
                wanted[name]: [c for c in HOTKEY_FALLBACKS[name] if c not in wanted.values()]
                for name in wanted
            },
        )
        or {}
    )
    in_use, notes = {}, []
    for name, purpose in (("hotkey_talk", "push-to-talk"), ("hotkey_mute", "microphone on/off")):
        active, reason = outcome.get(wanted[name], (wanted[name], ""))
        in_use[name] = active
        if active is None:
            notes.append(
                f"WARNING: no {purpose} hotkey: {wanted[name]} is unavailable ({reason or 'unknown reason'}) "
                f"and so are the alternatives. Set voice.{name} with 'aura config'."
            )
        elif active != wanted[name]:
            notes.append(
                f"NOTE: {wanted[name]} is unavailable ({reason}); {purpose} is on {active} instead. "
                f"Set voice.{name} with 'aura config' to choose another."
            )
    return in_use["hotkey_talk"], in_use["hotkey_mute"], notes


def _microphone_info(platform) -> dict | None:
    """{"name", "muted", "level"} for the default recording device, or None when the platform cannot tell."""
    try:
        return platform.microphone()
    except Exception:
        return None


def _microphone_verdict(info: dict | None) -> tuple[bool, str]:
    """(usable, text for the user). A muted or zero-level microphone is a failure: Aura hears nothing."""
    if info is None:
        return True, ""
    name = info.get("name") or "microphone"
    if info.get("muted"):
        return False, (
            f"{name} is MUTED in Windows, so Aura cannot hear anything. Unmute it: "
            "Settings > System > Sound > Input, or the microphone key on the keyboard."
        )
    if info.get("level", 100) <= 0:
        return (
            False,
            f"{name} input level is 0 percent in Windows, so Aura cannot hear anything. Raise it in Settings > System > Sound > Input.",
        )
    return True, f"{name}, level {info.get('level')} percent, not muted"


def _signal_warning(peak: int) -> str:
    """Text for a one-second test recording whose loudest sample was `peak` (16-bit), or ''."""
    if peak <= 2:
        return (
            "a one-second test recording was silent (loudest sample "
            f"{peak} of 32767). Normal in a quiet room; if Aura never hears you, check the microphone "
            "is not muted or switched off by a keyboard key."
        )
    return ""


def cmd_run(args) -> None:
    _logging(console=True)
    lock = _single_instance()  # noqa: F841 (kept open for the life of the process)
    from .voice.listener import Listener
    from .voice.tts import Speaker

    hub, brain = _hub()
    speaker = Speaker(int(hub.cfg["voice"]["speech_rate"]))
    listener = Listener(hub, speaker)
    print("Loading speech models (the first start downloads them)...", flush=True)
    listener.load_models()
    hub.speak = speaker.say
    hub.confirm_voice = listener.confirm

    def toggle_mute() -> None:
        hub.set_muted(not hub.muted)
        hub.platform.beep("off" if hub.muted else "wake")

    talk_key, mute_key, hotkey_notes = _start_hotkeys(hub, listener.talk.set, toggle_mute)
    hub.bus.start()
    hub.automation.start()
    hub.audit.record(
        "started", version=__version__, brain=brain, hotkey_talk=talk_key, hotkey_mute=mute_key
    )
    wake = hub.cfg["voice"]["wake_word"].replace("_", " ")
    print(f"Brain: {brain}", flush=True)
    for note in hotkey_notes:
        print(note, flush=True)
    print(
        f'Say "{wake}"'
        + (f" or press {talk_key}" if talk_key else "")
        + ". "
        + (f"{mute_key} turns the microphone off/on. " if mute_key else "")
        + "Ctrl+C quits.",
        flush=True,
    )
    mic_good, mic_detail = _microphone_verdict(_microphone_info(hub.platform))
    if not mic_good:
        print(f"WARNING: {mic_detail}", flush=True)
    speaker.say("Aura is ready.")
    if not mic_good:
        speaker.say(
            "I can't hear you: the microphone is muted in Windows. Unmute it in the sound settings."
        )
    if not talk_key:
        speaker.say("The talk shortcut is not available. Use the wake word.")
    try:
        listener.run()
    except KeyboardInterrupt:
        print("\nBye.")


def _text_hub(keep_warm: bool = True):
    hub, brain = _hub(keep_warm)

    def confirm(prompt: str) -> bool:
        return input(f"Aura: {prompt} [type yes] ").strip().lower() in ("yes", "y")

    hub.confirm_voice = confirm
    return hub, brain


def cmd_text(args) -> None:
    _logging(console=False)
    hub, brain = _text_hub()
    print(f"Aura text mode. Brain: {brain}. Type a command, or 'quit'.")
    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() in ("quit", "exit"):
            break
        reply = hub.handle(line, "text")
        hub.automation.tick()
        hub.bus.dispatch_pending()
        if reply:
            print(f"Aura: {reply}")


def cmd_once(args) -> None:
    _logging(console=False)
    hub, _ = _text_hub(keep_warm=False)
    print(hub.handle(" ".join(args.words), "text"))


def cmd_hear(args) -> None:
    """Listening test: shows what the microphone, the wake word and speech-to-text pick up.
    Nothing that is said here is acted on."""
    import numpy as np
    import openwakeword
    import openwakeword.utils
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from openwakeword.model import Model

    voice = config.load()["voice"]
    name, threshold = voice["wake_word"], float(voice["wake_threshold"])
    spoken = name.replace("_", " ")
    device = sd.query_devices(kind="input")
    print(f"Microphone: {device['name']}")
    print("Loading speech models...", flush=True)
    if name in openwakeword.MODELS:
        openwakeword.utils.download_models(model_names=[name])
    wake = Model(wakeword_models=[name], inference_framework="onnx")
    whisper = WhisperModel(
        voice["stt_model"],
        device="cpu",
        compute_type="int8",
        cpu_threads=int(voice.get("stt_threads", 4)),
    )
    rate, frame, seconds = 16000, 1280, int(args.seconds)
    print(f'Listening for {seconds} seconds. Say: "{spoken}, what time is it"', flush=True)
    audio = sd.rec(seconds * rate, samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    audio = audio.reshape(-1)
    best, loudest = 0.0, 0
    for second in range(seconds):
        part = audio[second * rate : (second + 1) * rate]
        score = 0.0
        for start in range(0, len(part) - frame + 1, frame):
            score = max(score, float(max(wake.predict(part[start : start + frame]).values())))
        peak = int(np.abs(part.astype(np.int32)).max())
        best, loudest = max(best, score), max(loudest, peak)
        print(
            f"  second {second + 1:2d}: loudness {peak:5d} {'#' * min(40, peak // 400):40s} wake score {score:.2f}"
        )
    segments, _info = whisper.transcribe(
        audio.astype(np.float32) / 32768.0, language="en", beam_size=1
    )
    text = " ".join(part.text.strip() for part in segments).strip()
    print(f"Speech-to-text heard: {text!r}")
    print(
        f"Best wake score {best:.2f}; Aura wakes at {threshold:.2f} "
        f"(and double-checks from {float(voice['wake_verify_threshold']):.2f})."
    )
    if loudest < 300:
        print(
            "RESULT: no sound reached Aura. Wrong or muted microphone: check Settings > System > Sound > Input."
        )
    elif loudest < 2000:
        print(
            "RESULT: the microphone is very quiet. Move closer or raise the input level in Windows."
        )
    elif best >= threshold:
        print("RESULT: the wake word works with this microphone.")
    elif not text:
        print(
            "RESULT: sound arrived but no words were recognised. Speak after the 'Listening' line."
        )
    else:
        print(
            f"RESULT: your words were heard but the wake word scored too low. In 'aura config' set "
            f"voice.wake_threshold to {max(0.1, round(best * 0.8, 2))}, or use the push-to-talk key."
        )


def cmd_doctor(args) -> None:
    ok = True

    def report(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        ok = ok and good
        print(f"[{'ok' if good else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))

    try:
        sys.stdout.reconfigure(
            errors="replace"
        )  # a device name with an unusual symbol must not crash the report
    except Exception:
        pass
    print(f"Aura {__version__}  |  data folder: {config.data_dir()}")
    report(sys.version_info[:2] >= (3, 10), "Python", sys.version.split()[0])
    try:
        from .brain import llm
        from .hub import Hub

        hub = Hub()
        problems = hub.automation.problems()
        report(not problems, "Config, routines and rules", "; ".join(problems))
    except Exception as exc:
        report(False, "Config", str(exc))
        sys.exit(1)
    report(
        hub.platform.name == "windows",
        "Platform",
        hub.platform.name + ("" if IS_WINDOWS else " (not Windows: laptop control is simulated)"),
    )
    try:
        brain, description = llm.choose(hub)
        report(True, "Brain", description)
        if isinstance(brain, llm.ClaudeCliBrain):
            try:
                plan = brain._ask(brain._prompt("what time is it", []))
                report(
                    bool(plan["actions"] or plan["say"]),
                    "Claude subscription answers",
                    f"plan: {plan}",
                )
            except Exception as exc:
                report(
                    False,
                    "Claude subscription answers",
                    f"{exc}  (run 'claude' once and log in; if Claude Code lives in WSL set brain.claude_command)",
                )
    except Exception as exc:
        report(False, "Brain", str(exc))
    for module, purpose in [
        ("numpy", "audio"),
        ("sounddevice", "microphone"),
        ("openwakeword", "wake word"),
        ("faster_whisper", "speech-to-text"),
        ("keyring", "credential store"),
        ("psutil", "status"),
    ] + (
        [
            ("win32com.client", "speech output"),
            ("pycaw.pycaw", "volume"),
            ("screen_brightness_control", "brightness"),
            ("PIL.ImageGrab", "screenshots"),
            ("pyperclip", "clipboard"),
            ("send2trash", "recycle bin"),
        ]
        if IS_WINDOWS
        else []
    ):
        try:
            __import__(module)
            report(True, f"Library for {purpose}", module)
        except Exception as exc:
            report(False, f"Library for {purpose}", f"{module}: {exc}")
    try:
        import sounddevice as sd

        device = sd.query_devices(kind="input")
        # Windows knows the full, correctly spelled name and whether the device is muted;
        # the audio library's name is cut at 31 characters and can mangle symbols.
        info = _microphone_info(hub.platform) if IS_WINDOWS else None
        good, detail = _microphone_verdict(info)
        report(good, "Microphone", detail or str(device["name"]))
        if good:
            import numpy as np

            sample = sd.rec(16000, samplerate=16000, channels=1, dtype="int16")
            sd.wait()
            warning = _signal_warning(
                int(np.abs(sample.astype(np.int32)).max()) if len(sample) else 0
            )
            if warning:
                print(f"[warn] Microphone signal: {warning}")
    except Exception as exc:
        report(False, "Microphone", str(exc))
    for name, purpose in (("hotkey_talk", "push-to-talk"), ("hotkey_mute", "microphone on/off")):
        combo = str(hub.cfg["voice"][name]).lower()
        try:
            free, reason = hub.platform.hotkey_available(combo)
        except Exception as exc:
            free, reason = False, str(exc)
        if free:
            report(True, f"Hotkey for {purpose}", combo)
            continue
        spare = None
        for candidate in HOTKEY_FALLBACKS[name]:
            try:
                if hub.platform.hotkey_available(candidate)[0]:
                    spare = candidate
                    break
            except Exception:
                pass
        # Not a failure when a spare works: 'aura run' switches to it and says so.
        # (While Aura itself is running, its own hotkeys show up here as taken.)
        report(
            spare is not None,
            f"Hotkey for {purpose}",
            f"{combo} is unavailable ({reason}); "
            + (
                f"'aura run' will use {spare} instead"
                if spare
                else "no alternative is free, set voice." + name
            ),
        )
    good, message = audit.verify(config.data_dir() / "audit.jsonl")
    report(good, "Audit log", message)
    print("\nAll good." if ok else "\nSome checks failed; see above.")
    sys.exit(0 if ok else 1)


def cmd_config(args) -> None:
    if args.defaults:
        print(config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        return
    path = config.user_config_path()
    if not path.exists():
        path.write_text(USER_CONFIG_TEMPLATE, encoding="utf-8")
    print(path)
    if IS_WINDOWS:
        import os

        os.startfile(str(path))


def cmd_secret(args) -> None:
    if args.action == "set":
        value = getpass.getpass(f"Value for {args.name} (hidden): ").strip()
        if not value:
            sys.exit("Nothing entered; nothing stored.")
        secrets.put(args.name, value)
        print("Stored in the system credential store.")
    else:
        secrets.delete(args.name)
        print("Deleted.")


def cmd_audit(args) -> None:
    path = config.data_dir() / "audit.jsonl"
    if args.action == "verify":
        good, message = audit.verify(path)
        print(message)
        sys.exit(0 if good else 1)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    print("\n".join(lines[-args.lines :]))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="aura", description="Voice-controlled laptop assistant")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="start listening (voice mode)").set_defaults(func=cmd_run)
    sub.add_parser("text", help="type commands instead of speaking").set_defaults(func=cmd_text)
    once = sub.add_parser("once", help="run a single typed command")
    once.add_argument("words", nargs="+")
    once.set_defaults(func=cmd_once)
    sub.add_parser("doctor", help="check that everything is installed and working").set_defaults(
        func=cmd_doctor
    )
    hear = sub.add_parser("hear", help="listening test: shows what Aura hears, acts on nothing")
    hear.add_argument("--seconds", type=int, default=10, choices=range(3, 31), metavar="3-30")
    hear.set_defaults(func=cmd_hear)
    cfg = sub.add_parser("config", help="open your settings file")
    cfg.add_argument("--defaults", action="store_true", help="print every available option")
    cfg.set_defaults(func=cmd_config)
    secret = sub.add_parser("secret", help="store or delete a secret in the credential store")
    secret.add_argument("action", choices=["set", "delete"])
    secret.add_argument("name")
    secret.set_defaults(func=cmd_secret)
    aud = sub.add_parser("audit", help="show or verify the action log")
    aud.add_argument("action", choices=["tail", "verify"])
    aud.add_argument("-n", "--lines", type=int, default=20)
    aud.set_defaults(func=cmd_audit)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception:
        # with no console (started at logon) the log file is the only place this can be seen
        logging.getLogger("aura").exception("Aura stopped because of an error")
        raise


if __name__ == "__main__":
    main()
