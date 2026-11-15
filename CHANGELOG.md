# Changelog

## 2026-11-15: project is in git and on GitHub

The source is now a git repository with a private GitHub repo, `divshettyy/aura`. Before the
first commit the tree was scanned for keys, tokens, personal addresses and user paths: none
found. `.gitignore` keeps out build output, caches, downloaded models and everything that lives
in `%APPDATA%\Aura` (config, audit log, state, logs). MIT `LICENSE` added, same as the other
projects. The README "Test status" section was brought up to date (it still said 68 tests and
"never run on real hardware").

## 2026-11-15: voice mode hears the wake word but not the command

From the user's own `aura run` output with Bluetooth earbuds as the microphone: the wake word
scored 0.16-0.19 (below 0.30), the double-check took 2.2-4.4 s, and after a confirmed wake the
command came back empty.

Fixed (`aura/voice/listener.py`)
- Noise floor. It was the middle value of the last 2 seconds of loudness. A wake phrase that the
  wake model scores low is in that history, so after "hey jarvis" (more so when repeated) the
  floor was the speaker's own voice, the speech threshold was three times that, and no command
  ever counted as loud. The floor is now the 20th percentile of the last 5 seconds.
- Time to start speaking. Audio that queued during the double-check counted against the
  4 seconds the user gets to start, so 2.2 s of checking left 1.8 s. The queued audio is still
  listened to first, but no longer uses up that time.

Not fixed: the double-check itself is slow on this laptop (2.2-4.4 s for 2 s of audio), and the
earbuds' microphone garbles speech ("Hey gentlemen", "Page Out of Us"). The laptop microphone
scored 0.42 on 13 November, which wakes at once with no double-check.

Also seen: the first `aura run` returned to the prompt right after "Aura is ready." with no
error in the console or the log. Cause unknown. A `heard: ''` at 16:40:26 had no wake line
before it (possibly push-to-talk); not explained, may be the same noise-floor fault.

Tests: 506 passed, 1 skipped. Not yet confirmed with the user's voice.

Open, waiting on the user
- The `aura run` that was open during the test still runs the old code. Stop it (Ctrl+C) and
  start it again, then say "hey jarvis", wait for the beep, and give a command.
- If the earbuds still struggle: make the laptop microphone the Windows input and unmute it
  (Settings > System > Sound > Input). `aura hear` compares the two microphones safely.
- Ideas not started: a smaller speech model for the double-check only, so it takes well under
  2 s; find why the first `aura run` exited silently.

## 2026-11-15: "it can't hear me"

The user spoke to Aura several times and got nothing. Found:
- Aura was not running. `aura.log` has no voice activity since 13 November and no Aura process
  existed. Sign-in autostart was declined at install, so Aura only listens while `aura run` is
  open in a terminal.
- The default Windows microphone is now the Bluetooth earbuds ("Headset (Airdopes Ultra Pro)"),
  not the laptop microphone array (which is the muted one). Aura uses the Windows default.

Added `aura hear` (`aura/__main__.py`): a 10-second listening test that prints, per second, the
loudness and the wake-word score, then what speech-to-text heard and a one-line result with the
next step. It acts on nothing. Run for 3 seconds with nobody speaking it showed sound arriving
from the earbuds (peak 6055) and no words. Not yet run with the user's voice.

## 2026-11-15: second review, and what it found

A read-only review of the phrase rewrite and the new tools, with 60 new sentences that were not
in the test file. Seven faults were confirmed and fixed; each has a test now.

- `calculate` could hang Aura: `round(7, -16000000)` ran for 68 seconds while every other
  action waited. `round` now takes at most 15 places (`aura/skills/meta.py`).
- "volume up ten" set the volume to 10, "brightness down ten" set brightness to 10. They are
  now changes of ten points. New tool `brightness_change`; "brighter" and "dim the screen" work.
- "type o negative", "type two diabetes symptoms" and "type c charger" were typed into the
  focused window. They go to the language model now.
- "find nemo", "find my phone", "where are my keys" ran a file search. File search now needs a
  word that names a file (document, pdf, resume, a file extension, and so on).
- "remind me at twenty five to call bob" was set for 20:05. "twenty five" is no longer a time.
- "i want to sleep" and "can you sleep" asked to put the laptop to sleep; "let's play" toggled
  the music. A bare "sleep" now goes to the language model; "put the laptop to sleep" still works.
- "volume a" set the volume to 1.
- The Wi-Fi name, which is chosen by whoever runs the access point, is cut to plain characters
  before it reaches the language model.

Also changed after the task-coverage run: sums speak only the answer ("That is 30"), past dates
read "was about 79 years ago", and "how much disk space" / "am i connected to wifi" answer that
part only.

Held up under review: compound requests use one turn (gate, taint and action limit apply to
each part), negations do not fire, shutdown / sleep / emptying the Recycle Bin still need the
dialog click, `calculate` rejects everything that is not arithmetic.

Not fixed, never run on Windows: `window` acts on the foreground window, which in text mode is
Aura's own terminal; Win+Left/Right may combine with a held push-to-talk key; the dark-mode
broadcast can wait 200 ms per hung window.

Verified on the installed copy: 505 passed, 1 skipped; `aura doctor` brain ok (microphone
muted); audit chain intact; ten built-in requests answered in 1.5-1.8 s each (time, sums, dates,
disk, Wi-Fi, battery, reminders, a request with fillers), two model requests in 5.5-5.8 s.

## 2026-11-15: task coverage

A battery of 318 spoken-style requests now lives in `tests/test_phrases.py`: every row of the
README table and every tool, each said several ways (polite forms, fillers, speech-to-text
spellings, number words, compound requests, relative times), plus 67 sentences that only
contain a trigger word and must be left to the language model.

Before: of the first 228 sentences, 149 were handled correctly. 60 plain built-in requests fell
through to the language model (5 to 7 seconds instead of about 1.5), 12 sentences fired an
action they should not have, and none of the 7 compound requests was handled. The tools added
today (calculate, date_info, stopwatch, window, dark_mode, empty_recycle_bin) had no built-in
phrase at all. After: all 318 pass.

Fixed (`aura/brain/local.py`)
- Fillers and politeness at either end: "um", "okay so", "i need you to", "for me", "thanks".
  Dictation and notes keep their last words ("type thank you" still types "thank you").
- Speech-to-text spellings: "Volume, 40.", "per cent", "note pad", "screen shot", "stop watch".
- "seventy percent" was read as a two-word number and rejected; "brightness seventy percent"
  now works.
- More ways to say the same thing: "pull up youtube", "take me to github", "a bit louder",
  "turn it up a little", "stop the music", "play the next one", "what's my battery level",
  "do i have any reminders", "make a note to ...", "jot down ...".
- Times: "in half an hour", "in an hour and a half", "in a couple of minutes", "45 mins",
  "at six pm", "at quarter past six", "at half past four", "at noon", "tomorrow morning",
  "tomorrow at 9 am", "start a ten minute timer". The time may come before or after the task.
- Several actions in one sentence run without the language model when every part is a built-in
  request: "open notepad and set volume to thirty", "open gmail, github and youtube" (the verb
  carries over). If any part is not built in, the whole sentence goes to the model as before.
- "close it" / "close that" closes the app Aura opened last.
- New phrases for the new tools: sums ("what is fifteen percent of two hundred", "square root
  of 144", "nine squared"), dates ("how many days until christmas", "what day was 15 august
  1947", "what's the date in 10 days"), stopwatch, window arranging, dark and light mode,
  emptying the recycle bin (still needs the dialog click), disk space.
- No longer fired by mistake: "where is paris" and "find out who won the match" (were file
  searches), "write a poem about rain" and "type of triangle ..." (were typed into the focused
  window), "note the difference between ..." (was saved as a note), "close to you by the
  carpenters" (was a close-app request), "search and rescue dogs". "write ..." no longer
  dictates; say "type ...".

Checked on the real install with read-only requests: built-in phrases answer in 1.5 s
(system status 2.4 s); the same kind of question through the language model takes 5.5 to 7.2 s.

Still not handled by a built-in phrase (they go to the language model): "brighter" / "dim the
screen" (there is no relative brightness tool), "play <song name>", dates named by a moving
festival ("when is diwali"), "how long until 5 pm", reading a note or reminder again.

Tests: 475 passed, 1 skipped.

## 2026-11-15: new skills

Six new actions and a fuller status report, for things people ask a laptop assistant every day.
No new libraries, no network calls, nothing that runs a program.

Added (`aura/skills/meta.py`, `aura/skills/system.py`, `aura/platform/windows.py`, `aura/platform/stub.py`)
- `calculate` (safe): exact arithmetic. The expression is parsed into numbers and operators and
  walked; it is never run as code. Names, attribute access, strings, lists and calls to anything
  outside a fixed list of maths functions are refused, and so are very large powers.
- `date_info` (safe): the weekday of a date, how many days away it is, and a date shifted by a
  number of days.
- `stopwatch` (safe): start, check, stop. The start time is kept in the state store, so it
  survives a restart of Aura.
- `window` (safe): minimise, maximise or restore the window in front; show the desktop; snap left
  or right. The last three press one fixed Windows-key shortcut chosen by name; no key code can
  come from a request. Closing a window stays with `close_app`, which needs a spoken "yes".
- `dark_mode` (safe): writes the same two per-user values the Settings app writes.
- `empty_recycle_bin` (critical): needs the on-screen click, is refused in automations and while
  locked, and can be blocked in the config like any other action.
- `system_status` now also reports battery time left (on battery only), free disk space and the
  volume. `reminder_set` is described to the model as "reminder or timer".

Looked at and not added
- Timers in seconds: reminders are checked every 15 seconds, so a "30 second timer" would be up
  to 15 seconds late. Timers in whole minutes already work through `reminder_set`.
- Night light and do-not-disturb: Windows has no documented way to switch them.
- Wi-Fi and Bluetooth on/off: needs administrator rights or a library that is not installed.
- Weather: no new network call; "search google for weather in Pune" already opens it.
- Cancel a reminder, clipboard, file search, recent files, media keys: already there.
- Switch to a named app: `open_app` already brings most apps to the front.

Run for real on this laptop (read-only calls): free disk space (278 of 474 GB), battery
(73 percent, charging, no time estimate while plugged in), dark mode state (on), Recycle Bin
item count (12).

Not run on real Windows, checked on the stand-in platform only: `window` (all six actions),
switching `dark_mode`, and `empty_recycle_bin` itself.

Tests: 39 new in `tests/test_new_skills.py` (arguments, risk level through the gate, taint,
locked laptop, automation). 153 passed, 1 skipped with `tests/test_phrases.py` left out: that
file belongs to the built-in-phrase work going on at the same time.

## 2026-11-15: review of the day's fixes

A read-only review of the routine, `open_url` and wake-phrase fixes, done because the first
brain fix had passed every test and broken the product.

Wake phrase (`aura/voice/listener.py`): the two-word match added earlier today was wrong. It
removed the start of ordinary sentences: "war is over" became "over", "jar is empty" became
"empty". An older fault did the same to "paris weather" and "davis cup scores". How close a
word must be to the wake name now depends on where it is: 0.72 after a greeting, 0.80 as the
first word, 0.92 when split across two words. Tests cover 13 ordinary openings that are kept
and 5 misheard wake names that are still removed.

Routines and `open_url`: both fixes held up. The model cannot supply its own turn, taint and
the action limit carry into routine steps, and no built-in phrase needs an extra "yes". Added
the missing test for the original bug (a voice-started routine with a confirm step and the
answer "no"). The README's list of confirm actions now includes web addresses.

Known and unchanged: a routine started by voice shares the 12-action limit of one request; a
declined step does not stop the later steps of a routine.

## 2026-11-15: brain speed

Measured the Claude leg on the real install, through the WSL route, with questions that run no
action (37 tools, model haiku, effort low).

Where the time goes
- Starting Claude Code: about 3.5 to 4 s. A request on a process that was just started took
  4.0 to 5.8 s; on a process started a few seconds earlier, 1.7 to 2.0 s.
- The model itself: 1.5 to 1.7 s of that 1.7 to 2.0 s (now and then 3.5 s, on the provider's side).
  Aura's own overhead on a started process is about 0.2 s.
- The login shell is not the cost: `wsl ... bash -lic true` 0.5 s, `bash -lc` 0.4 s, `bash -c` 0.45 s.

Fixed (`aura/brain/llm.py`, `tests/test_brain_fast.py`)
- The next spare process is now started the moment one is taken, not after the request ends
  and the used process has closed (closing alone takes 0.9 s). Before, the second step of a
  request (when Claude asks to see a tool result) and a request sent straight after another
  always met a cold start. Two requests back to back, second one: 5.1 s and 4.2 s before,
  3.5 s and 2.7 s after. Starting a process alongside a request costs that request under 0.1 s
  (1.84 to 1.92 s against 1.78 to 1.84 s); the old comment that said otherwise was not measured.
- The rules, the tool list and the answer format moved out of every request into the system
  prompt, read with `--system-prompt-file` from `system-prompt.txt` in the brain sandbox (found
  by name through WSL, because Claude starts in that folder). A request went from 7,724
  characters to 678. The provider caches the system prompt across processes: about 2,800 of
  3,700 input tokens are now read from cache on each request, where before all 3,700 were
  written fresh every time. That lowers what each request counts against the Claude
  subscription. The time gained is small: 2.10 s to 1.97 s on average over six different
  questions, which is inside the noise.

Unchanged: a single request on a started process still takes about 1.9 s, nearly all of it the
model's answer time. Nothing in Aura can shorten that except built-in phrases, which never
reach Claude.

Tried and rejected
- A shell other than `bash -lic`: saves at most 0.1 s, and `claude` is only on the PATH of a
  login shell on some installs.
- Reusing one process for several requests: it would remember earlier requests. Still one
  request per process.
- Redirecting the Claude config directory: it holds the sign-in (see the entry below).

Verified: 113 passed, 1 skipped. From the source tree: `aura doctor` reports "Claude
subscription answers" ok, and `aura once what is nine times nine` answered "Nine times nine is
81." in 5.9 s (a cold Python and a cold Claude; `once` cannot use a spare). Not installed into
the venv yet, and not timed inside a spoken `aura run` turn.

## 2026-11-15: start-up speed

Measured `aura once what time is it` (a built-in phrase, no Claude) on the laptop: about 4.0 s
before (4.08, 3.82, 4.18), about 1.5 s after (1.66, 1.52, 1.48, 1.49). An empty Python start is
0.27 s of that.

Where the time went, timed inside one process:
- About 0.86 s loading the credential-store library the first time the audit log wrote its head
  anchor: 0.46 s to import `keyring`, 0.40 s for it to search every installed back-end. The
  three anchor writes of a request cost only about 20 ms each.
- About 1.2 s at exit: `aura once` started a spare Claude process "to keep warm" for a second
  request that never comes, then waited for it to shut down.
- Imports were already lazy: the audio, speech and Windows libraries are not loaded in text mode.
  What is left is `yaml` (0.18 s) and argparse/logging (0.12 s).

Fixed
- `aura/secrets.py`: one `keyring_module()` loader. On Windows it names the back-end keyring
  already picks by itself (Windows Credential Manager), which skips the search; a
  `PYTHON_KEYRING_BACKEND` set by the user is left alone. `preload()` loads the library in a
  background thread.
- `aura/audit.py`: opening the audit log starts that preload, so it runs alongside the rest of
  start-up and the first request no longer waits for it. In `aura run` this takes the 0.86 s off
  the first spoken request. The integrity check is unchanged: the head anchor is still written
  with every entry, in the same call as before (`aura audit verify`: chain intact after the change).
- `aura/__main__.py`: `aura once` no longer keeps a spare Claude warm. Text mode and voice mode
  still do. For a free-form `aura once` request this also means one Claude process is started
  instead of two.

Left alone
- `yaml` import and config parsing (0.18 s): a cache of the parsed config could go stale.
- Reading the whole audit log when it is opened: milliseconds at the current size, and it is
  what keeps the chain going.
- `aura run` start-up is dominated by loading the speech models, which was not measured here
  (voice mode was not run).

Tests: 111 passed, 1 skipped (three new: preload is requested once and the anchor is still
written per entry; the back-end is named on Windows only and never overrides the user's;
`aura once` switches the warm spare off and text mode keeps it). `aura doctor`: unchanged, the
only failure is the muted microphone. Not yet installed into the venv copy.

## 2026-11-15: routine confirm / open_url

Closed both items from the 2026-11-13 "Open decisions" list.

Routines bypassing the spoken "yes" (`aura/automation.py`, `aura/skills/meta.py`, `aura/hub.py`)
- Root cause: `Automation.run_steps` always built a fresh `Turn("automation")` for a routine's
  steps, no matter who asked for the routine. `Policy.decide` treats `source == "automation"` as
  unattended and auto-allows confirm-tier steps (deliberately, so a 9am clock rule isn't stuck
  waiting for a "yes" nobody can give) — but that same rule was firing for a routine the user had
  just asked for by voice, which the README promises a spoken "yes" for.
- Fix: `run_routine` and `run_steps` now take an optional `turn`. `Hub.run_tool` passes the live
  turn into any tool function that declares a `turn` parameter (checked once via
  `inspect.signature`, currently just `run_routine`), so a routine launched by a live voice/text
  request now runs its steps under that same turn — confirm asks a spoken "yes", critical asks
  the on-screen dialog, same as a direct request. A routine fired by a clock/event rule
  (`_run_rule`/`tick`, nobody listening) still gets `turn=None` and keeps the old unattended
  "automation" turn: confirm auto-allows, critical is still denied as "unattended". No parallel
  confirmation system — this reuses the existing `Turn`/`Policy` gate end to end.
- Tests: replaced `test_automation_cannot_run_critical` with
  `test_unattended_automation_cannot_run_critical` (calls `run_routine(turn=None)` directly, the
  real unattended path) and added `test_live_routine_still_asks_for_critical_step` (a live
  "run bye" now asks the dialog and runs or cancels depending on the answer, instead of being
  flatly denied).

`open_url` accepting any address (`aura/skills/web.py`)
- `open_url` was `risk=SAFE` (the default) with only `outward=True`, so an untainted request opened
  any http(s) address immediately; only a *tainted* turn (content Aura itself read) escalated it
  to a spoken yes. Changed to `risk=CONFIRM`, the same tier `run_command` already uses, so every
  free-form `open_url` now asks "Open this address: {url}?" first — consistent with the README's
  confirm-tier list, no bespoke check. `open_site`/`search_site` (named `sites:` entries) are
  unchanged and still free, since those addresses come from the user's own config, not speech.
- This also strengthens the taint case: `risk=CONFIRM` + tainted now escalates straight to the
  on-screen dialog (`Policy.decide`'s existing CONFIRM-when-tainted rule), not just a voice "yes"
  a malicious page's own text could have asked for.
- Tests: added `test_open_url_needs_spoken_yes_even_untainted`; updated `test_taint_escalates`,
  whose first assertion used `open_url` as the "safe-but-outward" example — that role now falls
  to `search_site` (still `risk=SAFE, outward=True`), with `open_url` moved alongside `close_app`
  as a confirm-tier example that escalates further when tainted.

"Open decisions" from 2026-11-13 is now resolved; removed below.

Verified: full suite, `106 passed, 1 skipped` (pre-existing symlink-privilege skip), against the
source tree. Not exercised on real hardware — the next on-hardware session should confirm a
spoken "yes"/dialog actually pauses a routine and that `open_url` now asks before opening.

## 2026-11-15: voice loop

Re-checked every sub-item of the 2026-11-13 "Voice loop" in-progress note against
`aura/voice/listener.py` and `aura/voice/tts.py` as they stand. Most of it turned out to be
already implemented, just never marked done: `_converse`'s follow-up loop (`follow_up`,
`follow_up_seconds`, `follow_up_cue`), `_say`'s barge-in (`barge_in: hotkey` always lets the
push-to-talk key cut Aura off mid-reply; `barge_in: voice` additionally lets a clearly-louder
voice interrupt, learning the mic's own-echo level from the first half second), and the
wake-word "maybe" double-check (`wake_verify_threshold` / `_double_check`, re-transcribing the
last 2 s and checking for the wake name with `mentions_wake`) are all live code, not placeholders.

Fixed (`aura/voice/listener.py`)
- `strip_wake` only matched the wake name against one token. Speech-to-text sometimes splits it
  across two ("jar", "vis"); a merged two-token check now runs at the same match ratio as the
  single-token check (0.72 via `difflib`), so no new false-positive risk — it only adds matches,
  never loosens the existing ones. Covered by `test_strip_wake_name_split_across_two_tokens` in
  `tests/test_voice.py`.

Still open — the exact "Hey, John, miss." case from 2026-11-13
- That transcript doesn't resemble "jarvis" at the character level even merged, so no fuzzy-match
  widening fixes it; it's a speech-to-text accuracy problem, not a wake-stripping one. Already
  mitigated as far as code can: `transcribe()` passes `hotwords=name.capitalize()` to bias Whisper
  toward "Jarvis". Real fixes from here are on-hardware tuning, not something to guess blind:
  try `stt_model: small.en` (more accurate, slower) for this user's mic, or get the double-check
  path to require a *confirmed* wake name in the whole converse-opening phrase before falling back
  to sending the raw text, since there's no mic to retest against from here.
- Faster speech-to-text: `transcribe()` already runs the fastest correct path (`beam_size=1`,
  `vad_filter=False`, `condition_on_previous_text=False`, `compute_type=int8`) — no further
  speed win found without trading accuracy. `stt_model: tiny.en` is available in config for
  anyone who wants to make that trade; left as the user's own per-mic tuning call, same as
  `wake_threshold`.

Moved out of "In progress" below: follow-up questions, barge-in, and wake-word double-check are
done in source. Wake-word reliability and the specific wake-phrase-leak transcript are still
open and need a real mic to resolve further.

Verified: full suite, `104 passed, 1 skipped` (pre-existing symlink-privilege skip), run against
the installed venv copy after `pip install --upgrade --no-deps .` from the source dir. Not
verified by hand against a real microphone — that still needs the next on-hardware session.

## 2026-11-15: brain latency / isolation

A first attempt gave the brain's Claude Code its own config directory (`CLAUDE_CONFIG_DIR`
pointed at an empty folder), on the theory that the isolation flags did not keep the user's
hooks and CLAUDE.md out. That attempt passed every unit test and broke the product: Claude Code
keeps its sign-in in the config directory, so every request failed with
"Not logged in · Please run /login" (`aura doctor`: "Claude subscription answers" FAIL;
`aura once`: "My language model isn't reachable right now").

Fixed (`aura/brain/llm.py`, `aura/default_config.yaml`, `tests/test_brain_fast.py`)
- The `CLAUDE_CONFIG_DIR` override is removed. `command()` still returns `(argv, env)`, with
  `env` always `None`. Two tests now assert that the config directory is never redirected.
- The existing flags (`--safe-mode`, `--disable-slash-commands`, `--strict-mcp-config`,
  `--tools ""`, `--system-prompt`) are enough: the terse hook-style reply seen on 2026-11-13
  came from the cold `claude -p` call that predated them.

Verified on the real install, through the WSL route, after `pip install --upgrade --no-deps .`:
- `aura once what is seven times eight` -> "Seven times eight is 56." (6.7 s)
- `aura once tell me a one line joke` -> a full-sentence joke (6.4 s)
- `aura once open notepad and set volume to thirty` -> both actions ran (8.1 s)
Replies are plain full sentences, with no trace of the user's Claude Code hooks. The times are
for `aura once`, which starts Python and a cold Claude each time; `aura run` keeps a spare
Claude warm and has not been timed.
- Tests: 106 passed, 1 skipped.

Lesson: a change to how Claude is started is not verified by unit tests. Run `aura doctor` and
one `aura once` request after any such change.

Left alone: one Claude process per turn (a reused process would remember earlier turns; the
warm spare already takes start-up off the request path).

## 2026-11-13: first run on real hardware

First install and run on the Windows laptop. Before this, Aura had only run on Linux with a simulated Windows layer.

### Install

- `install.ps1` ran clean: Python 3.12 found, venv in `%LOCALAPPDATA%\Aura\venv`, speech models downloaded, `aura` added to PATH. Sign-in autostart was declined.
- User config created at `%APPDATA%\Aura\config.yaml`.

### First-run checklist

| Step | Result |
|---|---|
| 1. `aura doctor` | pass |
| 2. notepad, volume, brightness, screenshot, typing, gmail, job hunt, reminder | pass, checked against the real machine state |
| 3. shutdown dialog | not run (needs a click) |
| 4. free-form request | failed, fixed (see Brain) |
| 5. voice mode | failed, in progress (see Voice) |
| 6. lock test | not run |
| 7. Ctrl+Alt+M | not run by hand; the hotkey registers |

### Fixed

Brain
- Claude Code is not on the Windows PATH; it lives in WSL (kali-linux). The config now uses `claude_command: [wsl, -d, kali-linux, --, bash, -lic]`.
- Claude's reply is now found even when the login shell prints a banner first (`_claude_envelope` in `aura/brain/llm.py`).

Windows layer (`aura/platform/windows.py`, `aura/skills/system.py`)
- Typing reported "Typed" when Windows blocked the keystrokes; it now says the window may be running as administrator.
- The hotkey loop no longer dies or spins on a message error.
- Explicit argument types for the Win32 calls.
- If Edge is missing, the default browser is used.
- No console flash on sleep, shutdown and restart.

Speech output (`aura/voice/tts.py`)
- A stuck Windows voice call can no longer leave the microphone blocked forever (60 second cap).

Audit log (`aura/audit.py`)
- A half-written last line no longer stops Aura from starting.
- Lines deleted from the end of the log are now detected, through a head record kept in Windows Credential Manager.

Files (`aura/skills/files.py`)
- 24 more code-running file types are refused by "open".

Installer
- `uninstall.ps1` also removes the downloaded speech model (about 150 MB).

Tests: 67 passed and 1 failed at the start; 89 passed and 1 skipped now. The skip is the symlink test, which needs a privilege this account does not have.

### Voice mode: what was found

- The Windows microphone was muted at system level, so Aura received silence. Unmuted by hand. `aura doctor` reported the microphone as fine.
- "hey jarvis" scored at most 0.42 on this microphone with the user's voice; the threshold was 0.5. Lowered to 0.3 in the user config as a stopgap.
- Ctrl+Alt+Space never reached Aura: another program already owns that combination (Windows error 1409), and Aura ignored the failed registration.
- One real voice turn took about 8 seconds: 2 s speech-to-text, 5 s Claude, then speech. The wake phrase leaked into the command ("Hey, John, miss.").
- A reply came back in the terse style of the user's own Claude Code hooks ("Not catch that. Say again?"): the brain process inherits the user's personal Claude Code setup.

### In progress

- Hotkey: report failed registrations, fall back to another combination (Ctrl+Alt+J works on this laptop). Doctor fails on a muted microphone and warns on a silent one. Done in source, not yet installed.
- Voice loop: wake-word reliability and the exact wake-phrase-leak transcript from 2026-11-13 need a real mic to chase further (see 2026-11-15 voice loop entry above). Follow-up questions, barge-in, and the wake-word double-check were already done in source and are no longer open.

### Not yet tested by hand

Shutdown dialog, the lock test, Ctrl+Alt+M, and a full spoken conversation with the user's own voice.
