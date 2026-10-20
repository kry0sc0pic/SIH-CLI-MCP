import json

import pytest
from typer.testing import CliRunner

from sih import install
from sih.cli import app

runner = CliRunner()
CMD = ["uv", "run", "--directory", "/x y", "sih-mcp"]


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(install.Path, "home", lambda: tmp_path)
    return tmp_path


def test_server_command_sources():
    assert install.server_command("git")[:3] == ["uvx", "--from", install.REPO_URL]
    assert install.server_command("local")[:3] == ["uv", "run", "--directory"]
    with pytest.raises(ValueError):
        install.server_command("nope")


def test_snippets():
    assert install.snippet("claude", CMD) == "claude mcp add sih -- uv run --directory '/x y' sih-mcp"
    assert install.snippet("codex", CMD).startswith("codex mcp add sih -- ")
    h = install.snippet("hermes", CMD)
    assert "mcp_servers:" in h and 'command: "uv"' in h and '- "sih-mcp"' in h
    assert json.loads(install.snippet("cursor", CMD).split("\n", 1)[1])["mcpServers"]["sih"]["command"] == "uv"
    oc = json.loads(install.snippet("opencode", CMD).split("\n", 1)[1])["mcp"]["sih"]
    assert oc["type"] == "local" and oc["command"] == CMD


@pytest.mark.parametrize("agent", ["cursor", "gemini", "opencode", "claude-desktop"])
def test_apply_json_merges_and_preserves(agent, fake_home):
    path = install._json_file(agent)
    path.parent.mkdir(parents=True)
    key = install._json_key(agent)
    path.write_text(json.dumps({key: {"other": {"command": "x"}}, "unrelated": 1}))
    install.apply(agent, CMD)
    data = json.loads(path.read_text())
    assert data["unrelated"] == 1 and "other" in data[key] and "sih" in data[key]
    install.apply(agent, CMD)  # idempotent
    assert list(json.loads(path.read_text())[key]) == ["other", "sih"]


def test_apply_creates_missing_file():
    install.apply("cursor", CMD)
    assert json.loads(install._json_file("cursor").read_text())["mcpServers"]["sih"]["args"][-1] == "sih-mcp"


def test_apply_refuses_non_json(fake_home):
    p = install._json_file("opencode")
    p.parent.mkdir(parents=True)
    p.write_text("{ // comment\n}")
    with pytest.raises(RuntimeError, match="not plain JSON"):
        install.apply("opencode", CMD)
    assert p.read_text() == "{ // comment\n}"  # untouched


def test_apply_hermes_refused():
    with pytest.raises(RuntimeError):
        install.apply("hermes", CMD)


def test_apply_cli_agents_shell_out(monkeypatch):
    seen = []

    class R:
        returncode, stdout, stderr = 0, "ok", ""

    monkeypatch.setattr(install.subprocess, "run", lambda a, **k: (seen.append(a), R)[1])
    install.apply("claude", CMD)
    assert seen[0][:4] == ["claude", "mcp", "add", "sih"] and seen[0][4] == "--" and seen[0][5:] == CMD


def test_apply_cli_failure_raises(monkeypatch):
    class R:
        returncode, stdout, stderr = 1, "", "boom"

    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: R)
    with pytest.raises(RuntimeError, match="boom"):
        install.apply("codex", CMD)


def test_cli_prints_by_default(fake_home):
    r = runner.invoke(app, ["install", "cursor", "--source", "git"])
    assert r.exit_code == 0 and "mcpServers" in r.output
    assert not install._json_file("cursor").exists()


def test_cli_all_and_apply(fake_home):
    r = runner.invoke(app, ["install", "all"])
    assert r.exit_code == 0 and all(a in r.output for a in install.AGENTS)
    r = runner.invoke(app, ["install", "cursor", "--apply", "--source", "git"])
    assert r.exit_code == 0 and install._json_file("cursor").exists()


def test_cli_unknown_agent():
    assert runner.invoke(app, ["install", "emacs"]).exit_code != 0


def test_cli_apply_failure_exit_code(monkeypatch):
    r = runner.invoke(app, ["install", "hermes", "--apply"])
    assert r.exit_code == 1
