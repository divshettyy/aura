"""Websites in the browser: open, search, and pre-filled drafts the user sends themselves."""
from __future__ import annotations

import datetime as dt
import difflib
from urllib.parse import quote, urlsplit

from ..tools import CONFIRM, Tool, ToolError


def _site(hub, name: str):
    sites = hub.cfg["sites"]
    key = name.lower().strip()
    if key not in sites:
        close = difflib.get_close_matches(key, list(sites), n=1, cutoff=0.75)
        if not close:
            raise ToolError(f"I don't have a site called {name}")
        key = close[0]
    return key, sites[key]


def _go(hub, url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or '"' in url or any(c.isspace() for c in url):
        raise ToolError("that is not a valid web address")
    hub.platform.open_url(url, hub.cfg["assistant"]["browser"])


def open_site(hub, name: str) -> str:
    key, site = _site(hub, name)
    _go(hub, site["url"])
    hub.state.set("last_site", key)
    return f"Opened {key}"


def search_site(hub, site: str, query: str) -> str:
    key, spec = _site(hub, site)
    if "search" not in spec:
        raise ToolError(f"I can open {key} but it has no search link configured")
    url = spec["search"].replace("{q}", quote(query, safe="")).replace("{q_dash}", quote("-".join(query.lower().split()), safe="-"))
    _go(hub, url)
    hub.state.set("last_site", key)
    return f"Searching {key} for {query}"


def open_url(hub, url: str) -> str:
    _go(hub, url)
    return f"Opened {urlsplit(url).netloc}"


def compose_email(hub, to: str = "", subject: str = "", body: str = "") -> str:
    """Opens a Gmail draft in the browser. Aura never sends mail; the user reviews and presses Send."""
    url = "https://mail.google.com/mail/?view=cm&fs=1" + "".join(
        f"&{k}={quote(v, safe='@,')}" for k, v in (("to", to), ("su", subject), ("body", body)) if v
    )
    _go(hub, url)
    return "Email draft opened in Gmail. Review it and press Send yourself."


def calendar_draft(hub, title: str, start: str, end: str = "", details: str = "") -> str:
    """Opens a pre-filled Google Calendar event for the user to save."""
    try:
        begin = dt.datetime.fromisoformat(start)
        finish = dt.datetime.fromisoformat(end) if end else begin + dt.timedelta(hours=1)
    except ValueError:
        raise ToolError("times must look like 2026-11-14T15:00")
    if finish <= begin:
        raise ToolError("the event must end after it starts")
    fmt = "%Y%m%dT%H%M%S"
    url = (f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(title, safe='')}"
           f"&dates={begin.strftime(fmt)}/{finish.strftime(fmt)}")
    if details:
        url += f"&details={quote(details, safe='')}"
    _go(hub, url)
    return f"Calendar event '{title}' opened for {begin.strftime('%A %d %B at %H:%M')}. Press Save to keep it."


def register(reg) -> None:
    S = {"type": "string"}
    reg.add(Tool("open_site", "Open one of the user's configured websites by name (gmail, github, linkedin...).",
                 open_site, {"name": S}, ("name",)))
    reg.add(Tool("search_site", "Search a configured website, or ask a chatbot site (chatgpt, claude) a question.",
                 search_site, {"site": S, "query": S}, ("site", "query"), outward=True,
                 confirm="Search {site} for: {query}"))
    reg.add(Tool("open_url", "Open an http(s) web address in the browser.", open_url, {"url": S}, ("url",),
                 risk=CONFIRM, outward=True, confirm="Open this address: {url}"))
    reg.add(Tool("compose_email", "Open a pre-filled Gmail draft in the browser. It is NOT sent; the user sends it.",
                 compose_email, {"to": S, "subject": S, "body": S}, outward=True,
                 confirm="Open an email draft to {to}?"))
    reg.add(Tool("calendar_draft", "Open a pre-filled Google Calendar event (local ISO times) for the user to save.",
                 calendar_draft, {"title": S, "start": S, "end": S, "details": S}, ("title", "start"), outward=True,
                 confirm="Open a calendar event draft called {title}?"))
