"""Time, reminders, routines, trusted custom commands and Aura's own controls."""
from __future__ import annotations

import ast
import datetime as dt
import math
import operator
import re
import time

from ..tools import CONFIRM, Tool, ToolError

# calculate: plain arithmetic only. The expression is parsed, never executed as code.
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
def _round(value, digits=0):
    if isinstance(digits, float) and digits.is_integer():
        digits = int(digits)
    if not isinstance(digits, int) or not -15 <= digits <= 15:  # round(7, -16000000) runs for a minute
        raise ToolError("I can round to at most 15 places")
    return round(value, digits)


_FUNCTIONS = {"sqrt": math.sqrt, "abs": abs, "round": _round, "min": min, "max": max, "floor": math.floor,
              "ceil": math.ceil, "log": math.log, "log10": math.log10, "sin": math.sin, "cos": math.cos,
              "tan": math.tan, "radians": math.radians, "degrees": math.degrees}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_LIMIT = 1e15  # numbers stay small enough that nothing here can take long or fill memory


def get_time(hub) -> str:
    return dt.datetime.now().strftime("It's %H:%M on %A, %d %B %Y")


def reminder_set(hub, text: str, minutes: int = 0, at: str = "") -> str:
    if bool(minutes) == bool(at):
        raise ToolError("give either minutes from now or a time, not both")
    if minutes:
        due = dt.datetime.now() + dt.timedelta(minutes=minutes)
    else:
        try:
            due = dt.datetime.fromisoformat(at)
        except ValueError:
            raise ToolError("the time must look like 2026-11-14T15:00")
        if due <= dt.datetime.now():
            raise ToolError("that time has already passed")
    hub.state.add_reminder(due.timestamp(), text.strip())
    same_day = due.date() == dt.date.today()
    return f"I'll remind you to {text.strip()} at {due:%H:%M}" + ("" if same_day else f" on {due:%A %d %B}")


def reminders_list(hub) -> str:
    rows = hub.state.pending_reminders()
    if not rows:
        return "No reminders pending"
    return "Reminders: " + "; ".join(
        f"number {rid}, {text}, {dt.datetime.fromtimestamp(due):%a %H:%M}" for rid, due, text in rows)


def reminder_cancel(hub, id: int) -> str:
    return "Reminder cancelled" if hub.state.cancel_reminder(id) else "I couldn't find that reminder"


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError("I can only calculate with numbers")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)) or abs(value) > _LIMIT:
        raise ToolError("that number is too large for me")
    return value


def _evaluate(node, depth: int = 0):
    if depth > 30:
        raise ToolError("that calculation is too complicated")
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _number(_UNARY[type(node.op)](_evaluate(node.operand, depth + 1)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate(node.left, depth + 1), _evaluate(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and (abs(right) > 64 or abs(left) > 1e6):
            raise ToolError("that power is too large for me")
        return _number(_BINARY[type(node.op)](left, right))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS
            and not node.keywords and 1 <= len(node.args) <= 8):
        return _number(_FUNCTIONS[node.func.id](*[_evaluate(a, depth + 1) for a in node.args]))
    raise ToolError("I can only do arithmetic: numbers, + - * / % ** and functions like sqrt")


def calculate(hub, expression: str) -> str:
    text = expression.strip().replace("^", "**").replace("\u00d7", "*").replace("\u00f7", "/")
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)  # 1,200 -> 1200; "min(3, 4)" keeps its comma
    if not text or len(text) > 200:
        raise ToolError("give me a short calculation")
    try:
        value = _evaluate(ast.parse(text, mode="eval").body)
    except ToolError:
        raise
    except ZeroDivisionError:
        raise ToolError("that divides by zero") from None
    except (SyntaxError, ValueError, TypeError, OverflowError, RecursionError, MemoryError):
        raise ToolError("I couldn't work that calculation out") from None
    if isinstance(value, float):
        value = int(value) if value.is_integer() else round(value, 6)
    return f"That is {value}"


def date_info(hub, date: str = "", add_days: int = 0) -> str:
    """Weekday of a date and how far away it is; or the date a number of days after it."""
    today = dt.date.today()
    try:
        day = dt.date.fromisoformat(date) if date else today
    except ValueError:
        raise ToolError("the date must look like 2026-12-25") from None
    if add_days:
        try:
            day = day + dt.timedelta(days=add_days)
        except OverflowError:
            raise ToolError("that date is out of range") from None
    gap = (day - today).days
    span = abs(gap)
    if span >= 730:
        length = f"about {round(span / 365.25)} years"
    elif span >= 14:
        length = f"{span} days ({span // 7} weeks and {span % 7} days)"
    else:
        length = f"{span} day{'s' if span != 1 else ''}"
    if gap == 0:
        return f"{day:%A %d %B %Y} is today"
    return f"{day:%A %d %B %Y} is in {length}" if gap > 0 else f"{day:%A %d %B %Y} was {length} ago"


def _span(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{hours} hour{'s' if hours != 1 else ''}" if hours else "",
             f"{minutes} minute{'s' if minutes != 1 else ''}" if minutes else "",
             f"{secs} second{'s' if secs != 1 else ''}" if secs or not (hours or minutes) else ""]
    return " ".join(p for p in parts if p)


def stopwatch(hub, action: str) -> str:
    started = hub.state.get("stopwatch_started")
    if action == "start":
        hub.state.set("stopwatch_started", time.time())
        return "Stopwatch started"
    if not started:
        raise ToolError("the stopwatch is not running")
    elapsed = _span(time.time() - float(started))
    if action == "stop":
        hub.state.set("stopwatch_started", None)
        return f"Stopwatch stopped at {elapsed}"
    return f"Stopwatch at {elapsed}"


def run_routine(hub, name: str, turn=None) -> str:
    return hub.automation.run_routine(name, turn)


def list_routines(hub) -> str:
    return "Routines: " + ", ".join(sorted(hub.cfg["routines"]))


def run_command(hub, name: str) -> str:
    argv = hub.cfg["commands"].get(name.lower().strip())
    if not argv:
        raise ToolError(f"there is no saved command called {name}")
    hub.platform.run_visible([str(a) for a in argv])
    return f"Running {name}"


def stop_listening(hub) -> str:
    hub.set_muted(True)
    key = hub.cfg["voice"]["hotkey_mute"].replace("+", " ")
    return f"Microphone off. Press {key} to turn me back on."


def capabilities(hub) -> str:
    return ("I can open and close apps and your websites, search them, control volume, brightness and media, "
            "lock the laptop, take screenshots, arrange windows, switch dark mode, find and open files, take "
            "notes, set reminders and timers, run a stopwatch, calculate, work out dates, type what you "
            "dictate, draft emails and calendar events, and run routines like: " + ", ".join(sorted(hub.cfg["routines"])))


def register(reg) -> None:
    S = {"type": "string"}
    reg.add(Tool("get_time", "Current local time and date.", get_time))
    reg.add(Tool("reminder_set", "Set a spoken reminder or timer: either 'minutes' from now or 'at' (local ISO time).",
                 reminder_set, {"text": S, "minutes": {"type": "integer", "minimum": 1, "maximum": 525600}, "at": S},
                 ("text",)))
    reg.add(Tool("calculate", "Exact arithmetic: + - * / % **, sqrt, round, min, max, log, sin, pi.", calculate,
                 {"expression": S}, ("expression",)))
    reg.add(Tool("date_info", "Weekday of a date (YYYY-MM-DD, default today) and days until it; add_days shifts it.",
                 date_info, {"date": S, "add_days": {"type": "integer", "minimum": -36500, "maximum": 36500}}))
    reg.add(Tool("stopwatch", "Start, check or stop a stopwatch.", stopwatch,
                 {"action": {"type": "string", "enum": ["start", "check", "stop"]}}, ("action",)))
    reg.add(Tool("reminders_list", "List pending reminders.", reminders_list))
    reg.add(Tool("reminder_cancel", "Cancel a reminder by its number.", reminder_cancel,
                 {"id": {"type": "integer"}}, ("id",)))
    reg.add(Tool("run_routine", "Run one of the user's saved routines by name.", run_routine, {"name": S}, ("name",),
                 outward=True, confirm="Run the {name} routine?"))
    reg.add(Tool("list_routines", "List saved routines.", list_routines))
    reg.add(Tool("run_command", "Run one of the user's saved trusted commands by name.", run_command,
                 {"name": S}, ("name",), risk=CONFIRM, confirm="Run the saved command {name}?"))
    reg.add(Tool("stop_listening", "Turn Aura's microphone off until the hotkey is pressed.", stop_listening))
    reg.add(Tool("capabilities", "Describe what Aura can do.", capabilities))
