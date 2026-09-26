"""Where Jev keeps secrets and runtime state — never inside the repository.

JEV_ENV_FILE   dotenv file with TYPESAFE_API_KEY / PLAYWRIGHT_MCP_EXTENSION_TOKEN
               (default: ~/.config/super-computer-ai/credentials/jev/.env; loaded only if it exists)
JEV_STATE_DIR  browser profiles, task/run/takeover logs (default: ~/.local/state/super-computer-ai/jev, mode 0700)
"""
from __future__ import annotations

import os
from pathlib import Path


def env_file() -> Path:
    value = os.environ.get("JEV_ENV_FILE")
    return Path(value).expanduser() if value else Path.home() / ".config" / "super-computer-ai" / "credentials" / "jev" / ".env"


def state_dir() -> Path:
    value = os.environ.get("JEV_STATE_DIR")
    return Path(value).expanduser() if value else Path.home() / ".local" / "state" / "super-computer-ai" / "jev"


def ensure_dir(path: Path) -> Path:
    """Create path; the state root itself is private (0700) because browser profiles hold cookies and sessions."""
    root = state_dir()
    if path == root or root in path.parents:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
    path.mkdir(parents=True, exist_ok=True)
    return path
