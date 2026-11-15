"""Microphone pipeline: wake word -> record until silence -> local speech-to-text -> reply -> follow-up.

Audio never leaves the laptop. Only the recognised *text* of a request may go to the language model.

A conversation is one wake (wake word or push-to-talk) followed by any number of rounds:
the user speaks, Aura answers, and Aura keeps listening for a few seconds so the next thing
can be said without the wake word. Silence, or a word like "stop" or "thanks", ends it.
"""
from __future__ import annotations

import collections
import difflib
import logging
import queue
import re
import threading
import time

import numpy as np

log = logging.getLogger("aura.voice")

RATE = 16000
FRAME = 1280  # 80 ms, the frame size the wake-word model expects
FRAME_SECONDS = FRAME / RATE
MIN_SPEECH_RMS = 150.0  # never treat anything quieter than this as speech
YES = {"yes", "yes please", "yeah", "yep", "confirm", "confirmed", "do it", "go ahead", "yes do it", "yes go ahead", "sure"}
# Said on their own in a follow-up, these end the conversation instead of being sent as a request.
STOP = {"stop", "thanks", "thank you", "thanks a lot", "thank you very much", "ok thanks", "okay thanks", "ok thank you",
        "okay thank you", "no thanks", "no thank you", "thats all", "that is all", "thats it", "that is it", "never mind",
        "nevermind", "nothing", "nothing else", "no", "bye", "goodbye", "cancel", "im done", "done"}
# What speech-to-text tends to invent from a cough, a click or a hum. Ignored in follow-ups,
# where nothing but "some sound happened" says that the user was talking to Aura.
NOISE_TEXT = {"", "you", "the", "so", "oh", "uh", "um", "hmm", "mm", "thanks for watching", "thank you for watching"}
GREETINGS = {"hey", "hi", "hay", "he", "a", "ok", "okay", "hello", "yo", "eh", "hej", "say"}


def rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2))) if len(frame) else 0.0


def plain(text: str) -> str:
    """Lower case, letters and single spaces only: for comparing against YES / STOP."""
    return " ".join(re.sub(r"[^a-z ]", "", text.lower().replace("'", "")).split())


def _wake_parts(wake_word: str) -> tuple[set[str], str]:
    words = [w for w in re.split(r"[^a-z]+", wake_word.lower()) if w]
    return GREETINGS | set(words[:-1]), (words[-1] if words else "")


def _sounds_like(token: str, name: str, ratio: float = 0.72) -> bool:
    return bool(name) and difflib.SequenceMatcher(None, token.lower(), name).ratio() >= ratio


def mentions_wake(text: str, wake_word: str) -> bool:
    """True if the wake word's name ("jarvis" in "hey_jarvis") was recognised anywhere in text."""
    _lead, name = _wake_parts(wake_word)
    return any(_sounds_like(token, name) for token in re.findall(r"[A-Za-z']+", text))


def strip_wake(text: str, wake_word: str) -> tuple[bool, str]:
    """Remove a wake phrase from the start of a transcript: "Hey Jarvis, what time is it" ->
    (True, "what time is it"). The wake phrase is how Aura is addressed, never part of the request.

    How close a word must be to the wake name depends on how likely it is to be the wake name:
      after a greeting ("hey mavis ...")       0.72, the loose match
      as the very first word ("paris weather") 0.80, so ordinary words and names are kept
      split across two words ("jar vis")       0.92, so "jar is empty" and "war is over" are kept"""
    lead, name = _wake_parts(wake_word)
    tokens = list(re.finditer(r"[A-Za-z']+", text))
    limit = min(len(tokens), 4)
    for index in range(limit):
        if not all(t.group().lower() in lead for t in tokens[:index]):
            break
        token = tokens[index]
        end = token.end()
        matched = _sounds_like(token.group(), name, 0.72 if index else 0.8)
        if not matched and index + 1 < limit:
            pair = tokens[index + 1]
            if _sounds_like(token.group() + pair.group(), name, 0.92):
                matched, end = True, pair.end()
        if matched:
            return True, text[end:].lstrip(" ,.!?;:-").strip()
    return False, text.strip()


class Recorder:
    """Decides where a spoken command starts and ends, by loudness relative to the room's noise."""

    SHORT_SPEECH_SECONDS = 0.5   # less speech than this ("pause", "yes", a first word) ...
    SHORT_SILENCE_SECONDS = 0.9  # ... waits this long, because the speaker has probably not finished

    def __init__(self, silence_seconds: float, max_seconds: float, start_timeout: float = 4.0) -> None:
        self.silence_frames = max(1, round(silence_seconds / FRAME_SECONDS))
        self.short_silence_frames = max(self.silence_frames, round(self.SHORT_SILENCE_SECONDS / FRAME_SECONDS))
        self.short_speech_frames = round(self.SHORT_SPEECH_SECONDS / FRAME_SECONDS)
        self.max_frames = round(max_seconds / FRAME_SECONDS)
        self.start_frames = round(start_timeout / FRAME_SECONDS)

    def record(self, next_frame, noise_floor: float, start_timeout: float | None = None,
               lead: list[np.ndarray] | None = None) -> np.ndarray | None:
        """next_frame() returns an int16 frame or None when the source ends. None result = nobody spoke.
        start_timeout overrides how long to wait for the first word. lead is audio already known
        to be speech (the words that interrupted Aura); recording then counts as started."""
        threshold = max(noise_floor * 3.0, MIN_SPEECH_RMS)
        start_frames = self.start_frames if start_timeout is None else round(start_timeout / FRAME_SECONDS)
        kept: list[np.ndarray] = list(lead or [])
        started = bool(kept)
        spoken = sum(1 for f in kept if rms(f) > threshold)
        quiet, waited = 0, 0
        while len(kept) < self.max_frames:
            frame = next_frame()
            if frame is None:
                break
            loud = rms(frame) > threshold
            if not started:
                waited += 1
                kept = (kept + [frame])[-4:]  # keep a little lead-in so the first word isn't clipped
                if loud:
                    started, spoken = True, 1
                elif waited >= start_frames:
                    return None
                continue
            kept.append(frame)
            spoken += loud
            quiet = 0 if loud else quiet + 1
            # A long sentence ends on a short pause; one or two words get a longer one.
            if quiet >= (self.silence_frames if spoken > self.short_speech_frames else self.short_silence_frames):
                break
        return np.concatenate(kept) if started else None


class Listener:
    VERIFY_SECONDS = 2.0        # how much recent audio the wake double-check transcribes
    VERIFY_DELAY_FRAMES = 2      # wait 160 ms after a near-miss so the phrase is complete
    VERIFY_COOLDOWN_FRAMES = 19  # ~1.5 s between double-checks, so one near-miss is checked once
    BARGE_MIN_RMS = 400.0       # speech must be at least this loud to interrupt Aura
    BARGE_FRAMES = 3            # ... for this many frames in a row (240 ms)

    def __init__(self, hub, speaker) -> None:
        self.hub, self.speaker = hub, speaker
        self.cfg = hub.cfg["voice"]
        self.frames: queue.Queue = queue.Queue(maxsize=400)
        self.talk = threading.Event()  # set by the push-to-talk hotkey
        self.recent = collections.deque(maxlen=62)  # ~5 s of loudness history, for the room's noise floor
        self.ring = collections.deque(maxlen=round(self.VERIFY_SECONDS / FRAME_SECONDS))  # the audio just heard
        self.recorder = Recorder(float(self.cfg["silence_seconds"]), float(self.cfg["max_command_seconds"]))
        self.follow_up = bool(self.cfg.get("follow_up", True))
        self.follow_up_seconds = float(self.cfg.get("follow_up_seconds", 6))
        self.follow_up_cue = bool(self.cfg.get("follow_up_cue", True))
        barge = self.cfg.get("barge_in", "hotkey")
        self.barge_in = {True: "voice", False: "off"}.get(barge, str(barge).lower())
        self.verify_threshold = float(self.cfg.get("wake_verify_threshold", 1.0))
        self._verify_wait = 0
        self._candidate, self._candidate_score = 0, 0.0
        self.wake = None
        self.whisper = None

    # models -----------------------------------------------------------
    def load_models(self) -> None:
        import openwakeword
        import openwakeword.utils
        from faster_whisper import WhisperModel
        from openwakeword.model import Model

        name = self.cfg["wake_word"]
        if name in openwakeword.MODELS:
            openwakeword.utils.download_models(model_names=[name])  # no-op once downloaded
        self.wake = Model(wakeword_models=[name], inference_framework="onnx")
        self.whisper = WhisperModel(self.cfg["stt_model"], device="cpu", compute_type="int8",
                                    cpu_threads=int(self.cfg.get("stt_threads", 4)))
        # The first transcription pays a one-off start-up cost; pay it now, not on the first command.
        self.transcribe(np.zeros(RATE // 2, dtype=np.int16))

    def transcribe(self, audio: np.ndarray) -> str:
        # The recorder has already cut the audio to the speech, so the extra voice-detection
        # pass and timestamps are skipped, and greedy decoding is used: about twice as fast.
        _lead, name = _wake_parts(self.cfg["wake_word"])
        segments, _info = self.whisper.transcribe(audio.astype(np.float32) / 32768.0, language="en", beam_size=1,
                                                  without_timestamps=True, vad_filter=False,
                                                  condition_on_previous_text=False,
                                                  hotwords=name.capitalize() or None)
        return " ".join(s.text.strip() for s in segments).strip()

    # audio ------------------------------------------------------------
    def _on_audio(self, indata, frames, time_info, status) -> None:
        try:
            self.frames.put_nowait(np.frombuffer(bytes(indata), dtype=np.int16).copy())
        except queue.Full:
            pass  # the consumer is far behind (32 s of audio queued); the newest frame is dropped

    def _flush(self) -> None:
        while not self.frames.empty():
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break

    def _next(self):
        try:
            return self.frames.get(timeout=2)
        except queue.Empty:
            return None

    def _floor(self) -> float:
        """The room's noise level: the quiet part of the last five seconds. A wake phrase the wake
        model scored low is in this history too (said two or three times it fills most of it), so
        the middle value would be the speaker's own voice and no command would count as loud."""
        return float(np.percentile(self.recent, 20)) if self.recent else 100.0

    def capture(self, start_timeout: float | None = None, flush: bool = True,
                lead: list[np.ndarray] | None = None) -> str:
        """Record one utterance and return its text ('' if nobody spoke)."""
        if flush:
            self._flush()
        audio = self.recorder.record(self._next, self._floor(), start_timeout, lead)
        return self.transcribe(audio) if audio is not None else ""

    def confirm(self, prompt: str) -> bool:
        self.speaker.say(prompt)
        self.hub.platform.beep("wake")
        heard = plain(self.capture())
        log.info("confirmation heard: %r", heard)
        return heard in YES

    # main loop --------------------------------------------------------
    def _deaf(self) -> bool:
        """Muted, or locked: nothing is listened to, whatever else is going on."""
        if self.hub.muted:
            return True
        return not self.cfg["listen_when_locked"] and self.hub.platform.is_locked()

    def _blocked(self) -> bool:
        return self._deaf() or self.speaker.speaking

    def step(self, frame: np.ndarray) -> None:
        """Process one 80 ms frame."""
        if self._deaf():
            self.talk.clear()
            self.ring.clear()
            return
        if self.speaker.speaking:
            # Aura is talking outside a conversation (a reminder). Push-to-talk may cut it short.
            if self.talk.is_set() and self.barge_in != "off" and hasattr(self.speaker, "stop"):
                self.speaker.stop()
                self.talk.clear()
                self._converse(flush=True)
            else:
                self.talk.clear()
                self.ring.clear()
            return
        self.ring.append(frame)
        self._verify_wait = max(0, self._verify_wait - 1)
        if self.talk.is_set():
            self.talk.clear()
            self._converse(flush=True)
            return
        score = self.wake.predict(frame).get(self.cfg["wake_word"], 0.0)
        if score >= float(self.cfg["wake_threshold"]):
            self._converse(flush=False)
        elif self._candidate:
            self._candidate -= 1
            if self._candidate == 0:
                self._double_check()
        elif score >= self.verify_threshold and self._verify_wait == 0 and self.whisper is not None:
            # Close, but not sure. Let the phrase finish (two more frames), then ask speech-to-text.
            self._candidate, self._candidate_score = self.VERIFY_DELAY_FRAMES, score
        else:
            self.recent.append(rms(frame))

    def _double_check(self) -> None:
        """A near-miss on the wake word: did the last two seconds really contain it?"""
        self._verify_wait = self.VERIFY_COOLDOWN_FRAMES
        heard = self.transcribe(np.concatenate(self.ring))
        confirmed = mentions_wake(heard, self.cfg["wake_word"])
        log.info("wake score %.2f, double-check heard %r: %s", self._candidate_score, heard,
                 "wake" if confirmed else "ignored")
        if confirmed:
            self._converse(flush=False)  # keep what was said meanwhile: it may be the command

    def _converse(self, flush: bool) -> None:
        """One wake: a command, its answer, then follow-ups until the user stops talking."""
        word = self.cfg["wake_word"]
        self.hub.bus.publish("voice.wake")
        self.hub.platform.beep("wake")
        # Audio that queued up while the wake word was double-checked (two seconds or more on a
        # slow processor) is listened to first, but must not use up the time the user gets to start.
        backlog = 0.0 if flush else self.frames.qsize() * FRAME_SECONDS
        text = self.capture(flush=flush, start_timeout=self.recorder.start_frames * FRAME_SECONDS + backlog)
        addressed, rest = strip_wake(text, word)
        if addressed and not rest:
            text = self.capture(flush=False)  # only the wake phrase so far: the command comes next
            addressed, rest = strip_wake(text, word)
        text = rest
        log.info("heard: %r", text)
        if not text:
            self.hub.platform.beep("error")
        while text:
            interruption = self._say(self.hub.handle(text, "voice"))
            if not self.follow_up or self._deaf():
                break
            text = self._hear_follow_up(interruption)
        self.wake.reset()
        self._flush()
        self.ring.clear()
        self._verify_wait, self._candidate = 0, 0

    def _hear_follow_up(self, interruption: list[np.ndarray] | None) -> str:
        """What the user says next, or '' when the conversation is over."""
        if interruption:
            text = self.capture(flush=False, lead=interruption)  # they are already mid-sentence
        elif interruption is not None:
            self.hub.platform.beep("wake")  # push-to-talk cut the reply short: listen like a fresh wake
            text = self.capture()
        else:
            if self.follow_up_cue:
                self.hub.platform.beep("done")
            text = self.capture(start_timeout=self.follow_up_seconds)
        text = strip_wake(text, self.cfg["wake_word"])[1]
        said = plain(text)
        log.info("follow-up heard: %r", text)
        if said in NOISE_TEXT or said in STOP:
            return ""
        return text

    def _say(self, text: str) -> list[np.ndarray] | None:
        """Speak a reply. Returns None when it was spoken to the end, [] when push-to-talk cut it
        short, or the audio of the user's voice cutting in (the start of their next request)."""
        if not text:
            return None
        stop = getattr(self.speaker, "stop", None)
        if stop is None or self.barge_in == "off":
            self.speaker.say(text)
            return None
        self.talk.clear()
        self.speaker.say(text, wait=False)
        levels: list[float] = []
        tail: collections.deque = collections.deque(maxlen=self.BARGE_FRAMES + 2)
        loud = 0
        while self.speaker.speaking:
            if self.talk.is_set():  # push-to-talk always interrupts
                self.talk.clear()
                stop()
                self._flush()
                return []
            frame = self._next_while_speaking()
            if frame is None or len(frame) != FRAME:
                continue
            if self._deaf():
                stop()
                return None
            if self.barge_in != "voice":
                continue
            # The microphone hears a little of Aura's own voice. Learn that level from the
            # first half second, and only something clearly louder counts as the user.
            level = rms(frame)
            tail.append(frame)
            echo = float(np.percentile(levels, 90)) if len(levels) >= 6 else None
            if echo is None:
                levels.append(level)
                continue
            if level > max(self.BARGE_MIN_RMS, echo * 4.0):
                loud += 1
                if loud >= self.BARGE_FRAMES:
                    stop()
                    log.info("interrupted by voice (level %.0f, own echo %.0f)", level, echo)
                    return list(tail)
            else:
                loud = 0
                levels.append(level)
                del levels[:-60]
        return None

    def _next_while_speaking(self):
        try:
            return self.frames.get(timeout=0.1)
        except queue.Empty:
            return None

    def run(self) -> None:
        import sounddevice as sd

        while True:
            if self.hub.muted:
                time.sleep(0.3)  # microphone device is fully closed while muted
                continue
            with sd.RawInputStream(samplerate=RATE, blocksize=FRAME, dtype="int16", channels=1, callback=self._on_audio):
                while not self.hub.muted:
                    frame = self._next()
                    if frame is not None and len(frame) == FRAME:
                        self.step(frame)
            self._flush()
