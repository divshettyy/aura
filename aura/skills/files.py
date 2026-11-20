"""Files and notes. Everything is confined to the folders listed under files.roots."""

from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path

from ..config import expand
from ..tools import CONFIRM, CRITICAL, Tool, ToolError

# Opening these would run code, so Aura refuses to open them by voice.
EXECUTABLE = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".pif",
    ".msi",
    ".msp",
    ".ps1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".hta",
    ".lnk",
    ".url",
    ".reg",
    ".jar",
    ".py",
    ".pyw",
    ".sh",
    ".cpl",
    ".dll",
    ".appx",
    ".msix",
    ".application",
    ".gadget",
    ".inf",
    ".scf",
    ".chm",
    ".iso",
    ".img",
    ".vhd",
    ".vhdx",
    ".msc",
    ".wsb",
    ".diagcab",
    ".diagpkg",
    ".search-ms",
    ".library-ms",
    ".settingcontent-ms",
    ".appref-ms",
    ".website",
    ".ps1xml",
    ".psm1",
    ".psd1",
    ".wsc",
    ".sct",
    ".ws",
    ".vb",
    ".msu",
    ".mst",
    ".xll",
    ".jnlp",
    ".xbap",
    ".appinstaller",
    ".appxbundle",
    ".msixbundle",
}
TEXT = {
    ".txt",
    ".md",
    ".csv",
    ".log",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".ini",
    ".cfg",
    ".rst",
    ".tex",
}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "AppData"}


def roots(hub) -> list[Path]:
    return [expand(r).resolve() for r in hub.cfg["files"]["roots"]]


def guard(hub, path: str, must_exist: bool = True) -> Path:
    """Resolve symlinks and '..' first, then require the result to sit inside an allowed folder."""
    try:
        real = expand(path).resolve()
    except (OSError, RuntimeError):
        raise ToolError("that path is not valid")
    if not any(real == r or r in real.parents for r in roots(hub)):
        raise ToolError("that location is outside the folders I'm allowed to use")
    if must_exist and not real.exists():
        raise ToolError(f"{real.name} does not exist")
    return real


def _walk(hub):
    for root in roots(hub):
        if not root.is_dir():
            continue
        for folder, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in names:
                yield Path(folder) / name


def files_search(hub, query: str) -> str:
    words = query.lower().split()
    hits = []
    for path in _walk(hub):
        if all(w in path.name.lower() for w in words):
            hits.append(path)
            if len(hits) >= 200:
                break
    if not hits:
        return f"No files matching {query}"
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    hub.state.set("last_file", str(hits[0]))
    shown = hits[:8]
    more = f" (and {len(hits) - 8} more)" if len(hits) > 8 else ""
    return f"Found {len(hits)} file(s){more}, newest first:\n" + "\n".join(str(p) for p in shown)


def files_recent(hub) -> str:
    newest = sorted(_walk(hub), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
    if not newest:
        return "No files found"
    hub.state.set("last_file", str(newest[0]))
    return "Most recently changed:\n" + "\n".join(str(p) for p in newest)


def files_open(hub, path: str) -> str:
    real = guard(hub, path)
    if real.is_file() and real.suffix.lower() in EXECUTABLE:
        raise ToolError(f"I won't open {real.suffix} files by voice because they can run code")
    hub.platform.open_path(str(real))
    hub.state.set("last_file", str(real))
    return f"Opened {real.name}"


def files_read(hub, path: str) -> str:
    real = guard(hub, path)
    if real.suffix.lower() not in TEXT:
        raise ToolError("I can only read plain text files")
    limit = int(hub.cfg["files"]["max_read_kb"]) * 1024
    if real.stat().st_size > limit:
        raise ToolError(f"{real.name} is larger than {limit // 1024} KB, too big to read out")
    hub.state.set("last_file", str(real))
    return real.read_text(encoding="utf-8", errors="replace")


def files_move(hub, source: str, destination: str) -> str:
    src = guard(hub, source)
    dst = guard(hub, destination, must_exist=False)
    if dst.is_dir():
        dst = dst / src.name
    if dst.exists():
        raise ToolError(f"{dst.name} already exists there; I won't overwrite it")
    if not dst.parent.is_dir():
        raise ToolError("the destination folder does not exist")
    shutil.move(str(src), str(dst))
    hub.state.set("last_file", str(dst))
    return f"Moved {src.name} to {dst.parent}"


def files_delete(hub, path: str) -> str:
    real = guard(hub, path)
    if real in roots(hub):
        raise ToolError("I won't delete a whole root folder")
    hub.platform.trash(str(real))
    return f"Moved {real.name} to the Recycle Bin"


def _notes_dir(hub) -> Path:
    folder = expand(hub.cfg["files"]["notes_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def note_add(hub, text: str) -> str:
    now = dt.datetime.now()
    path = _notes_dir(hub) / f"{now:%Y-%m-%d}.md"
    with path.open("a", encoding="utf-8") as fh:
        if path.stat().st_size == 0:
            fh.write(f"# Notes for {now:%A %d %B %Y}\n\n")
        fh.write(f"- {now:%H:%M} {text.strip()}\n")
    hub.state.set("last_file", str(path))
    return "Noted"


def notes_read(hub, date: str = "") -> str:
    day = date or f"{dt.date.today():%Y-%m-%d}"
    try:
        dt.date.fromisoformat(day)
    except ValueError:
        raise ToolError("the date must look like 2026-11-13")
    path = _notes_dir(hub) / f"{day}.md"
    return path.read_text(encoding="utf-8") if path.exists() else f"No notes for {day}"


def register(reg) -> None:
    S = {"type": "string"}
    reg.add(
        Tool(
            "files_search",
            "Find files by words in their name, inside the user's allowed folders.",
            files_search,
            {"query": S},
            ("query",),
        )
    )
    reg.add(Tool("files_recent", "List the most recently changed files.", files_recent))
    reg.add(
        Tool(
            "files_open",
            "Open a file or folder with its default app (full path).",
            files_open,
            {"path": S},
            ("path",),
        )
    )
    reg.add(
        Tool(
            "files_read",
            "Read a plain-text file so it can be summarised or read out (full path).",
            files_read,
            {"path": S},
            ("path",),
            untrusted=True,
        )
    )
    reg.add(
        Tool(
            "files_move",
            "Move or rename a file (full paths). Never overwrites.",
            files_move,
            {"source": S, "destination": S},
            ("source", "destination"),
            risk=CONFIRM,
            confirm="Move {source} to {destination}?",
        )
    )
    reg.add(
        Tool(
            "files_delete",
            "Send a file or folder to the Recycle Bin (full path).",
            files_delete,
            {"path": S},
            ("path",),
            risk=CRITICAL,
            confirm="Send {path} to the Recycle Bin?",
        )
    )
    reg.add(Tool("note_add", "Add a line to today's notes file.", note_add, {"text": S}, ("text",)))
    reg.add(
        Tool(
            "notes_read",
            "Read the notes for a day (YYYY-MM-DD, default today).",
            notes_read,
            {"date": S},
        )
    )
