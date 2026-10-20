"""Register the sih MCP server with coding agents."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

REPO_URL = "git+https://github.com/kry0sc0pic/SIH-CLI-MCP"
NAME = "sih"
_ROOT = Path(__file__).resolve().parents[2]

AGENTS = ("claude", "codex", "gemini", "cursor", "opencode", "claude-desktop", "hermes")


def server_command(source: str | None = None) -> list[str]:
    """Command that launches the server: local checkout if present, else straight from GitHub via uvx."""
    source = source or ("local" if (_ROOT / "pyproject.toml").exists() else "git")
    if source == "local":
        return ["uv", "run", "--directory", str(_ROOT), "sih-mcp"]
    if source == "git":
        return ["uvx", "--from", REPO_URL, "sih-mcp"]
    raise ValueError("source must be 'local' or 'git'")


def _json_file(agent: str) -> Path:
    home = Path.home()
    return {
        "gemini": home / ".gemini" / "settings.json",
        "cursor": home / ".cursor" / "mcp.json",
        "opencode": home / ".config" / "opencode" / "opencode.json",
        "claude-desktop": home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    }[agent]


def _entry(agent: str, cmd: list[str]) -> dict:
    if agent == "opencode":
        return {"type": "local", "command": cmd, "enabled": True}
    return {"command": cmd[0], "args": cmd[1:]}


def _json_key(agent: str) -> str:
    return "mcp" if agent == "opencode" else "mcpServers"


def snippet(agent: str, cmd: list[str]) -> str:
    """What to run or paste to register the server with `agent`."""
    if agent == "claude":
        return f"claude mcp add {NAME} -- {shlex.join(cmd)}"
    if agent == "codex":
        return f"codex mcp add {NAME} -- {shlex.join(cmd)}"
    if agent == "hermes":
        args = "".join(f"\n      - {json.dumps(a)}" for a in cmd[1:])
        return f"# add to ~/.hermes/config.yaml\nmcp_servers:\n  {NAME}:\n    command: {json.dumps(cmd[0])}\n    args:{args}"
    body = {_json_key(agent): {NAME: _entry(agent, cmd)}}
    return f"# merge into {_json_file(agent)}\n{json.dumps(body, indent=2)}"


def apply(agent: str, cmd: list[str]) -> str:
    """Register the server. Returns a human-readable result; raises RuntimeError on failure."""
    if agent in ("claude", "codex"):
        r = subprocess.run([agent, "mcp", "add", NAME, "--", *cmd], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip() or f"{agent} mcp add failed")
        return (r.stdout or f"Added to {agent}").strip()
    if agent == "hermes":
        raise RuntimeError("hermes config is YAML; paste the snippet printed by `sih install hermes` instead")
    path = _json_file(agent)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{path} is not plain JSON ({e}); paste the snippet manually") from e
    data.setdefault(_json_key(agent), {})[NAME] = _entry(agent, cmd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return f"Wrote {NAME} to {path}"
