"""Speech output through the voices built into Windows (SAPI). Fully offline."""
from __future__ import annotations

import queue
import sys
import threading
import time

SPEAK_ASYNC, SPEAK_PURGE = 1, 2  # SAPI SpeechVoiceSpeakFlags


class _Utterance:
    def __init__(self, text: str) -> None:
        self.text = text
        self.done = threading.Event()
        self.cancel = threading.Event()


class Speaker:
    # A single spoken reply should never last longer than this. If SAPI wedges past it, the
    # utterance is cut off and treated as finished so the listener can't be deafened forever.
    MAX_UTTERANCE_SECONDS = 60
    TAIL_SECONDS = 0.4  # stay "speaking" this long after the last word, so Aura never hears itself

    def __init__(self, rate: int = 1, voice=None) -> None:
        """voice: an object with SAPI's Speak(text, flags) and WaitUntilDone(ms), for tests.
        By default the Windows voice is created on the speech thread."""
        self.rate = rate
        self._voice = voice
        self._queue: queue.Queue = queue.Queue()
        self._pending = 0
        self._lock = threading.Lock()
        self._current: _Utterance | None = None
        self.quiet_since = time.monotonic()
        self._speak_started = 0.0  # monotonic time the current utterance began speaking
        threading.Thread(target=self._worker, name="aura-tts", daemon=True).start()

    @property
    def speaking(self) -> bool:
        """True while speaking and for a moment after, so Aura never hears itself. Bounded by
        MAX_UTTERANCE_SECONDS so a wedged SAPI call can't leave the mic blocked indefinitely."""
        if self._pending > 0 and time.monotonic() - self._speak_started < self.MAX_UTTERANCE_SECONDS:
            return True
        return time.monotonic() - self.quiet_since < self.TAIL_SECONDS

    def say(self, text: str, wait: bool = True) -> None:
        if not text:
            return
        item = _Utterance(text)
        with self._lock:
            if self._pending == 0:
                self._speak_started = time.monotonic()  # the cap counts from now, not from a stale start
            self._pending += 1
        self._queue.put(item)
        if wait:
            # Bounded so a wedged Speak can't block the caller forever; _pending is owned by
            # the worker's finally, never decremented here (that would un-block the mic mid-audio).
            item.done.wait(timeout=self.MAX_UTTERANCE_SECONDS + 5)

    def stop(self) -> None:
        """Stop talking now (the user interrupted) and drop everything still waiting to be said."""
        with self._lock:
            current = self._current
        if current is not None:
            current.cancel.set()
        with self._queue.mutex:
            for item in self._queue.queue:
                item.cancel.set()

    def _worker(self) -> None:
        voice = self._voice
        if voice is None and sys.platform == "win32":
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Rate = self.rate
        while True:
            item = self._queue.get()
            with self._lock:
                self._current = item
            self._speak_started = time.monotonic()
            try:
                if not item.cancel.is_set():
                    print(f"Aura: {item.text}", flush=True)
                    if voice is not None:
                        self._speak(voice, item)
            except Exception as exc:  # a speech failure must not take the assistant down
                print(f"(speech failed: {exc})", flush=True)
            finally:
                with self._lock:
                    self._current = None
                    self._pending = max(0, self._pending - 1)
                    self.quiet_since = time.monotonic()
                item.done.set()

    def _speak(self, voice, item: _Utterance) -> None:
        """Speak without blocking inside SAPI, so the reply can be cut short at any moment."""
        voice.Speak(item.text, SPEAK_ASYNC)
        deadline = time.monotonic() + self.MAX_UTTERANCE_SECONDS
        while not voice.WaitUntilDone(50):
            if item.cancel.is_set() or time.monotonic() > deadline:
                voice.Speak("", SPEAK_ASYNC | SPEAK_PURGE)  # empties SAPI's queue: silence at once
                break
