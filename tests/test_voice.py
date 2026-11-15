import numpy as np

from aura.voice.listener import FRAME, Listener, strip_wake

rng = np.random.default_rng(1)
quiet = lambda: rng.normal(0, 40, FRAME).astype(np.int16)
loud = lambda: rng.normal(0, 3000, FRAME).astype(np.int16)


class FakeSpeaker:
    speaking = False

    def __init__(self):
        self.said = []

    def say(self, text, wait=True):
        self.said.append(text)


class FakeWake:
    def __init__(self):
        self.score, self.resets, self.seen = 0.0, 0, 0

    def predict(self, frame):
        self.seen += 1
        return {"hey_jarvis": self.score}

    def reset(self):
        self.resets += 1


def make(hub, transcripts):
    listener = Listener(hub, FakeSpeaker())
    listener.wake = FakeWake()
    texts = iter(transcripts)
    listener.transcribe = lambda audio: next(texts)
    utterance = lambda: [quiet()] * 3 + [loud()] * 10 + [quiet()] * 15
    feed = iter(utterance() * len(transcripts))
    listener._next = lambda: next(feed, None)
    listener._flush = lambda: None
    hub.confirm_voice = listener.confirm
    return listener


def test_wake_word_to_action(hub):
    listener = make(hub, ["Open Notepad."])
    listener.step(quiet())                       # below threshold: nothing happens
    assert not hub.platform.calls
    listener.wake.score = 0.93
    listener.step(quiet())
    assert ("launch", "notepad", "") in hub.platform.calls
    assert listener.speaker.said == ["Opened notepad"]
    assert listener.wake.resets == 1


def test_push_to_talk_and_spoken_confirmation(hub):
    listener = make(hub, ["close edge", "Yes."])
    listener.talk.set()
    listener.step(quiet())
    assert listener.speaker.said == ["Close edge? Say yes to confirm.", "Closed edge"]
    assert ("close", "msedge.exe") in hub.platform.calls


def test_anything_but_yes_cancels(hub):
    listener = make(hub, ["close edge", "yes I mean no wait"])
    listener.talk.set()
    listener.step(quiet())
    assert not [c for c in hub.platform.calls if c[0] == "close"]


def test_silence_after_wake_does_nothing(hub):
    listener = Listener(hub, FakeSpeaker())
    listener.wake = FakeWake()
    listener.wake.score = 0.9
    frames = iter([quiet()] * 80)
    listener._next = lambda: next(frames, None)
    listener._flush = lambda: None
    listener.step(quiet())
    assert listener.speaker.said == [] and not hub.platform.calls


def test_strip_wake_single_token():
    assert strip_wake("Hey Jarvis, what time is it", "hey_jarvis") == (True, "what time is it")


def test_strip_wake_name_split_across_two_tokens():
    # speech-to-text sometimes splits "jarvis" into two short tokens
    assert strip_wake("Hey jar vis, what time is it", "hey_jarvis") == (True, "what time is it")


def test_strip_wake_no_match_keeps_text_unchanged():
    assert strip_wake("Hey, John, miss. What time is it", "hey_jarvis") == (False, "Hey, John, miss. What time is it")


def test_deaf_when_muted_locked_or_speaking(hub):
    listener = make(hub, ["open notepad"] * 3)
    listener.wake.score = 0.99
    hub.muted = True
    listener.step(quiet())
    hub.muted = False
    hub.platform.locked = True
    listener.talk.set()
    listener.step(quiet())
    hub.platform.locked = False
    listener.speaker.speaking = True
    listener.step(quiet())
    assert listener.wake.seen == 0 and not hub.platform.calls and not listener.talk.is_set()


def test_strip_wake_keeps_ordinary_openings():
    for said in ("war is over", "jar is empty", "java is slow today", "art is fun", "jay is calling",
                 "hey car is ready", "ok car is here", "jar wins", "paris weather", "davis cup scores",
                 "how far is the airport", "service the printer"):
        assert strip_wake(said, "hey_jarvis") == (False, said), said


def test_strip_wake_still_takes_misheard_names():
    for said, rest in (("Jarvis open notepad", "open notepad"), ("Hey Jervis, volume up", "volume up"),
                       ("hey jarvas what time is it", "what time is it"), ("Jarvus, mute", "mute"),
                       ("ok jar vis lock the screen", "lock the screen")):
        assert strip_wake(said, "hey_jarvis") == (True, rest), said


def test_noise_floor_ignores_a_repeated_wake_phrase():
    # "hey jarvis" said three times at a low wake score put speech into most of the loudness
    # history; the floor must stay at the room's level or the command after it is never "loud".
    from aura.voice.listener import Listener

    listener = Listener.__new__(Listener)
    import collections
    listener.recent = collections.deque([40.0] * 20 + [3000.0] * 42, maxlen=62)
    assert listener._floor() < 200

