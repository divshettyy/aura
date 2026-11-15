"""The hub wires everything together. Every action, from any source, passes through run_tool."""
from __future__ import annotations

import inspect
import logging
import threading
from dataclasses import dataclass

from . import config
from .audit import AuditLog
from .automation import Automation
from .bus import Bus
from .policy import ALLOW, DENY, PHYSICAL, VOICE, Policy, Turn
from .state import State
from .tools import Registry, ToolError

log = logging.getLogger("aura.hub")


@dataclass
class Result:
    ok: bool
    text: str
    untrusted: bool = False


class Hub:
    def __init__(self, cfg: dict | None = None, platform=None, state_path=None, audit_path=None) -> None:
        from . import platform as platform_pkg
        from .skills import files, meta, system, web

        self.cfg = cfg or config.load()
        home = config.data_dir()
        self.platform = platform or platform_pkg.load()
        self.bus = Bus()
        self.state = State(state_path or home / "state.db")
        self.audit = AuditLog(audit_path or home / "audit.jsonl")
        self.policy = Policy(self.cfg["policy"])
        self.tools = Registry()
        for skill in (system, web, files, meta):
            skill.register(self.tools)
        unknown = set(self.policy.overrides) - {t.name for t in self.tools.all()}
        if unknown:
            raise ValueError(f"policy.overrides names unknown tools: {sorted(unknown)}")
        self.automation = Automation(self)
        self.muted = False
        self._lock = threading.RLock()  # one action at a time
        # Front-ends replace these three.
        self.speak = lambda text: print(f"Aura: {text}")
        self.confirm_voice = lambda prompt: False
        self.brain = None
        from .brain.local import LocalBrain

        self.local = LocalBrain(self)

    # ------------------------------------------------------------------
    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        self.audit.record("microphone", muted=muted)
        self.bus.publish("mic.muted" if muted else "mic.unmuted")

    def run_tool(self, name: str, args: dict, turn: Turn) -> Result:
        """The single gate: validate -> policy -> confirm -> run -> audit -> announce."""
        tool = self.tools.get(name)
        if tool is None:
            return Result(False, f"There is no action called {name}.")
        try:
            args = tool.validate(dict(args or {}))
        except ToolError as exc:
            return Result(False, f"I can't do that: {exc}.")
        with self._lock:
            decision = self.policy.decide(tool, args, turn, locked=self.platform.is_locked())
            turn.calls += 1
            if decision.action == DENY:
                self.audit.record("denied", tool=name, args=args, source=turn.source, reason=decision.reason)
                return Result(False, f"Not allowed: {decision.reason}.")
            if decision.action in (VOICE, PHYSICAL):
                question = tool.confirmation(args)
                if decision.action == VOICE:
                    approved = self.confirm_voice(question + " Say yes to confirm.")
                else:
                    approved = self.platform.confirm_dialog(
                        f"Aura wants to:\n\n{question}\n\nRequested by: {turn.source}"
                        + ("\n\nWarning: this request followed content Aura read from a file, "
                           "the clipboard or the web." if turn.tainted else ""))
                self.audit.record("confirmation", tool=name, args=args, how=decision.action, approved=approved)
                if not approved:
                    return Result(False, "Cancelled; it was not confirmed.")
            try:
                # A tool that declares a `turn` parameter (currently only run_routine) gets the
                # real Turn passed through, so steps it runs itself still go through the same
                # confirm-level gate as a directly-spoken request, instead of a fresh unattended
                # "automation" turn that would skip the spoken "yes" the README promises.
                if "turn" in inspect.signature(tool.func).parameters:
                    text = str(tool.func(self, turn=turn, **args))
                else:
                    text = str(tool.func(self, **args))
            except ToolError as exc:
                self.audit.record("failed", tool=name, args=args, source=turn.source, error=str(exc))
                return Result(False, f"{exc}."[0].upper() + f"{exc}."[1:])
            except Exception as exc:
                log.exception("tool %s crashed", name)
                self.audit.record("failed", tool=name, args=args, source=turn.source, error=repr(exc))
                return Result(False, f"Something went wrong while running {name.replace('_', ' ')}.")
            if tool.untrusted:
                turn.tainted = True
            self.audit.record("ran", tool=name, args=args, source=turn.source)
            self.state.set("last_action", {"tool": name, "args": args})
            self.bus.publish(f"tool.{name}", args=args, source=turn.source)
            return Result(True, text, tool.untrusted)

    def handle(self, text: str, source: str = "voice") -> str:
        """One spoken or typed request in, one reply out."""
        text = text.strip()
        if not text:
            return ""
        turn = Turn(source)
        self.audit.record("heard", text=text, source=source)
        reply = self.local.handle(text, turn)
        if reply is None and self.brain is not None:
            try:
                reply = self.brain.handle(text, turn)
            except Exception as exc:
                log.exception("brain failed")
                reply = f"My language model isn't reachable right now ({type(exc).__name__})."
        if reply is None:
            reply = "Sorry, I didn't understand that. Say 'what can you do' for examples."
        self.audit.record("replied", text=reply)
        return reply

    def context(self) -> dict:
        """What every part of Aura currently knows; given to the language model with each request."""
        import datetime as dt

        snap = self.state.snapshot()
        return {
            "now": dt.datetime.now().strftime("%Y-%m-%dT%H:%M (%A)"),
            "last_file": snap.get("last_file"),
            "last_app": snap.get("last_app"),
            "last_site": snap.get("last_site"),
            "sites": sorted(self.cfg["sites"]),
            "routines": sorted(self.cfg["routines"]),
            "saved_commands": sorted(self.cfg["commands"]),
            "allowed_folders": [str(config.expand(r)) for r in self.cfg["files"]["roots"]],
        }
