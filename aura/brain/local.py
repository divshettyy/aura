"""Built-in phrases: instant, offline, and predictable. Anything else falls through to the model.

A sentence is handled here only if the WHOLE sentence is a known request. A sentence that merely
contains a trigger word ("what is the volume of a sphere") is left to the model.
"""

from __future__ import annotations

import datetime as dt
import re

from ..policy import Turn
from ..tools import ToolError

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
NUM = r"(\d{1,3}|[a-z]+(?:[ -][a-z]+)?)"

# Words people put in front of or behind a request that change nothing about it.
_LEAD = re.compile(
    r"^(?:(?:um+|uh+|er+|hmm+|ok|okay|so|alright|all right|right|well|now|hey|hi|hello|please|kindly|just|quickly"
    r"|(?:let's|lets)(?! play\b)|can you|could you|would you|will you|i want you to|i need you to|i'd like you to"
    r"|go ahead and|jarvis|aura)[, ]+)+"
)
_TRAIL = re.compile(r"(?:[, ]+(?:please|thanks|thank you|for me|now|right now|aura|jarvis))+$")
# Requests that end in the user's own words: only a final "please" is taken off those.
_FREE_TEXT = re.compile(
    r"(?:type|dictate|note|take a note|make a note|add a note|jot down|write down|remember"
    r"|search|google|look up|ask|remind me|set a reminder|find)\b"
)

_LITTLE = r"(?: a bit| a little| a little bit| slightly| a touch)?"
_LITTLE_FIRST = r"(?:a bit |a little |a little bit |slightly |a touch )?"
_UNITS = {"second": 1 / 60, "sec": 1 / 60, "minute": 1, "min": 1, "hour": 60, "hr": 60}
_UNIT = r"(second|sec|minute|min|hour|hr)s?"
_WHEN_WORD = r"(?:at|tomorrow|tonight|this evening|this afternoon|this morning)"
_NOT_A_FILE = re.compile(
    r"(?:out|me|us|a|an|some|someone|somebody|something|somewhere|how|who|what|when|why"
    r"|the nearest|nearest|the best|best|the cheapest|cheap)\b"
)
_FILE_WORD = re.compile(
    r"\b(?:file|files|document|documents|doc|folder|pdf|photo|photos|picture|pictures|image"
    r"|spreadsheet|presentation|resume|cv|report|invoice|receipt|screenshot|screenshots|notes?)\b"
)
_FILE_LIKE = re.compile(
    _FILE_WORD.pattern
    + r"|\.[a-z0-9]{2,4}\b|\b(?:downloads?|desktop|slides|deck|notebook|essay|thesis"
    r"|letter|contract|form|certificate|ticket|tickets|statement|manual|draft|budget|transcript|pptx?|docx?|xlsx?|csv|txt|zip|jpe?g|png|mp[34])\b"
)
_NOT_DICTATION = re.compile(
    r"of |[b-z] |a (?:personality|blood|positive|negative)\b|ab (?:positive|negative)\b"
    r"|(?:\d|one|two|three|i|ii) diabetes\b|[a-z0-9]+ (?:error|mismatch|safety|checking|inference)\b"
)
_SPLIT = re.compile(r"\s*(?:,\s*and then|,\s*then|,\s*and|,| and then | then | and also | and )\s*")


def number(text: str) -> int | None:
    text = text.strip().lower().replace("-", " ")
    if text.isdigit():
        return int(text)
    if text in ("a", "an"):
        return 1
    if text in ("max", "maximum", "full", "hundred", "one hundred", "a hundred"):
        return 100
    if text == "half":
        return 50
    words = text.split()
    if len(words) == 1 and words[0] in _ONES:
        return _ONES.index(words[0])
    if words and words[0] in _TENS:
        if len(words) == 1:
            return _TENS[words[0]]
        if len(words) == 2 and words[1] in _ONES[1:10]:
            return _TENS[words[0]] + _ONES.index(words[1])
    return None


def normalise(text: str) -> str:
    text = text.lower().strip()
    text = (
        text.replace("a.m.", "am")
        .replace("p.m.", "pm")
        .replace("%", " percent")
        .replace("per cent", "percent")
    )
    text = re.sub(r"[.!?]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    text = _LEAD.sub("", text)
    text = re.sub(r"^set (?:a |me a )?reminder ", "remind me ", text)
    if _FREE_TEXT.match(text):
        text = re.sub(r",? please$", "", text)
    else:
        text = _TRAIL.sub("", text)
    return text.strip(" ,")


def clock(text: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """'5', '5 pm', '17:30', '5:30 pm' -> the next time the clock shows that."""
    m = re.fullmatch(r"(\d{1,2})(?:[:. ](\d{2}))? ?(am|pm)?", text.strip())
    if not m:
        return None
    hour, minute, half = int(m[1]), int(m[2] or 0), m[3]
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    now = now or dt.datetime.now()
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due <= now:
        # "at 5" said at 2 pm means 5 pm; otherwise it means tomorrow
        if not half and hour < 12 and due + dt.timedelta(hours=12) > now:
            due += dt.timedelta(hours=12)
        else:
            due += dt.timedelta(days=1)
    return due


def _clock_words(text: str) -> str | None:
    """'six', 'six thirty', 'quarter past six', 'half past four', 'quarter to seven', 'noon' -> 'h:mm'."""
    text = text.replace("o'clock", "").replace("oclock", "").strip()
    if text in ("noon", "midday"):
        return "12:00"
    if text == "midnight":
        return "0:00"
    m = re.fullmatch(r"(quarter|half) (past|to) ([a-z0-9]+)", text)
    if m:
        hour = number(m[3])
        if hour is None or not 1 <= hour <= 12 or (m[1], m[2]) == ("half", "to"):
            return None
        if m[2] == "past":
            return f"{hour}:{15 if m[1] == 'quarter' else 30}"
        return f"{(hour - 2) % 12 + 1}:45"
    if re.fullmatch(r"\d{1,2}(?:[:. ]\d{2})?", text):
        return text
    words = text.split()
    if (
        not words or len(words) > 3 or (len(words) > 1 and number(text) is not None)
    ):  # "twenty five" is no time
        return None
    hour = number(words[0])
    minute = number(" ".join(words[1:])) if len(words) > 1 else 0
    if hour is None or minute is None or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return f"{hour}:{minute:02d}"


def when(text: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """A spoken point in time: 'at 6 pm', 'at quarter past six', 'tomorrow morning', 'tomorrow at 9 am',
    'tonight', 'at 6 in the evening'."""
    now = now or dt.datetime.now()
    text = f" {text.strip()} "
    tomorrow = " tomorrow " in text
    text = text.replace(" tomorrow ", " ")
    half, default = None, None
    for words, meaning, hour in (
        (("in the morning", "this morning", "morning"), "am", 9),
        (("in the afternoon", "this afternoon", "afternoon"), "pm", 15),
        (("in the evening", "this evening", "evening"), "pm", 18),
        (("tonight", "at night"), "pm", 20),
    ):
        for word in words:
            if f" {word} " in text:
                text, half, default = text.replace(f" {word} ", " "), meaning, hour
                break
    text = re.sub(r"^at ", "", " ".join(text.split()))
    m = re.fullmatch(r"(.*?) ?(am|pm)", text)
    if m:
        text, half = m[1], m[2]
    if not text:
        if default is None and not tomorrow:
            return None
        day = now + dt.timedelta(days=1) if tomorrow else now
        due = day.replace(hour=default or 9, minute=0, second=0, microsecond=0)
        return due if due > now else None
    face = _clock_words(text)
    if face is None:
        return None
    if text in ("noon", "midday", "midnight"):
        half = None
    if not tomorrow:
        return clock(f"{face} {half}" if half else face, now)
    start = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return clock(f"{face} {half}" if half else face, start - dt.timedelta(seconds=1))


def duration(text: str) -> int | None:
    """Minutes in 'twenty minutes', 'half an hour', 'an hour and a half', 'a couple of minutes', '45 mins',
    '1 hour 30 minutes', '90 seconds'. At least 1."""
    text = text.strip()
    if text in ("half an hour", "half hour", "a half hour"):
        return 30
    total = None
    m = re.fullmatch(rf"(.+?) {_UNIT} and a half", text) or re.fullmatch(
        rf"(.+?) and a half {_UNIT}", text
    )
    if m and number(m[1]):
        total = (number(m[1]) + 0.5) * _UNITS[m[2]]
    m = re.fullmatch(rf"a (couple of|few) {_UNIT}", text)
    if m:
        total = (2 if m[1] == "couple of" else 3) * _UNITS[m[2]]
    m = re.fullmatch(rf"(.+?) {_UNIT}(?: and)? (.+?) {_UNIT}", text)
    if total is None and m and number(m[1]) and number(m[3]):
        total = number(m[1]) * _UNITS[m[2]] + number(m[3]) * _UNITS[m[4]]
    m = re.fullmatch(rf"(.+?)[ -]{_UNIT}", text)
    if total is None and m and number(m[1]):
        total = number(m[1]) * _UNITS[m[2]]
    return None if total is None else max(1, round(total))


_SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000}
_MATHS = [  # spoken operator -> symbol, longest first
    (r"multiplied by|times|into", "*"),
    (r"divided by|over", "/"),
    (r"plus|added to|and", "+"),
    (r"minus|take away|less", "-"),
    (r"to the power of|to the power|raised to", "**"),
    (r"squared", "**2"),
    (r"cubed", "**3"),
    (r"x", "*"),
]


def spoken_number(words: list[str]) -> str | None:
    """['one', 'hundred', 'and', 'five'] -> '105'; ['three', 'point', 'five'] -> '3.5'; ['2.5'] -> '2.5'."""
    if len(words) == 1 and re.fullmatch(r"\d+(?:\.\d+)?", words[0]):
        return words[0]
    if "point" in words:
        cut = words.index("point")
        whole = spoken_number(words[:cut]) if cut else "0"
        digits = [
            str(_ONES.index(w)) if w in _ONES[:10] else w if w.isdigit() else None
            for w in words[cut + 1 :]
        ]
        return f"{whole}.{''.join(digits)}" if whole and digits and None not in digits else None
    total = current = 0
    seen = False
    for word in words:
        if word == "and" and seen:
            continue
        if word in ("a", "an") and not seen:
            value = 1
        elif word in _ONES:
            value = _ONES.index(word)
        elif word in _TENS:
            value = _TENS[word]
        elif word.isdigit():
            value = int(word)
        elif word in _SCALES and seen:
            scale = _SCALES[word]
            if scale == 100:
                current = max(current, 1) * 100
            else:
                total, current = total + max(current, 1) * scale, 0
            continue
        else:
            return None
        current, seen = current + value, True
    return str(total + current) if seen else None


def arithmetic(text: str) -> str | None:
    """Spoken sums as an expression for the calculate tool: 'twelve times twelve' -> '12 * 12',
    'fifteen percent of two hundred' -> '15 / 100 * 200', 'square root of 144' -> 'sqrt(144)'.
    None unless every word is a number or an operator and there is something to work out."""
    text = re.sub(
        r"(?<=\d),(?=\d{3})",
        "",
        text.replace("-", " - ") if re.search(r"\d\s*-\s*\d", text) else text.replace("-", " "),
    )
    text = re.sub(r"\bpercent of\b", " / 100 * ", text)
    text = re.sub(r"(?<=\d)\s*([+*/])\s*(?=\d)", r" \1 ", text)
    root = re.fullmatch(r"(?:the )?(square|cube) root of (.+)", text.strip())
    if root:
        inner = arithmetic(root[2]) or spoken_number(root[2].split())
        return (
            None
            if inner is None
            else f"sqrt({inner})"
            if root[1] == "square"
            else f"({inner}) ** (1 / 3)"
        )
    out, run, worked = [], [], False
    words = text.split()
    index = 0

    def flush() -> bool:
        if run:
            value = spoken_number(run)
            if value is None:
                return False
            out.append(value)
            run.clear()
        return True

    while index < len(words):
        symbol = None
        if words[index] in ("+", "-", "*", "/", "**"):
            symbol, size = words[index], 1
        else:
            for spoken, sign in _MATHS:
                for size in (4, 3, 2, 1):
                    if re.fullmatch(spoken, " ".join(words[index : index + size])):
                        symbol = sign
                        break
                if symbol:
                    break
        # "and" inside a number ("one hundred and five") is not a plus
        if symbol == "+" and words[index] == "and" and run and run[-1] in _SCALES:
            symbol = None
        if symbol and (run or out):
            if not flush():
                return None
            out.append(symbol)
            worked = True
            index += size
        else:
            run.append(words[index])
            index += 1
    if not flush() or not worked or not out or out[-1] in ("+", "-", "*", "/", "**"):
        return None
    return " ".join(out).replace(" **2", " ** 2").replace(" **3", " ** 3")


_MONTHS = {
    name: i + 1
    for i, name in enumerate(
        "january february march april may june july august september october november december".split()
    )
}
_MONTHS.update({name[:3]: i for name, i in list(_MONTHS.items())})
_ORDINALS = {
    w: i + 1
    for i, w in enumerate(
        "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth "
        "sixteenth seventeenth eighteenth nineteenth twentieth".split()
    )
}
_ORDINALS.update(
    {
        "thirtieth": 30,
        **{
            f"twenty {w}": 21 + i
            for i, w in enumerate(
                "first second third fourth fifth sixth seventh eighth ninth".split()
            )
        },
        "thirty first": 31,
    }
)
_WEEKDAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
_FIXED_DAYS = {
    "christmas": (12, 25),
    "christmas day": (12, 25),
    "christmas eve": (12, 24),
    "new year": (1, 1),
    "new year's": (1, 1),
    "new years": (1, 1),
    "new year's day": (1, 1),
    "new year's eve": (12, 31),
    "new years eve": (12, 31),
    "valentine's day": (2, 14),
    "valentines day": (2, 14),
    "halloween": (10, 31),
}


def _day_number(text: str) -> int | None:
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)$", "", text.strip().replace("-", " "))
    value = _ORDINALS.get(text) or number(text)
    return value if value and 1 <= value <= 31 else None


def spoken_date(text: str, today: dt.date | None = None) -> dt.date | None:
    """'25 december', 'december 25th 2027', 'the 3rd of march', 'christmas', 'tomorrow', 'next friday'.
    Without a year it is the next time that day comes round."""
    today = today or dt.date.today()
    text = re.sub(r"^(?:on |the )+", "", text.strip())
    text = re.sub(r" (?:this year|this time)$", "", text)
    if text in ("today", "tomorrow", "yesterday", "the day after tomorrow", "day after tomorrow"):
        return today + dt.timedelta(days={"today": 0, "tomorrow": 1, "yesterday": -1}.get(text, 2))
    m = re.fullmatch(r"(next |this |this coming )?(\w+)", text)
    if m and m[2] in _WEEKDAYS:
        ahead = (_WEEKDAYS.index(m[2]) - today.weekday()) % 7
        return today + dt.timedelta(days=ahead or 7)
    year = None
    m = re.fullmatch(r"(.+?),? ((?:19|20)\d{2})", text)
    if m:
        text, year = m[1], int(m[2])
    month = day = None
    if text in _FIXED_DAYS:
        month, day = _FIXED_DAYS[text]
    else:
        m = re.fullmatch(r"(.+?) (?:of )?([a-z]+)", text)
        if m and m[2] in _MONTHS:
            month, day = _MONTHS[m[2]], _day_number(m[1])
        else:
            m = re.fullmatch(r"([a-z]+) (?:the )?(.+)", text)
            if m and m[1] in _MONTHS:
                month, day = _MONTHS[m[1]], _day_number(m[2])
    if not month or not day:
        return None
    try:
        found = dt.date(year or today.year, month, day)
        return found if year or found >= today else dt.date(today.year + 1, month, day)
    except ValueError:
        return None


class LocalBrain:
    def __init__(self, hub) -> None:
        self.hub = hub
        r = lambda pattern: re.compile(pattern)  # noqa: E731
        self.patterns = [
            (r(r"(?:never ?mind|cancel|nothing|forget it|stop)"), lambda m: "Okay."),
            (
                r(
                    r"(?:what can you do|help|what are your commands|what can i say|what can i ask(?: you)?)"
                ),
                lambda m: ("capabilities", {}),
            ),
            (
                r(
                    r"(?:tell me |do you know |give me )?(?:what(?:'s| is) |what )?(?:the |today's )?(?:current )?(?:time|date|day)(?: is it| it is)?(?: now| today| right now)?"
                ),
                lambda m: ("get_time", {}),
            ),
            (
                r(r"(?:stop listening|go to sleep|mute yourself|microphone off|mic off)"),
                lambda m: ("stop_listening", {}),
            ),
            (
                r(r"(?:start|begin|run) (?:a |the |my )?stop ?watch|stop ?watch (?:start|on|go)"),
                lambda m: ("stopwatch", {"action": "start"}),
            ),
            (
                r(r"(?:stop|end) (?:the |my )?stop ?watch|stop ?watch (?:stop|off)"),
                lambda m: ("stopwatch", {"action": "stop"}),
            ),
            (
                r(
                    r"(?:check |read |show )?(?:the |my )?stop ?watch|how long has it been|what(?:'s| is) (?:the |my )?stop ?watch (?:at|on|showing)"
                    r"|what does (?:the |my )?stop ?watch say"
                ),
                lambda m: ("stopwatch", {"action": "check"}),
            ),
            (
                r(
                    r"(minimi[sz]e|maximi[sz]e|restore)(?: this| that| the| it| my)?(?: window| app)?"
                ),
                lambda m: (
                    "window",
                    {
                        "action": {"mini": "minimize", "maxi": "maximize", "rest": "restore"}[
                            m[1][:4]
                        ]
                    },
                ),
            ),
            (
                r(r"(?:make|put) (?:this|that|it|the window) full ?screen|full ?screen"),
                lambda m: ("window", {"action": "maximize"}),
            ),
            (
                r(
                    r"(?:show|go to|show me) (?:the |my )?desktop|minimi[sz]e (?:everything|all windows|all)"
                ),
                lambda m: ("window", {"action": "show_desktop"}),
            ),
            (
                r(
                    r"(?:(?:snap|dock)(?: this| that| it| the window| this window)?|(?:move|put) (?:this|that|it|the window|this window))(?: to| on)?(?: the)? (left|right)(?: side| half)?"
                ),
                lambda m: ("window", {"action": f"snap_{m[1]}"}),
            ),
            (
                r(
                    r"(?:turn on |switch on |enable |switch to |go to |use |set )?(?:the )?dark (?:mode|theme)(?: on)?|(?:turn off |switch off |disable )(?:the )?light (?:mode|theme)|light (?:mode|theme) off"
                ),
                lambda m: ("dark_mode", {"on": True}),
            ),
            (
                r(
                    r"(?:turn on |switch on |enable |switch to |go to |use |set )?(?:the )?light (?:mode|theme)(?: on)?|(?:turn off |switch off |disable )(?:the )?dark (?:mode|theme)|dark (?:mode|theme) off"
                ),
                lambda m: ("dark_mode", {"on": False}),
            ),
            (
                r(
                    r"(?:empty|clear|clean out|clean) (?:the |my |out the )?(?:recycle bin|recycling bin|trash|bin)"
                ),
                lambda m: ("empty_recycle_bin", {}),
            ),
            (
                r(
                    r"(?:how much |check (?:the |my )?)?(?:free |empty )?(?:disk |hard drive |drive )?(?:space|storage)(?: is| do i have| have i got)?(?: left| free| available)?(?: on (?:my |the |this )?(?:laptop|computer|pc|disk|drive|c drive))?"
                ),
                self._disk,
            ),
            (
                r(
                    r"how (?:many days|long)(?: are there| is it| do i have| is there)? (?:until|till|to|before|left until|left till) (.+)"
                ),
                self._date,
            ),
            (
                r(
                    r"what day (?:of the week )?(?:is|was|will|does)(?: it be on| it be| it)? (.+?)(?: be| fall on| on)?"
                ),
                self._date,
            ),
            (r(r"when is (.+)"), self._date),
            (
                r(
                    rf"what(?:'s| is| will be)?(?: the)? (?:date|day)(?: is it| will it be)? (?:in )?{NUM} (day|week)s?(?: from now| from today| from| time)?"
                ),
                self._date_after,
            ),
            (
                r(
                    r"(?:what(?:'s| is| are)|calculate|compute|work out|how much is|how much are|tell me)? ?(.+)"
                ),
                self._sum,
            ),
            (
                r(
                    r"(?:open|launch|start|go to|show me|show|pull up|bring up|take me to|fire up) (?:the |my |up )?(.+)"
                ),
                self._open,
            ),
            (r(r"(?:close|quit|exit|shut(?! ?down)) (?:the |my )?(.+)"), self._close),
            (
                r(
                    r"(?:find|search for|look for) (?:the |a |my )?files? (?:called |named |about )?(.+)"
                ),
                lambda m: ("files_search", {"query": m[1]}),
            ),
            (r(r"(?:search|look up|find) (?:for )?(.+?) (?:on|in) (\w+)"), self._search_on),
            (r(r"find (.+)"), self._find),
            (r(r"(?:where is|where's|where are) (.+)"), self._where),
            (r(r"search (\w+) for (.+)"), lambda m: self._search(m[1], m[2])),
            (r(r"ask (\w+) (?:about |to |for )?(.+)"), lambda m: self._search(m[1], m[2])),
            (
                r(r"(?:google|search the web for|search for|search|look up) (.+)"),
                lambda m: self._search("google", m[1]),
            ),
            (
                r(
                    r"(?:what are |show |list )?(?:my )?recent files|what (?:did|have) i (?:work|worked|been working) on (?:recently|lately|last)"
                ),
                lambda m: ("files_recent", {}),
            ),
            (
                r(
                    rf"(?:set |turn |change |put |make )?(?:the |my )?volume (up |down )?(?:by )?(?:to |at |on )?{NUM}(?: percent| points)?"
                ),
                lambda m: self._level("volume_set", m[2], m[1], "volume_change"),
            ),
            (
                r(
                    rf"(?:turn |make |put )?(?:the |it |that )?(?:volume |sound )?{_LITTLE_FIRST}(?:up|louder){_LITTLE}"
                    rf"|(?:increase|raise|boost|turn up) (?:the )?(?:volume|sound){_LITTLE}"
                ),
                lambda m: ("volume_change", {"delta": 10}),
            ),
            (
                r(
                    rf"(?:turn |make |put )?(?:the |it |that )?(?:volume |sound )?{_LITTLE_FIRST}(?:down|quieter|softer){_LITTLE}"
                    rf"|(?:decrease|lower|reduce|turn down) (?:the )?(?:volume|sound){_LITTLE}"
                ),
                lambda m: ("volume_change", {"delta": -10}),
            ),
            (
                r(r"(?:mute|silence)(?: the)?(?: volume| sound| speakers| laptop)?"),
                lambda m: ("mute", {"on": True}),
            ),
            (
                r(
                    r"unmute(?: the)?(?: volume| sound| speakers| laptop)?|(?:turn |put )?(?:the )?sound (?:back )?on"
                ),
                lambda m: ("mute", {"on": False}),
            ),
            (
                r(
                    rf"(?:set |turn |change |put |make )?(?:the |my )?(?:screen )?brightness (up |down )?(?:by )?(?:to |at |on )?{NUM}(?: percent| points)?"
                ),
                lambda m: self._level("brightness_set", m[2], m[1], "brightness_change"),
            ),
            (
                r(
                    rf"(?:make |turn )?(?:it |the screen |my screen |the display )?{_LITTLE_FIRST}brighter{_LITTLE}"
                    rf"|(?:increase|raise|turn up) (?:the )?(?:screen )?brightness{_LITTLE}|brightness up"
                ),
                lambda m: ("brightness_change", {"delta": 10}),
            ),
            (
                r(
                    rf"(?:make |turn )?(?:it |the screen |my screen |the display )?{_LITTLE_FIRST}(?:dimmer|darker){_LITTLE}"
                    rf"|dim (?:the |my )?(?:screen|display){_LITTLE}|(?:decrease|lower|reduce|turn down) (?:the )?(?:screen )?brightness{_LITTLE}"
                    rf"|brightness down"
                ),
                lambda m: ("brightness_change", {"delta": -10}),
            ),
            (
                r(
                    r"(?:play |go to )?(?:the )?(?:next|skip)(?: the| this| to the next)?(?: song| track| video| one)?|skip it"
                ),
                lambda m: ("media", {"action": "next"}),
            ),
            (
                r(
                    r"(?:play |go to )?(?:the )?(?:previous|last)(?: song| track| video| one)|previous|go back a (?:song|track|video)"
                ),
                lambda m: ("media", {"action": "previous"}),
            ),
            (
                r(
                    r"(?:play|pause|resume)(?: the)?(?: music| song| video| it)?|stop (?:the )?(?:music|song|video|playback)"
                ),
                lambda m: ("media", {"action": "play_pause"}),
            ),
            (
                r(r"lock(?: the| my)?(?: laptop| computer| screen| pc| system)?"),
                lambda m: ("lock_screen", {}),
            ),
            (
                r(
                    r"(?:take |grab |capture |get )?(?:a |me a )?screen ?shot(?: of (?:this|that|the screen|my screen))?"
                ),
                lambda m: ("screenshot", {}),
            ),
            (
                r(
                    r"(?:battery|system|laptop|wi-?fi) (?:status|level|percentage)|how much (?:battery|charge|power)(?: is left| do i have(?: left)?)?"
                    r"|how(?:'s| is) the battery|system status|what(?:'s| is) (?:my|the) battery(?: level| percentage| status)?"
                    r"|am i (?:connected to|on) (?:the )?(?:wi-?fi|internet)|is (?:the |my )?(?:wi-?fi|internet) (?:on|connected|working)"
                ),
                lambda m: (
                    "system_status",
                    {"about": "wifi"}
                    if re.search(r"wi-?fi|internet", m[0])
                    else {"about": "battery"}
                    if re.search(r"battery|charge|power", m[0])
                    else {},
                ),
            ),
            (
                r(
                    r"(shut ?down|restart|reboot|sleep|hibernate)(?: the| my)?(?: laptop| computer| pc| system)?"
                ),
                self._power,
            ),
            (
                r(r"(?:put (?:the |my )?(?:laptop|computer|pc) to sleep)"),
                lambda m: ("power", {"action": "sleep"}),
            ),
            (
                r(
                    r"(?:take a note|make a note|add a note|note that|note down|jot down|write down|remember that|remember to)[:,]? (?:that |of |to )?(.+)"
                ),
                self._note,
            ),
            (r(r"note[:,] (.+)"), self._note),
            (
                r(
                    r"(?:read |what are |show )?(?:me )?(?:my |today's )?notes(?: for today| today)?|what notes do i have|do i have any notes"
                ),
                lambda m: ("notes_read", {}),
            ),
            (r(r"remind me (.+)"), self._remind),
            (r(r"(?:set |start )?(?:a |an )?timer (?:for |of )?(.+)"), lambda m: self._timer(m[1])),
            (r(rf"(?:set |start )?(?:a |an )?(.+?[ -]{_UNIT}) timer"), lambda m: self._timer(m[1])),
            (
                r(
                    r"(?:what are |list |show |read )?(?:my )?reminders|what reminders do i have|do i have any reminders"
                ),
                lambda m: ("reminders_list", {}),
            ),
            (
                r(r"(?:type|dictate)[:,]? (.+)"),
                lambda m: None if _NOT_DICTATION.match(m[1]) else ("type_text", {"text": m[1]}),
            ),
            (
                r(r"(?:what(?:'s| is) on (?:the |my )?clipboard|read (?:the |my )?clipboard)"),
                lambda m: ("clipboard_read", {}),
            ),
            (
                r(r"(?:list |what are |show )?(?:my )?routines|what routines do i have"),
                lambda m: ("list_routines", {}),
            ),
            (
                r(r"(?:run|start|do|begin|activate)(?: the| my)? (.+?)(?: routine| mode)?"),
                self._routine,
            ),
        ]

    # helpers returning (tool, args), a reply string, or None to fall through
    def _app(self, name: str) -> str | None:
        """The name to give open_app/close_app, or None if no such app is known."""
        from ..skills.system import _resolve_app

        for candidate in (name, name.replace(" ", "")):  # speech-to-text writes "note pad"
            try:
                return _resolve_app(self.hub, candidate)[0]
            except ToolError:
                continue
        return None

    def _open(self, m):
        name = m[1].strip()
        if name in self.hub.cfg["sites"]:
            return "open_site", {"name": name}
        if self.hub.automation.find_routine(name) == name:
            return "run_routine", {"name": name}
        app = self._app(name)
        return (
            ("open_app", {"name": app}) if app else None
        )  # else maybe a file, or something for the model

    def _close(self, m):
        name = m[1].strip()
        if name in ("it", "that", "this", "that app", "this app", "that one"):
            name = self.hub.state.snapshot().get("last_app") or ""
        app = self._app(name) if name else None
        return ("close_app", {"name": app}) if app else None

    def _search(self, site, query):
        if site not in self.hub.cfg["sites"] or "search" not in self.hub.cfg["sites"][site]:
            return None
        if query.startswith("and "):  # "search and rescue dogs" is not a search request
            return None
        return "search_site", {"site": site, "query": query}

    def _search_on(self, m):
        return self._search(m[2], m[1])

    def _find(self, m):
        if _NOT_A_FILE.match(m[1]) or not _FILE_LIKE.search(
            m[1]
        ):  # "find out who won", "find nemo", "find my phone"
            return None
        return "files_search", {"query": re.sub(r"^(?:the |my )", "", m[1])}

    def _where(self, m):
        if not _FILE_LIKE.search(m[1]):  # "where is paris", "where are my keys"
            return None
        return "files_search", {"query": re.sub(r"^(?:the |my )", "", m[1])}

    def _note(self, m):
        if re.match(r"time (?:we|i|when|you)\b", m[1]):  # "remember that time we ..."
            return None
        return "note_add", {"text": m[1]}

    def _disk(self, m):
        return (
            ("system_status", {"about": "disk"})
            if re.search(r"space|storage", m[0]) and len(m[0].split()) > 1
            else None
        )

    def _date(self, m):
        day = spoken_date(m[1])
        return ("date_info", {"date": day.isoformat()}) if day else None

    def _date_after(self, m):
        count = number(m[1])
        return ("date_info", {"add_days": count * (7 if m[2] == "week" else 1)}) if count else None

    def _sum(self, m):
        expression = arithmetic(m[1])
        return ("calculate", {"expression": expression}) if expression else None

    def _level(self, tool, raw, direction=None, change_tool=None):
        raw = re.sub(r" (?:percent|points)$", "", raw)  # NUM is greedy: "seventy percent"
        value = None if raw in ("a", "an") else number(raw)
        if value is None or not 0 <= value <= 100:
            return None
        if direction:  # "volume up ten" moves it by ten, it does not set it to ten
            return change_tool, {"delta": value if direction.strip() == "up" else -value}
        return tool, {"level": value}

    def _power(self, m):
        word = m[1].replace(" ", "")
        if (
            word in ("sleep", "hibernate") and m[0].strip() == m[1]
        ):  # a bare "sleep" may be about the speaker
            return None
        return "power", {
            "action": {"shutdown": "shutdown", "restart": "restart", "reboot": "restart"}.get(
                word, "sleep"
            )
        }

    def _timer(self, spoken):
        minutes = duration(spoken)
        return (
            ("reminder_set", {"text": "your timer is up", "minutes": minutes}) if minutes else None
        )

    def _remind(self, m):
        """Everything after "remind me": the time may come first or last, as a span or as a clock time."""
        rest = m[1]
        lead = re.fullmatch(r"in (.+?) (?:to |about |that )(.+)", rest)
        if lead and duration(lead[1]):
            return "reminder_set", {"text": lead[2], "minutes": duration(lead[1])}
        lead = re.fullmatch(rf"({_WHEN_WORD}\b.*?) (?:to |about |that )(.+)", rest)
        if lead and when(lead[1]):
            return "reminder_set", {"text": lead[2], "at": when(lead[1]).strftime("%Y-%m-%dT%H:%M")}
        rest = re.sub(r"^(?:to |about |that )", "", rest)
        for cut in reversed([found.start() for found in re.finditer(r" in ", rest)]):
            minutes = duration(rest[cut + 4 :])
            if minutes and rest[:cut]:
                return "reminder_set", {"text": rest[:cut], "minutes": minutes}
        for cut in reversed([found.start() for found in re.finditer(rf" {_WHEN_WORD}\b", rest)]):
            due = when(rest[cut + 1 :])
            if due and rest[:cut]:
                return "reminder_set", {"text": rest[:cut], "at": due.strftime("%Y-%m-%dT%H:%M")}
        return None

    def _routine(self, m):
        name = self.hub.automation.find_routine(m[1])
        return ("run_routine", {"name": name}) if name else None

    # ------------------------------------------------------------------
    def _one(self, clean: str):
        routine = self.hub.automation.find_routine(clean) if clean else None
        if routine and routine == clean:
            return "run_routine", {"name": routine}
        for pattern, build in self.patterns:
            m = pattern.fullmatch(clean)
            if m:
                intent = build(m)
                if intent is not None:
                    return intent
        return None

    def match(self, text: str):
        """The one built-in request this sentence is, or None."""
        clean = normalise(text)
        intent = self._one(clean)
        if intent is None and "," in clean:  # speech-to-text writes "Volume, 40."
            intent = self._one(" ".join(clean.replace(",", " ").split()))
        return intent

    def match_all(self, text: str) -> list | None:
        """Every built-in request in this sentence, in order: usually one, several for
        "open notepad and set volume to thirty". None unless every part is a built-in request."""
        whole = self.match(text)
        if whole is not None:
            return [whole]
        parts = [part for part in _SPLIT.split(normalise(text)) if part]
        if not 2 <= len(parts) <= 5:
            return None
        intents, verb = [], ""
        for part in parts:
            intent = self.match(part)
            if intent is not None:
                verb = normalise(part).split(" ", 1)[0]
            elif verb:  # "open github and linkedin": the verb carries over
                intent = self.match(f"{verb} {part}")
            if intent is None or isinstance(intent, str):
                return None
            intents.append(intent)
        return intents

    def handle(self, text: str, turn: Turn) -> str | None:
        intents = self.match_all(text)
        if intents is None:
            return None
        if isinstance(intents[0], str):
            return intents[0]
        return " ".join(self.hub.run_tool(tool, args, turn).text for tool, args in intents)
