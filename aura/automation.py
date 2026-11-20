"""Routines (named step lists) and rules (steps that fire on an event or at a clock time)."""

from __future__ import annotations

import datetime as dt
import difflib
import logging
import threading

from .policy import Turn
from .tools import ToolError

log = logging.getLogger("aura.automation")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class _Blank(dict):
    def __missing__(self, key):
        return ""


class Automation:
    def __init__(self, hub) -> None:
        self.hub = hub
        self._fired: set[str] = set()
        self._battery_warned = False
        self._stop = threading.Event()
        for rule in hub.cfg["rules"]:
            if "event" in rule:
                hub.bus.subscribe(
                    rule["event"], lambda topic, data, r=rule: self._run_rule(r, data)
                )

    # validation ------------------------------------------------------
    def problems(self) -> list[str]:
        """Config mistakes, found at start-up instead of at 9 am on a Monday."""
        found = []

        def check(owner: str, steps) -> None:
            for step in steps or []:
                if "tool" in step:
                    tool = self.hub.tools.get(step["tool"])
                    if not tool:
                        found.append(f"{owner}: unknown tool '{step['tool']}'")
                        continue
                    try:
                        tool.validate(step.get("args") or {})
                    except ToolError as exc:
                        found.append(f"{owner}: {step['tool']}: {exc}")
                elif "routine" in step:
                    if step["routine"] not in self.hub.cfg["routines"]:
                        found.append(f"{owner}: unknown routine '{step['routine']}'")
                elif "say" not in step:
                    found.append(f"{owner}: a step needs 'say', 'tool' or 'routine'")

        for name, steps in self.hub.cfg["routines"].items():
            check(f"routine '{name}'", steps)
        for rule in self.hub.cfg["rules"]:
            label = f"rule '{rule.get('name', '?')}'"
            if ("event" in rule) == ("at" in rule):
                found.append(f"{label}: needs exactly one of 'event' or 'at'")
            if "at" in rule:
                try:
                    dt.time.fromisoformat(str(rule["at"]))
                except ValueError:
                    found.append(f"{label}: 'at' must look like \"09:00\" (with quotes)")
                bad = [d for d in rule.get("days", []) if d not in DAYS]
                if bad:
                    found.append(f"{label}: unknown day(s) {bad}")
            check(label, rule.get("do"))
        return found

    # execution -------------------------------------------------------
    def find_routine(self, name: str) -> str | None:
        key = name.lower().strip()
        routines = self.hub.cfg["routines"]
        if key in routines:
            return key
        close = difflib.get_close_matches(key, list(routines), n=1, cutoff=0.8)
        return close[0] if close else None

    def run_routine(self, name: str, turn: Turn | None = None) -> str:
        """`turn` is the live voice/text turn that asked for this routine, so its confirm-level
        steps (saved commands, moving files) can still ask a spoken "yes" per the README. Left
        None for a routine fired by a clock/event rule, where nobody is there to answer: those
        steps keep running as an "automation" turn, same as before."""
        key = self.find_routine(name)
        if not key:
            raise ToolError(f"there is no routine called {name}")
        self.hub.audit.record("routine", name=key)
        return self.run_steps(self.hub.cfg["routines"][key], {}, turn=turn) or f"{key} done"

    def run_steps(self, steps, data: dict, depth: int = 0, turn: Turn | None = None) -> str:
        if depth > 3:
            raise ToolError("routines are nested too deeply")
        spoken = []
        if turn is None:
            turn = Turn("automation")
        for step in steps or []:
            if "say" in step:
                spoken.append(str(step["say"]).format_map(_Blank(data)))
            elif "routine" in step:
                spoken.append(
                    self.run_steps(
                        self.hub.cfg["routines"].get(step["routine"]), data, depth + 1, turn
                    )
                )
            elif "tool" in step:
                result = self.hub.run_tool(step["tool"], step.get("args") or {}, turn)
                if step.get("speak") or not result.ok:
                    spoken.append(result.text)
        return " ".join(s for s in spoken if s)

    def _run_rule(self, rule: dict, data: dict) -> None:
        try:
            self.hub.audit.record("rule", name=rule.get("name"))
            text = self.run_steps(rule.get("do"), data)
            if text:
                self.hub.speak(text)
        except Exception:
            log.exception("rule %s failed", rule.get("name"))

    # clock, reminders, battery --------------------------------------
    def tick(self, now: dt.datetime | None = None) -> None:
        now = now or dt.datetime.now()
        for rid, _due, text in self.hub.state.take_due_reminders(now.timestamp()):
            self.hub.bus.publish("reminder.due", id=rid, text=text)
        stamp = now.strftime("%Y-%m-%d %H:%M")
        for index, rule in enumerate(self.hub.cfg["rules"]):
            if "at" not in rule:
                continue
            due = dt.time.fromisoformat(str(rule["at"]))
            days = rule.get("days") or DAYS
            key = f"{index} {stamp}"
            if (
                (now.hour, now.minute) == (due.hour, due.minute)
                and DAYS[now.weekday()] in days
                and key not in self._fired
            ):
                self._fired = {k for k in self._fired if k.endswith(stamp)} | {key}
                self._run_rule(rule, {})
        battery = self.hub.platform.battery()
        if battery:
            percent, plugged = battery
            low = percent <= int(self.hub.cfg["monitors"]["battery_low_percent"]) and not plugged
            if low and not self._battery_warned:
                self.hub.bus.publish("battery.low", percent=percent)
            self._battery_warned = low

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(15):
                try:
                    self.tick()
                except Exception:
                    log.exception("tick failed")

        threading.Thread(target=loop, name="aura-clock", daemon=True).start()
