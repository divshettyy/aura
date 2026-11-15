"""Event bus: the one channel every part of Aura uses to tell the others what happened."""
from __future__ import annotations

import logging
import queue
import threading
from collections import defaultdict
from typing import Callable

log = logging.getLogger("aura.bus")
Handler = Callable[[str, dict], None]


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def subscribe(self, topic: str, handler: Handler) -> None:
        """topic is an exact name ("battery.low"), a prefix ("tool.*") or "*"."""
        with self._lock:
            self._subs[topic].append(handler)

    def publish(self, topic: str, **data) -> None:
        self._queue.put((topic, data))

    def _handlers(self, topic: str) -> list[Handler]:
        with self._lock:
            found = list(self._subs.get(topic, [])) + list(self._subs.get("*", []))
            for pattern, handlers in self._subs.items():
                if pattern.endswith(".*") and topic.startswith(pattern[:-1]):
                    found += handlers
        return found

    def dispatch_pending(self) -> None:
        """Deliver everything queued so far (used directly by tests and text mode)."""
        while True:
            try:
                topic, data = self._queue.get_nowait()
            except queue.Empty:
                return
            self._deliver(topic, data)

    def _deliver(self, topic: str, data: dict) -> None:
        for handler in self._handlers(topic):
            try:
                handler(topic, data)
            except Exception:  # one bad subscriber must not silence the rest
                log.exception("handler failed for %s", topic)

    def start(self) -> None:
        def loop() -> None:
            while True:
                item = self._queue.get()
                if item is None:
                    return
                self._deliver(*item)

        self._thread = threading.Thread(target=loop, name="aura-bus", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
