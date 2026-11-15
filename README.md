# Aura - a voice-controlled ecosystem for your Windows laptop

Say **"hey jarvis"** (or press **Ctrl+Alt+Space**) and speak. Aura opens apps and your
websites, controls sound/brightness/media, finds files, takes notes, sets reminders, types what
you dictate, drafts emails and calendar events, and runs multi-step routines.

Every part goes through one hub, so the parts know about each other: a reminder becomes an
event that the automation rules react to; "open it" refers to the file you just searched for;
every action lands in one tamper-evident log.

## Install (about 10 minutes)

1. Copy this `aura` folder to the laptop and unzip it.
2. Double-click **`install.cmd`**. It needs no administrator rights. It installs Python 3.12 if
   missing (asks first), creates a private environment in `%LOCALAPPDATA%\Aura`, downloads the
   offline speech models, adds the `aura` command, and offers to start Aura at sign-in.
3. Open a **new** terminal and run:

   ```
   aura doctor
   aura text
   aura run
   ```

   `doctor` checks everything, `text` lets you type commands (best first test), `run` is voice mode.

### The brain (uses your Claude subscription, no API key)

Simple commands are understood by built-in phrases, instantly and offline. Anything else is sent
(as text only) to Claude through the **Claude Code** command-line tool, which signs in with your
Claude subscription.

* If `claude` works in a normal Windows terminal: nothing to do.
* If Claude Code is installed **inside Kali (WSL)**, run `aura config` and add:

  ```yaml
  brain:
    claude_command: [wsl, -d, kali-linux, --, bash, -lic]
  ```

  (Kali's default shell is zsh; if `aura doctor` says claude was not found, use `zsh` instead of `bash`.)
* Not installed anywhere? Install it on Windows (see https://code.claude.com/docs) and run `claude` once to sign in.
* Other options: `provider: api` with `aura secret set anthropic_api_key`, or `provider: none`
  (built-in phrases only, nothing ever leaves the laptop).

`aura doctor` makes a real test call and tells you whether the brain answers.

## What to say

| Say | What happens |
|---|---|
| "open notepad" / "open kali" / "open Claude" | apps from the config or the Start Menu |
| "open gmail" / "open linkedin" / "open naukri" | your sites, in Edge |
| "search for data analyst on linkedin" / "search github for whisper" | site search |
| "ask chatgpt how do I ..." / "ask claude ..." | opens the chatbot with your question |
| "volume 40" / "louder" / "mute" / "brightness 70" | sound and screen |
| "pause" / "next song" | media keys |
| "take a screenshot" / "lock the laptop" / "battery status" | system |
| "find my resume" / "recent files" | files in Documents, Desktop, Downloads, Pictures |
| "take a note: call the recruiter" / "read my notes" | daily notes file in `Documents\Aura Notes` |
| "remind me to stretch in 20 minutes" / "remind me to call mom at 6 pm" | spoken reminders |
| "type thank you for your time" | dictation into the focused window (e.g. Notepad) |
| "what is 18 percent of 2,450" / "square root of 144" | exact arithmetic, worked out on the laptop |
| "how many days until 25 December" / "what day is 90 days from today" | dates |
| "start a stopwatch" / "how long has it been" / "set a timer for ten minutes" | stopwatch; timers are reminders |
| "minimise this window" / "snap it to the left" / "show the desktop" | the window in front |
| "switch to dark mode" / "light mode" | Windows colour mode |
| "how much disk space is left" / "how long will the battery last" | fuller system status |
| "empty the recycle bin" | permanent, so it needs a click on the on-screen dialog |
| "job hunt" / "good morning" / "focus mode" / "coding setup" / "wrap up" | routines |
| "stop listening" | microphone off until Ctrl+Alt+M |
| anything else, e.g. "open github and linkedin and remind me in ten minutes to apply" | handled by Claude |

Edit routines, sites, apps and rules with `aura config` (see all options: `aura config --defaults`).

## Security model

* **Audio never leaves the laptop.** Wake word and speech-to-text run locally. Only the *text* of
  requests the built-in phrases can't handle goes to Claude.
* **The model can only propose actions.** A fixed gate (`aura/hub.py`, `aura/policy.py`) decides:
  * *safe* actions run;
  * *confirm* actions (close an app, move a file, saved commands, open a web address that is not one of your named sites) need a spoken "yes";
  * *critical* actions (shut down, delete to Recycle Bin, empty the Recycle Bin) need a click on an on-screen dialog -
    a voice from a video or another person cannot approve them.
* **Prompt-injection defence.** After Aura reads content it did not write (a file, the clipboard),
  anything that could act on hidden instructions in that content is moved up one level for the rest
  of that request.
* **No shell.** There is no tool that runs arbitrary commands or programs. Apps come only from the
  config or the Start Menu; files are confined to your listed folders (symlinks and `..` resolved
  first); executable file types are never opened; dictation cannot press Enter or Tab.
* **Nothing is sent on your behalf.** Emails and calendar events open as drafts for you to send.
* **Locked means deaf.** Aura ignores speech while Windows is locked.
* **No network ports** are opened; nothing can connect to Aura.
* **Secrets** (only if you use an API key) are stored in Windows Credential Manager.
* **Audit log.** Every request, action, refusal and confirmation is written to
  `%APPDATA%\Aura\audit.jsonl`; each line contains the hash of the previous one.
  `aura audit verify` detects edits or removed lines; `aura audit tail` shows recent activity.
* **Privacy switch.** Ctrl+Alt+M closes the microphone device completely.
* Tighten or block anything in the config, e.g. `policy: {overrides: {type_text: confirm, power: blocked}}`.

Known limits, stated plainly:

* Aura does not recognise *whose* voice is speaking. Anyone in the room can ask for safe actions
  while the laptop is unlocked. That is why risky actions need the dialog click.
* The audit log detects tampering by anything that edits lines; someone with full control of your
  account could rewrite the whole file with a fresh chain.
* The wake word "hey jarvis" is a ready-made model. A custom wake word needs training your own model.

## Test status

Automated: 506 tests pass, 1 is skipped (`pip install pytest && pytest`). The skip is the symlink
test, which needs a Windows privilege most accounts do not have. The tests run against a simulated
Windows layer and cover phrases (a 318-sentence battery with must-not-match cases), the
permission gate, injection escalation, file confinement, URL building, routines, rules,
reminders, the audit chain, the Claude Code brain (with Claude replaced by a script), and voice
start/end detection.

Run on a real Windows 11 laptop (first on 13 November 2026, details in `CHANGELOG.md`):

* The installer, `aura doctor`, and text mode: open an app, volume, brightness, screenshot,
  typing, a site, a routine, a reminder. Each was checked against the real machine state.
* The Claude Code brain through WSL, with real free-form requests.
* Built-in requests answer in about 1.5-1.8 s through `aura once`, model requests in about 5.5 s.
* Voice mode with a real microphone: the wake word is heard. Two listener faults found on
  15 November (the command after the wake word came back empty) are fixed in code, but the fix
  is **not yet confirmed with a real voice**. Bluetooth earbud microphones score low on the wake
  word and are slow; a laptop microphone works better.

**Not yet tested by hand on real hardware:** the shutdown dialog click, the lock test, the
Ctrl+Alt+M privacy switch (the hotkey registers), a full spoken back-and-forth conversation,
window control (minimise, snap, show desktop), the dark-mode switch, emptying the Recycle Bin,
and `brightness_change` ("brighter" / "dim the screen"). They use standard, documented Windows
calls and pass against the simulated layer. Please go through the checklist below and report
anything that fails.

Known on some laptops: Ctrl+Alt+Space may already belong to another program. Aura then falls
back to another combination (Ctrl+Alt+J first) and tells you which one it took; set your own
with `voice.hotkey_talk` in `aura config`.

### First-run checklist

1. `aura doctor` - every line should say `ok`.
2. `aura text`, then: `open notepad`, `volume 30`, `brightness 60`, `take a screenshot`,
   `type hello`, `open gmail`, `job hunt`, `remind me to test in 1 minute`.
3. `shut down the laptop` - a dialog must appear; click **No**.
4. Ask something free-form: `open github and tell me the time`.
5. `aura run`, say "hey jarvis", wait for the beep, say "what time is it".
6. Press Win+L, say "hey jarvis, open notepad", unlock: Notepad must **not** have opened.
7. Press Ctrl+Alt+M (two-tone beep = microphone off), again to turn it back on.

Logs: `%APPDATA%\Aura\aura.log`. Uninstall: `powershell -ExecutionPolicy Bypass -File uninstall.ps1`.
