import pytest


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path / "home"))
    from aura import config
    from aura.hub import Hub
    from aura.platform.stub import StubPlatform

    cfg = config.load()
    docs = tmp_path / "docs"
    docs.mkdir()
    cfg["files"].update(
        roots=[str(docs)], notes_dir=str(docs / "notes"), screenshots_dir=str(docs / "shots")
    )
    h = Hub(cfg=cfg, platform=StubPlatform())
    h.docs = docs
    h.spoken = []
    h.speak = h.spoken.append
    h.asked = []
    h.voice_answer = False

    def confirm(prompt):
        h.asked.append(prompt)
        return h.voice_answer

    h.confirm_voice = confirm
    return h
