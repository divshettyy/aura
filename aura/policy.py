"""Deterministic permission rules. No model output can change what these decide.

  safe      runs immediately
  confirm   needs a spoken "yes"
  critical  needs a click on an on-screen dialog (a voice alone cannot approve it)

Once a turn has read content Aura did not author (a file, a web page, clipboard),
that turn is "tainted": anything that could act on hidden instructions in that
content is moved up one level.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tools import CONFIRM, CRITICAL, RISKS, SAFE, Tool

ALLOW, VOICE, PHYSICAL, DENY = "allow", "voice", "physical", "deny"


@dataclass
class Turn:
    source: str  # "voice" | "text" | "automation"
    tainted: bool = False
    calls: int = 0


@dataclass
class Decision:
    action: str
    reason: str = ""


class Policy:
    def __init__(self, cfg: dict) -> None:
        self.overrides: dict = cfg.get("overrides") or {}
        self.max_calls: int = int(cfg.get("max_tool_calls_per_request", 12))
        bad = {k: v for k, v in self.overrides.items() if v not in RISKS + ("blocked",)}
        if bad:
            raise ValueError(f"invalid policy overrides: {bad}")

    def decide(self, tool: Tool, args: dict, turn: Turn, locked: bool = False) -> Decision:
        risk = self.overrides.get(tool.name) or tool.risk_for(args)
        if risk == "blocked":
            return Decision(DENY, "this action is blocked in your settings")
        if turn.calls >= self.max_calls:
            return Decision(DENY, "too many actions in one request")
        if locked and turn.source != "automation":
            return Decision(DENY, "the laptop is locked")
        if turn.source == "automation":
            if risk == CRITICAL or locked and risk != SAFE:
                return Decision(DENY, "automations cannot run this action unattended")
            return Decision(ALLOW)
        if risk == CRITICAL:
            return Decision(PHYSICAL)
        if risk == CONFIRM:
            return Decision(PHYSICAL if turn.tainted else VOICE)
        if turn.tainted and tool.outward:
            return Decision(VOICE)
        return Decision(ALLOW)
