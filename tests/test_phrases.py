"""A battery of things people really say, checked against the built-in phrases.

MATCH: must be handled by a built-in phrase, with this tool and at least these arguments.
          A built-in phrase answers in well under a second; the language model takes several.
BRAIN: must NOT be handled by a built-in phrase. These only contain a trigger word; firing an
          action on them would be wrong, so they go to the language model.
SEVERAL: one sentence, more than one action.
"""

import pytest

T = "get_time"
MATCH = [
    # time and date
    ("what time is it", T, {}),
    ("What's the time?", T, {}),
    ("could you please tell me the time", T, {}),
    ("um what time is it now", T, {}),
    ("what is the date today", T, {}),
    ("what day is it", T, {}),
    ("do you know what time it is", T, {}),
    ("what's today's date", T, {}),
    ("time please", T, {}),
    ("okay so what's the date", T, {}),
    # apps
    ("open notepad", "open_app", {"name": "notepad"}),
    ("Open Notepad.", "open_app", {"name": "notepad"}),
    ("could you please open notepad", "open_app", {"name": "notepad"}),
    ("okay so open the calculator", "open_app", {"name": "calculator"}),
    ("launch notepad for me", "open_app", {"name": "notepad"}),
    ("open up notepad", "open_app", {"name": "notepad"}),
    ("can you open notepad please", "open_app", {"name": "notepad"}),
    ("uh start file explorer", "open_app", {"name": "file explorer"}),
    ("open note pad", "open_app", {"name": "notepad"}),
    ("open notepad thanks", "open_app", {"name": "notepad"}),
    ("i need you to open the terminal", "open_app", {"name": "terminal"}),
    ("close notepad", "close_app", {"name": "notepad"}),
    ("quit edge please", "close_app", {"name": "edge"}),
    ("shut notepad", "close_app", {"name": "notepad"}),
    # sites
    ("open gmail", "open_site", {"name": "gmail"}),
    ("go to github", "open_site", {"name": "github"}),
    ("open my calendar", "open_site", {"name": "calendar"}),
    ("pull up youtube", "open_site", {"name": "youtube"}),
    ("bring up linkedin", "open_site", {"name": "linkedin"}),
    ("open gmail for me", "open_site", {"name": "gmail"}),
    ("take me to github", "open_site", {"name": "github"}),
    ("hey aura open gmail", "open_site", {"name": "gmail"}),
    # site search
    (
        "search for data analyst on linkedin",
        "search_site",
        {"site": "linkedin", "query": "data analyst"},
    ),
    ("search github for whisper", "search_site", {"site": "github", "query": "whisper"}),
    (
        "google python list comprehension",
        "search_site",
        {"site": "google", "query": "python list comprehension"},
    ),
    ("look up weather in mumbai", "search_site", {"site": "google", "query": "weather in mumbai"}),
    ("search youtube for lo-fi music", "search_site", {"site": "youtube", "query": "lo-fi music"}),
    (
        "ask chatgpt how do i reverse a list",
        "search_site",
        {"site": "chatgpt", "query": "how do i reverse a list"},
    ),
    (
        "ask claude about rust lifetimes",
        "search_site",
        {"site": "claude", "query": "rust lifetimes"},
    ),
    ("please search for whisper on github", "search_site", {"site": "github", "query": "whisper"}),
    (
        "find data analyst jobs on linkedin",
        "search_site",
        {"site": "linkedin", "query": "data analyst jobs"},
    ),
    (
        "search the web for cheap flights",
        "search_site",
        {"site": "google", "query": "cheap flights"},
    ),
    # volume
    ("volume 40", "volume_set", {"level": 40}),
    ("Volume, 40.", "volume_set", {"level": 40}),
    ("set the volume to forty", "volume_set", {"level": 40}),
    ("volume to 40 percent", "volume_set", {"level": 40}),
    ("set volume to 30 per cent", "volume_set", {"level": 30}),
    ("set volume at twenty five", "volume_set", {"level": 25}),
    ("turn the volume to max", "volume_set", {"level": 100}),
    ("put the volume on fifty", "volume_set", {"level": 50}),
    ("volume fifty", "volume_set", {"level": 50}),
    ("make the volume 20%", "volume_set", {"level": 20}),
    ("turn the volume up", "volume_change", {"delta": 10}),
    ("louder", "volume_change", {"delta": 10}),
    ("make it louder", "volume_change", {"delta": 10}),
    ("a bit louder", "volume_change", {"delta": 10}),
    ("volume up", "volume_change", {"delta": 10}),
    ("increase the volume", "volume_change", {"delta": 10}),
    ("raise the volume", "volume_change", {"delta": 10}),
    ("turn it up a little", "volume_change", {"delta": 10}),
    ("turn it down", "volume_change", {"delta": -10}),
    ("quieter", "volume_change", {"delta": -10}),
    ("lower the volume", "volume_change", {"delta": -10}),
    ("turn the volume down a bit", "volume_change", {"delta": -10}),
    ("volume down please", "volume_change", {"delta": -10}),
    ("mute", "mute", {"on": True}),
    ("mute the sound", "mute", {"on": True}),
    ("alright mute", "mute", {"on": True}),
    ("unmute", "mute", {"on": False}),
    ("turn the sound back on", "mute", {"on": False}),
    # brightness
    ("brightness 70", "brightness_set", {"level": 70}),
    ("set brightness to seventy percent", "brightness_set", {"level": 70}),
    ("screen brightness to 50", "brightness_set", {"level": 50}),
    ("brightness seventy per cent", "brightness_set", {"level": 70}),
    ("turn the brightness to full", "brightness_set", {"level": 100}),
    # media
    ("pause", "media", {"action": "play_pause"}),
    ("pause the music", "media", {"action": "play_pause"}),
    ("play", "media", {"action": "play_pause"}),
    ("resume", "media", {"action": "play_pause"}),
    ("stop the music", "media", {"action": "play_pause"}),
    ("next song", "media", {"action": "next"}),
    ("skip this song", "media", {"action": "next"}),
    ("next", "media", {"action": "next"}),
    ("play the next one", "media", {"action": "next"}),
    ("previous track", "media", {"action": "previous"}),
    ("go back a song", "media", {"action": "previous"}),
    ("play the previous song", "media", {"action": "previous"}),
    # system
    ("take a screenshot", "screenshot", {}),
    ("screenshot", "screenshot", {}),
    ("grab a screenshot please", "screenshot", {}),
    ("take a screen shot of this", "screenshot", {}),
    ("lock the laptop", "lock_screen", {}),
    ("lock my computer", "lock_screen", {}),
    ("lock", "lock_screen", {}),
    ("battery status", "system_status", {"about": "battery"}),
    ("how much battery do i have", "system_status", {"about": "battery"}),
    ("how's the battery", "system_status", {"about": "battery"}),
    ("what's my battery level", "system_status", {"about": "battery"}),
    ("battery percentage", "system_status", {"about": "battery"}),
    ("how much charge is left", "system_status", {"about": "battery"}),
    ("am i connected to wifi", "system_status", {"about": "wifi"}),
    ("shut down", "power", {"action": "shutdown"}),
    ("restart the laptop", "power", {"action": "restart"}),
    ("put the laptop to sleep", "power", {"action": "sleep"}),
    ("shut down the computer please", "power", {"action": "shutdown"}),
    ("what's on my clipboard", "clipboard_read", {}),
    ("read the clipboard", "clipboard_read", {}),
    # files
    ("find my resume", "files_search", {"query": "resume"}),
    ("where is my resume", "files_search", {"query": "resume"}),
    ("where's the budget spreadsheet", "files_search", {"query": "budget spreadsheet"}),
    ("find the file called budget", "files_search", {"query": "budget"}),
    ("look for files about taxes", "files_search", {"query": "taxes"}),
    ("recent files", "files_recent", {}),
    ("show my recent files", "files_recent", {}),
    ("what did i work on recently", "files_recent", {}),
    # notes
    ("take a note: call the recruiter", "note_add", {"text": "call the recruiter"}),
    ("note that the meeting moved to friday", "note_add", {"text": "the meeting moved to friday"}),
    ("make a note to buy milk", "note_add", {"text": "buy milk"}),
    ("write down call the bank", "note_add", {"text": "call the bank"}),
    ("add a note call mom back", "note_add", {"text": "call mom back"}),
    (
        "jot down the wifi password is on the fridge",
        "note_add",
        {"text": "the wifi password is on the fridge"},
    ),
    ("read my notes", "notes_read", {}),
    ("what are my notes", "notes_read", {}),
    ("read me my notes please", "notes_read", {}),
    ("what notes do i have", "notes_read", {}),
    # reminders and timers
    ("remind me to stretch in 20 minutes", "reminder_set", {"text": "stretch", "minutes": 20}),
    ("Remind me to stretch in twenty minutes.", "reminder_set", {"text": "stretch", "minutes": 20}),
    (
        "remind me in ten minutes to check the oven",
        "reminder_set",
        {"text": "check the oven", "minutes": 10},
    ),
    ("remind me to stretch in half an hour", "reminder_set", {"text": "stretch", "minutes": 30}),
    (
        "remind me in an hour to call the bank",
        "reminder_set",
        {"text": "call the bank", "minutes": 60},
    ),
    (
        "remind me to drink water in two hours",
        "reminder_set",
        {"text": "drink water", "minutes": 120},
    ),
    (
        "remind me in 2 hours to drink water",
        "reminder_set",
        {"text": "drink water", "minutes": 120},
    ),
    ("remind me to call in 90 seconds", "reminder_set", {"text": "call", "minutes": 2}),
    ("set a reminder to stretch in 20 minutes", "reminder_set", {"text": "stretch", "minutes": 20}),
    (
        "remind me to check the oven in an hour and a half",
        "reminder_set",
        {"text": "check the oven", "minutes": 90},
    ),
    (
        "remind me to send the invoice in 45 mins",
        "reminder_set",
        {"text": "send the invoice", "minutes": 45},
    ),
    (
        "remind me to stand up in a couple of minutes",
        "reminder_set",
        {"text": "stand up", "minutes": 2},
    ),
    ("set a timer for five minutes", "reminder_set", {"minutes": 5}),
    ("timer 10 minutes", "reminder_set", {"minutes": 10}),
    ("start a ten minute timer", "reminder_set", {"minutes": 10}),
    ("set a timer for half an hour", "reminder_set", {"minutes": 30}),
    ("remind me to call mom at 6 pm", "reminder_set", {"text": "call mom"}),
    ("remind me at 6:30 pm to call mom", "reminder_set", {"text": "call mom"}),
    ("remind me to call mom at six pm", "reminder_set", {"text": "call mom"}),
    (
        "remind me to take my medicine at quarter past six",
        "reminder_set",
        {"text": "take my medicine"},
    ),
    ("remind me to leave at half past four", "reminder_set", {"text": "leave"}),
    ("remind me to submit the form at 5", "reminder_set", {"text": "submit the form"}),
    ("remind me to call the dentist at 6 p.m.", "reminder_set", {"text": "call the dentist"}),
    ("remind me to pay rent at noon", "reminder_set", {"text": "pay rent"}),
    (
        "remind me to water the plants tomorrow morning",
        "reminder_set",
        {"text": "water the plants"},
    ),
    ("remind me tomorrow at 9 am to call the bank", "reminder_set", {"text": "call the bank"}),
    ("what are my reminders", "reminders_list", {}),
    ("list reminders", "reminders_list", {}),
    ("do i have any reminders", "reminders_list", {}),
    ("what reminders do i have", "reminders_list", {}),
    # dictation
    ("type thank you for your time", "type_text", {"text": "thank you for your time"}),
    ("type: hello world", "type_text", {"text": "hello world"}),
    ("dictate dear sir", "type_text", {"text": "dear sir"}),
    # routines
    ("job hunt", "run_routine", {"name": "job hunt"}),
    ("good morning", "run_routine", {"name": "good morning"}),
    ("focus mode", "run_routine", {"name": "focus mode"}),
    ("run job hunt", "run_routine", {"name": "job hunt"}),
    ("start focus mode", "run_routine", {"name": "focus mode"}),
    ("run the job hunt routine", "run_routine", {"name": "job hunt"}),
    ("start my coding setup", "run_routine", {"name": "coding setup"}),
    ("good morning aura", "run_routine", {"name": "good morning"}),
    ("let's wrap up", "run_routine", {"name": "wrap up"}),
    ("list routines", "list_routines", {}),
    ("what routines do i have", "list_routines", {}),
    # Aura itself
    ("stop listening", "stop_listening", {}),
    ("mic off", "stop_listening", {}),
    ("what can you do", "capabilities", {}),
    ("help", "capabilities", {}),
    ("what can i say", "capabilities", {}),
    # arithmetic
    ("what is twelve times twelve", "calculate", {"expression": "12 * 12"}),
    ("what's 7 plus 8", "calculate", {"expression": "7 + 8"}),
    ("What is 15% of 200?", "calculate", {"expression": "15 / 100 * 200"}),
    ("what is fifteen percent of two hundred", "calculate", {"expression": "15 / 100 * 200"}),
    ("square root of 144", "calculate", {"expression": "sqrt(144)"}),
    (
        "what's the square root of one hundred and forty four",
        "calculate",
        {"expression": "sqrt(144)"},
    ),
    ("calculate 144 divided by 12", "calculate", {"expression": "144 / 12"}),
    ("how much is three point five times four", "calculate", {"expression": "3.5 * 4"}),
    ("um what is one hundred and five minus twenty", "calculate", {"expression": "105 - 20"}),
    ("nine squared", "calculate", {"expression": "9 ** 2"}),
    ("what is 2 to the power of 10", "calculate", {"expression": "2 ** 10"}),
    ("what is two thousand five hundred plus 1,200", "calculate", {"expression": "2500 + 1200"}),
    ("what is 6 x 7", "calculate", {"expression": "6 * 7"}),
    ("what's 100 - 37", "calculate", {"expression": "100 - 37"}),
    ("could you work out twenty times thirty please", "calculate", {"expression": "20 * 30"}),
    # dates
    ("how many days until christmas", "date_info", {}),
    ("how many days till the 25th of december", "date_info", {}),
    ("how long until new year's eve", "date_info", {}),
    ("what day is christmas this year", "date_info", {}),
    ("what day is december 25th", "date_info", {}),
    ("what day is the third of march", "date_info", {}),
    ("what day was 15 august 1947", "date_info", {"date": "1947-08-15"}),
    ("what day is 1 january 2030", "date_info", {"date": "2030-01-01"}),
    ("when is halloween", "date_info", {}),
    ("what's the date in 10 days", "date_info", {"add_days": 10}),
    ("what is the date two weeks from now", "date_info", {"add_days": 14}),
    ("what day will it be in thirty days", "date_info", {"add_days": 30}),
    ("what day is it tomorrow", "date_info", {}),
    ("what day is it on friday", "date_info", {}),
    # stopwatch
    ("start the stopwatch", "stopwatch", {"action": "start"}),
    ("start a stop watch", "stopwatch", {"action": "start"}),
    ("please start my stopwatch", "stopwatch", {"action": "start"}),
    ("stop the stopwatch", "stopwatch", {"action": "stop"}),
    ("okay stop the stopwatch now", "stopwatch", {"action": "stop"}),
    ("how long has it been", "stopwatch", {"action": "check"}),
    ("check the stopwatch", "stopwatch", {"action": "check"}),
    ("what's the stopwatch at", "stopwatch", {"action": "check"}),
    # windows
    ("minimise this", "window", {"action": "minimize"}),
    ("minimize the window", "window", {"action": "minimize"}),
    ("maximise this window", "window", {"action": "maximize"}),
    ("could you maximize it", "window", {"action": "maximize"}),
    ("make this full screen", "window", {"action": "maximize"}),
    ("restore the window", "window", {"action": "restore"}),
    ("show desktop", "window", {"action": "show_desktop"}),
    ("show me the desktop", "window", {"action": "show_desktop"}),
    ("minimise everything", "window", {"action": "show_desktop"}),
    ("snap left", "window", {"action": "snap_left"}),
    ("snap this to the right", "window", {"action": "snap_right"}),
    ("move the window to the left side", "window", {"action": "snap_left"}),
    # dark mode
    ("dark mode", "dark_mode", {"on": True}),
    ("turn on dark mode", "dark_mode", {"on": True}),
    ("switch to dark mode please", "dark_mode", {"on": True}),
    ("light mode", "dark_mode", {"on": False}),
    ("turn off dark mode", "dark_mode", {"on": False}),
    ("switch to the light theme", "dark_mode", {"on": False}),
    # recycle bin and disk
    ("empty the recycle bin", "empty_recycle_bin", {}),
    ("empty my trash", "empty_recycle_bin", {}),
    ("clear the recycling bin please", "empty_recycle_bin", {}),
    ("how much disk space", "system_status", {"about": "disk"}),
    ("how much disk space do i have left", "system_status", {"about": "disk"}),
    ("how much storage is left on my laptop", "system_status", {"about": "disk"}),
    ("check my disk space", "system_status", {"about": "disk"}),
]

BRAIN = [
    "what is the volume of a sphere",
    "open question about notepad pricing",
    "remind me why the sky is blue",
    "what time does the store close",
    "what is the time complexity of quicksort",
    "find out who won the match",
    "where is paris",
    "where's the nearest pharmacy",
    "find me a good pasta recipe",
    "find a restaurant near me",
    "type of triangle with three equal sides",
    "write a poem about rain",
    "write an email to my landlord about the heating",
    "how do i mute a zoom call",
    "is the date palm a tree",
    "help me write a cover letter",
    "show me how to tie a tie",
    "play some jazz",
    "lock picking tutorial",
    "sleep well",
    "start a conversation about cars",
    "run a marathon in under four hours",
    "next week's weather",
    "note the difference between affect and effect",
    "the last song was great",
    "who wrote pride and prejudice",
    "brightness of the sun in lumens",
    "pause for thought is a radio show",
    "remind me what happened in 1947",
    "remember that time we went to goa",
    "open the pod bay doors",
    "screenshot tools for linux",
    "battery life of a pixel 9",
    "search and rescue dogs",
    "do i need a visa for japan",
    "close to you by the carpenters",
    "mute swans are native to europe",
    "stop the war",
    "what is a timer in javascript",
    "how do reminders work",
    "what is the dark mode setting for",
    "what is love",
    "what is five",
    "what is the square root of happiness",
    "what is 5 times the population of india",
    "what is the meaning of forty two",
    "one and only",
    "is dark mode better for your eyes",
    "how do i empty the recycle bin on a mac",
    "trash talk in cricket",
    "how much space does a horse need",
    "space",
    "storage wars",
    "how long until the cows come home",
    "what day is the meeting",
    "when is the next train to pune",
    "when is my flight",
    "snap out of it",
    "move left",
    "restore my faith in humanity",
    "full screen mode in vlc",
    "how long has it been since the moon landing",
    "stop watching me",
    "start watching the game",
    "the left side of the brain",
    "how many days are in a leap year",
]

SEVERAL = [
    (
        "open notepad and set volume to thirty",
        [("open_app", {"name": "notepad"}), ("volume_set", {"level": 30})],
    ),
    (
        "open github and linkedin",
        [("open_site", {"name": "github"}), ("open_site", {"name": "linkedin"})],
    ),
    (
        "open gmail, github and youtube",
        [
            ("open_site", {"name": "gmail"}),
            ("open_site", {"name": "github"}),
            ("open_site", {"name": "youtube"}),
        ],
    ),
    ("mute and lock the laptop", [("mute", {"on": True}), ("lock_screen", {})]),
    (
        "take a screenshot then open notepad",
        [("screenshot", {}), ("open_app", {"name": "notepad"})],
    ),
    (
        "pause the music and remind me to stretch in 20 minutes",
        [("media", {"action": "play_pause"}), ("reminder_set", {"text": "stretch", "minutes": 20})],
    ),
    (
        "set volume to 20 and brightness to 40",
        [("volume_set", {"level": 20}), ("brightness_set", {"level": 40})],
    ),
    (
        "dark mode and start the stopwatch",
        [("dark_mode", {"on": True}), ("stopwatch", {"action": "start"})],
    ),
    (
        "snap left then open notepad",
        [("window", {"action": "snap_left"}), ("open_app", {"name": "notepad"})],
    ),
]

# One request that must stay ONE action although it contains "and" or "then".
WHOLE = [
    ("take a note: buy milk and eggs", "note_add", {"text": "buy milk and eggs"}),
    ("remind me to call mom and dad at 6 pm", "reminder_set", {"text": "call mom and dad"}),
    (
        "google salt and pepper chicken",
        "search_site",
        {"site": "google", "query": "salt and pepper chicken"},
    ),
    ("type research and development", "type_text", {"text": "research and development"}),
    ("ask claude about cats and dogs", "search_site", {"site": "claude", "query": "cats and dogs"}),
    ("what is one hundred and five plus two", "calculate", {"expression": "105 + 2"}),
    ("what is two and two", "calculate", {"expression": "2 + 2"}),
]


def _fits(intent, tool, args):
    return (
        isinstance(intent, tuple)
        and intent[0] == tool
        and all(intent[1].get(k) == v for k, v in args.items())
    )


@pytest.mark.parametrize("said,tool,args", MATCH + WHOLE)
def test_built_in_phrase(hub, said, tool, args):
    intents = hub.local.match_all(said)
    assert intents is not None and len(intents) == 1 and _fits(intents[0], tool, args), (
        said,
        intents,
    )


@pytest.mark.parametrize("said", BRAIN)
def test_left_to_the_language_model(hub, said):
    assert hub.local.match_all(said) is None, (said, hub.local.match_all(said))


@pytest.mark.parametrize("said,wanted", SEVERAL)
def test_several_actions_in_one_sentence(hub, said, wanted):
    intents = hub.local.match_all(said)
    assert intents is not None and len(intents) == len(wanted), (said, intents)
    for intent, (tool, args) in zip(intents, wanted):
        assert _fits(intent, tool, args), (said, intents)


def test_reminder_clock_words(hub):
    at = lambda said: hub.local.match_all(said)[0][1]["at"][11:]  # noqa: E731
    assert at("remind me to call mom at six pm") == "18:00"
    assert at("remind me to take my medicine at quarter past six pm") == "18:15"
    assert at("remind me to leave at half past four pm") == "16:30"
    assert at("remind me to go at quarter to seven pm") == "18:45"
    assert at("remind me to pay rent at noon") == "12:00"
    assert at("remind me to water the plants tomorrow morning") == "09:00"
    assert at("remind me tomorrow at 9 am to call the bank") == "09:00"


def test_it_and_that_use_the_last_app(hub):
    hub.handle("open notepad")
    assert hub.local.match_all("close it") == [("close_app", {"name": "notepad"})]
    assert hub.local.match_all("close that please") == [("close_app", {"name": "notepad"})]


def test_several_actions_all_run(hub):
    reply = hub.handle("open notepad and set volume to thirty")
    kinds = [c[0] for c in hub.platform.calls]
    assert "launch" in kinds and ("volume", 30) in hub.platform.calls, (reply, hub.platform.calls)


def test_new_tools_really_run(hub):
    assert hub.handle("what is twelve times twelve").endswith("is 144")
    assert hub.handle("what is fifteen percent of two hundred").endswith("is 30")
    assert hub.handle("square root of 144").endswith("is 12")
    assert "Thursday 25 December 2025" in hub.handle("what day was 25 december 2025")
    assert hub.handle("start the stopwatch") == "Stopwatch started"
    assert hub.handle("how long has it been").startswith("Stopwatch at")
    hub.handle("snap left")
    hub.handle("dark mode")
    assert ("window", "snap_left") in hub.platform.calls and (
        "dark_mode",
        True,
    ) in hub.platform.calls
    hub.platform.dialog_answer = False  # emptying the bin is critical: a voice is never enough
    hub.voice_answer = True
    hub.handle("empty the recycle bin")
    assert not [c for c in hub.platform.calls if c[0] == "empty_recycle_bin"]


# ---- found by the second review: each of these fired the wrong action --------------------------
@pytest.mark.parametrize(
    "said, tool, args",
    [
        ("volume up ten", "volume_change", {"delta": 10}),
        ("turn the volume down twenty", "volume_change", {"delta": -20}),
        ("volume down 5 percent", "volume_change", {"delta": -5}),
        ("volume to forty", "volume_set", {"level": 40}),
        ("brightness down ten", "brightness_change", {"delta": -10}),
        ("brightness to sixty", "brightness_set", {"level": 60}),
        ("brighter", "brightness_change", {"delta": 10}),
        ("dim the screen", "brightness_change", {"delta": -10}),
        ("find my resume", "files_search", {"query": "resume"}),
        ("type thank you for your time", "type_text", {"text": "thank you for your time"}),
        ("let's wrap up", "run_routine", {"name": "wrap up"}),
        ("put the laptop to sleep", "power", {"action": "sleep"}),
    ],
)
def test_review_two_still_handled(hub, said, tool, args):
    assert hub.local.match(said) == (tool, args), said


@pytest.mark.parametrize(
    "said",
    [
        "type o negative",
        "type two diabetes symptoms",
        "type c charger",
        "type a personality",
        "find nemo",
        "find my phone",
        "find the meaning of life",
        "where is my mind",
        "where are my keys",
        "i want to sleep",
        "can you sleep",
        "let's play",
        "volume a",
    ],
)
def test_review_two_left_to_the_model(hub, said):
    assert hub.local.match(said) is None, said


def test_twenty_five_is_not_a_clock_time(hub):
    found = hub.local.match("remind me at twenty five to call bob")
    assert found is None or "T20:05" not in str(found)
