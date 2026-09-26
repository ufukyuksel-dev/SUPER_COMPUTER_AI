"""Secrets and runtime state live outside the repository (SUPER_COMPUTER_AI import)."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from jev import env, paths


def test_defaults_are_outside_the_checkout(monkeypatch, tmp_path):
    monkeypatch.delenv("JEV_ENV_FILE", raising=False)
    monkeypatch.delenv("JEV_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    checkout = Path(paths.__file__).resolve().parents[2]
    assert paths.env_file() == tmp_path / ".config/super-computer-ai/credentials/jev/.env"
    assert paths.state_dir() == tmp_path / ".local/state/super-computer-ai/jev"
    for p in (paths.env_file(), paths.state_dir()):
        assert checkout not in p.parents


def test_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_ENV_FILE", str(tmp_path / "x.env"))
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path / "state"))
    assert paths.env_file() == tmp_path / "x.env"
    assert paths.state_dir() == tmp_path / "state"


def test_state_root_is_private(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path / "state"))
    target = paths.ensure_dir(tmp_path / "state" / "chrome-profile-x")
    assert target.is_dir()
    assert stat.S_IMODE((tmp_path / "state").stat().st_mode) == 0o700


STARTUP = r"""
import json, os, sys
from jev import agent, mcp_server, runlog  # imported before config is loaded, as the entry points do
from jev import browser, env
env.load()                                   # mcp_server.main() / cli.main() order
agent.TaskStore("t1").add("spec", goal="g")
runlog.record("g", {"url": "http://x/", "title": "X", "status": "done", "steps": []})
mcp_server._log_takeover({"tool": "jev_click"})
print(json.dumps({"profile": str(browser.profile_dir("claude")), "tasks": str(agent.tasks_dir()),
                  "runs": str(runlog.runs_file()), "takeovers": str(mcp_server.takeover_log())}))
"""


def test_state_dir_from_env_file_applies_to_every_writer(tmp_path):
    """Regression: JEV_STATE_DIR set only in the .env must reach profiles and all logs (fresh process, no reload)."""
    state = tmp_path / "from-dotenv"
    dotenv = tmp_path / "jev.env"
    dotenv.write_text(f"JEV_STATE_DIR={state}\n")
    child_env = {k: v for k, v in os.environ.items() if k not in ("JEV_STATE_DIR", "TYPESAFE_API_KEY")}
    child_env.update(HOME=str(tmp_path / "home"), JEV_ENV_FILE=str(dotenv))
    out = subprocess.run([sys.executable, "-c", STARTUP], env=child_env, capture_output=True, text=True, check=True)
    got = {k: Path(v) for k, v in json.loads(out.stdout.strip().splitlines()[-1]).items()}
    assert got == {"profile": state / "chrome-profile-claude", "tasks": state / "tasks",
                   "runs": state / "runs.jsonl", "takeovers": state / "takeovers.jsonl"}
    assert (state / "tasks" / "t1.jsonl").is_file()
    assert got["runs"].is_file() and got["takeovers"].is_file()
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert not (tmp_path / "home" / ".local").exists()  # nothing leaked to the default location


def test_env_load_reads_only_the_configured_file(monkeypatch, tmp_path):
    checkout_env = Path(paths.__file__).resolve().parents[2] / ".env"
    assert not checkout_env.exists(), "a .env inside the checkout must never exist"
    secret = tmp_path / "jev.env"
    secret.write_text("JEV_TEST_ONLY_VALUE=from-file\nJEV_TEST_EXPORTED=from-file\n")
    monkeypatch.setenv("JEV_ENV_FILE", str(secret))
    monkeypatch.delenv("JEV_TEST_ONLY_VALUE", raising=False)
    monkeypatch.setenv("JEV_TEST_EXPORTED", "exported")
    env.load()
    assert os.environ["JEV_TEST_ONLY_VALUE"] == "from-file"
    assert os.environ["JEV_TEST_EXPORTED"] == "exported"  # exported values win
    monkeypatch.delenv("JEV_TEST_ONLY_VALUE")
    monkeypatch.setenv("JEV_ENV_FILE", str(tmp_path / "missing.env"))
    env.load()  # a missing file is not an error and loads nothing
    assert "JEV_TEST_ONLY_VALUE" not in os.environ
