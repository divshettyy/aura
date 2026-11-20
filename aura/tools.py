"""Tool registry. Every action Aura can take is a declared tool with a risk level."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

SAFE, CONFIRM, CRITICAL = "safe", "confirm", "critical"
RISKS = (SAFE, CONFIRM, CRITICAL)
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
MAX_STRING = 8000


class ToolError(Exception):
    """Raised by tools for expected failures; the message is safe to speak."""


@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    params: dict = field(default_factory=dict)  # JSON-schema "properties"
    required: tuple = ()
    risk: str | Callable[[dict], str] = SAFE
    outward: bool = False  # can carry information off the laptop or into another app
    untrusted: bool = False  # result contains content Aura did not author
    confirm: str = ""  # spoken confirmation, formatted with the arguments

    def risk_for(self, args: dict) -> str:
        return self.risk(args) if callable(self.risk) else self.risk

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": self.params,
            "required": list(self.required),
            "additionalProperties": False,
        }

    def validate(self, args: dict) -> dict:
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        unknown = set(args) - set(self.params)
        if unknown:
            raise ToolError(f"unknown argument(s): {', '.join(sorted(unknown))}")
        missing = [k for k in self.required if k not in args]
        if missing:
            raise ToolError(f"missing argument(s): {', '.join(missing)}")
        for key, value in args.items():
            spec = self.params[key]
            expected = _TYPES[spec["type"]]
            if (
                isinstance(value, bool)
                and spec["type"] != "boolean"
                or not isinstance(value, expected)
            ):
                raise ToolError(f"argument '{key}' must be {spec['type']}")
            if "enum" in spec and value not in spec["enum"]:
                raise ToolError(f"argument '{key}' must be one of {spec['enum']}")
            if isinstance(value, str) and len(value) > MAX_STRING:
                raise ToolError(f"argument '{key}' is too long")
            if (
                "minimum" in spec
                and value < spec["minimum"]
                or "maximum" in spec
                and value > spec["maximum"]
            ):
                raise ToolError(f"argument '{key}' is out of range")
        return args

    def confirmation(self, args: dict) -> str:
        if self.confirm:
            try:
                return self.confirm.format(**args)
            except (KeyError, IndexError):
                pass
        return f"{self.name.replace('_', ' ')} with {args}" if args else self.name.replace("_", " ")


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def add(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return [self._tools[k] for k in sorted(self._tools)]  # stable order
