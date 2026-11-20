"""The Claude Code brain: isolated, fast, one process per turn. Claude is replaced by a script."""

import json
import sys
import textwrap
import time

import pytest

from aura.brain import llm

FAKE = textwrap.dedent("""
    import json, os, sys, time
    mode = os.environ.get("FAKE_CLAUDE", "ok")
    log = os.environ["FAKE_CLAUDE_LOG"]
    with open(log, "a") as fh:
        fh.write(json.dumps({"pid": os.getpid(), "argv": sys.argv[1:]}) + "\\n")
    if mode == "dead":
        sys.exit(3)
    print("Welcome to the shell {not json}", flush=True)
    print(json.dumps({"tip": "a banner that is JSON"}), flush=True)
    seen = 0
    for line in sys.stdin:
        seen += 1
        text = json.loads(line)["message"]["content"]
        if mode == "hang" or (mode == "hang_once" and not os.path.exists(log + ".hung")):
            open(log + ".hung", "w").close()
            time.sleep(60)
        print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
        plan = {"say": "turn %d in pid %d: %s" % (seen, os.getpid(), text), "actions": [], "done": True}
        print(json.dumps({"type": "result", "is_error": mode == "error", "result": json.dumps(plan)}), flush=True)
""")


@pytest.fixture
def fake(hub, tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE", "ok")
    hub.cfg["brain"].update(claude_command=[sys.executable, str(script)], timeout_seconds=15)
    hub.calls = lambda: (
        [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    )
    made = []

    def make(warm=False):
        brain = llm.ClaudeCliBrain(hub, warm=warm)
        made.append(brain)
        return brain

    yield make
    for brain in made:
        brain.close()


def wait_for(condition, seconds=10.0):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_command_is_isolated_and_toolless(hub):
    hub.cfg["brain"].update(claude_command=["claude"], claude_model="haiku", claude_effort="low")
    brain = llm.ClaudeCliBrain(hub, warm=False)
    argv, env = brain.command()
    assert argv[argv.index("--tools") + 1] == ""  # no Claude Code tools at all
    for flag in (
        "--safe-mode",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--no-session-persistence",
    ):
        assert flag in argv  # no hooks, CLAUDE.md, plugins, skills, MCP
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--effort") + 1] == "low"
    # rules, tool list and answer format are the system prompt, read from a file in the sandbox
    prompt_file = argv[argv.index("--system-prompt-file") + 1]
    assert prompt_file == str(brain.sandbox / "system-prompt.txt")
    written = (brain.sandbox / "system-prompt.txt").read_text(encoding="utf-8")
    assert (
        written == brain.system_prompt()
        and llm.RULES in written
        and '"tool": "get_time"' in written
    )
    assert "Answer with ONE JSON object" in written
    # the config dir holds the sign-in: redirecting it makes every request fail with "Not logged in"
    assert env is None and not any("CLAUDE_CONFIG_DIR" in part for part in argv)


def test_shell_route_is_one_quoted_line(hub):
    import shlex

    hub.cfg["brain"].update(
        claude_command=["wsl", "-d", "kali-linux", "--", "bash", "-lic"], claude_model="haiku"
    )
    brain = llm.ClaudeCliBrain(hub, warm=False)
    argv, env = brain.command()
    assert argv[:6] == ["wsl", "-d", "kali-linux", "--", "bash", "-lic"] and len(argv) == 7
    assert env is None
    inner = shlex.split(argv[6])
    assert "CLAUDE_CONFIG_DIR" not in argv[6]  # the sign-in lives in the config dir
    assert inner[0] == "claude" and inner[inner.index("--tools") + 1] == ""
    # by name: the shell on the other side starts in the sandbox, a Windows path means nothing there
    assert inner[inner.index("--system-prompt-file") + 1] == "system-prompt.txt"
    assert (brain.sandbox / "system-prompt.txt").exists()
    assert "--safe-mode" in inner and inner[inner.index("--model") + 1] == "haiku"


def test_request_prompt_carries_only_what_changes(hub):
    brain = llm.ClaudeCliBrain(hub, warm=False)
    prompt = brain._prompt("what time is it", [{"tool": "get_time", "ok": True, "result": "noon"}])
    assert (
        llm.RULES not in prompt and "TOOLS YOU MAY REQUEST" not in prompt
    )  # those are cached, in the system prompt
    assert '"what time is it"' in prompt and "noon" in prompt and "CONTEXT:" in prompt


def test_next_spare_starts_when_one_is_taken(hub, fake):
    brain = fake(warm=True)
    assert wait_for(lambda: brain._spare is not None)
    first = brain._take()  # a request begins; it has not finished
    assert wait_for(lambda: brain._spare is not None and brain._spare is not first)
    first.close()
    brain.close()


def test_unsafe_model_value_is_dropped(hub):
    hub.cfg["brain"].update(
        claude_command=["bash", "-lc"], claude_model="haiku'; rm -rf ~ #", claude_effort=""
    )
    line = llm.ClaudeCliBrain(hub, warm=False).command()[0][-1]
    assert "--model" not in line and "rm -rf" not in line and "--effort" not in line


def test_default_config_is_fast(hub):
    brain = hub.cfg["brain"]
    assert (
        brain["claude_model"] == "haiku"
        and brain["claude_effort"] == "low"
        and brain["keep_warm"] is True
    )


def test_turn_skips_banner_and_returns_plan(fake):
    plan = fake()._ask("hello there")
    assert plan["say"].endswith(": hello there") and plan["actions"] == [] and plan["done"] is True


def test_every_turn_gets_a_fresh_process(hub, fake):
    brain = fake()
    first, second = brain._ask("one"), brain._ask("two")
    # "turn 1" both times: the second request never ran in a process that saw the first
    assert first["say"].startswith("turn 1 in pid") and second["say"].startswith("turn 1 in pid")
    assert first["say"].split()[4] != second["say"].split()[4]
    assert len(hub.calls()) == 2


def test_spare_is_started_ahead_and_used(hub, fake):
    brain = fake(warm=True)
    assert wait_for(lambda: brain._spare is not None and len(hub.calls()) == 1)
    spare, spare_pid = brain._spare, hub.calls()[0]["pid"]  # the pid the process itself reported
    plan = brain._ask("warm")
    assert f"in pid {spare_pid}:" in plan["say"]  # answered by the waiting process
    assert wait_for(
        lambda: brain._spare is not None and brain._spare is not spare
    )  # the next one is warming
    brain.close()
    assert brain._spare is None


def test_dead_spare_is_replaced(hub, fake):
    brain = fake(warm=True)
    assert wait_for(lambda: brain._spare is not None)
    brain._spare.proc.kill()
    brain._spare.proc.wait(timeout=5)
    assert brain._ask("after death")["say"].endswith(": after death")


def test_hung_turn_times_out_and_is_retried(hub, fake, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE", "hang_once")
    hub.cfg["brain"]["timeout_seconds"] = 1
    started = time.time()
    plan = fake()._ask("slow")
    assert plan["say"].endswith(": slow") and time.time() - started < 10
    assert len(hub.calls()) == 2


def test_two_failures_raise(hub, fake, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE", "dead")
    with pytest.raises(RuntimeError, match="exited 3"):
        fake()._ask("x")
    monkeypatch.setenv("FAKE_CLAUDE", "hang")
    hub.cfg["brain"]["timeout_seconds"] = 1
    with pytest.raises(RuntimeError, match="did not answer"):
        fake()._ask("x")


def test_claude_error_is_raised_not_acted_on(fake, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE", "error")
    with pytest.raises(RuntimeError, match="reported an error"):
        fake()._ask("x")


def test_brain_handle_runs_through_the_gate(hub, fake):
    brain = fake()
    hub.brain = brain
    assert "banana" in hub.handle("banana flavoured nonsense request", "text")
