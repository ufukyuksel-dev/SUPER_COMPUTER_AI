#!/usr/bin/env python3
"""Launch a local MCP server instance written by scripts/install.py --mcp. Stdlib only, Python 3.9+.

Usage: run_mcp.py --spec <instances.json> <instance> --client claude|codex

Reads nothing but the given spec (absolute, install-time-resolved values): no ~, no $HOME, no $SCAI_HOME. Then
  0. removes the variables listed in "unset" from the inherited environment (legacy aliases; for account-specific
     servers the optional settings the instance does not set) so another account's exports can never leak in,
  1. loads the instance's credentials .env if it exists (must be a regular file only its owner can read or write),
     accepting only the server's secret variables listed in "secret_keys" (anything else is ignored, named on
     stderr); variables already exported win,
  2. applies the instance env from the spec (it wins over inherited values: an instance never falls back to another
     instance's configuration exported in the shell),
  3. replaces {client} in the arguments and execs the server.
stdout belongs to the MCP protocol: every message of this wrapper goes to stderr. Exit 2 on any setup error.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from typing import Dict, List, Optional


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"run_mcp: {message}", file=sys.stderr)
    sys.exit(2)


def parse_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, sep, value = line.partition("=")
            key = key.strip()
            if not sep or not key.replace("_", "").isalnum():
                fail(f"{path}:{number}: expected NAME=value")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def load_credentials(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {}
    except OSError as exc:
        fail(f"cannot read credentials file: {exc}")
    if not stat.S_ISREG(info.st_mode):
        fail(f"credentials file {path} must be a regular file")
    if info.st_mode & 0o077 or info.st_uid != os.getuid():
        fail(f"credentials file {path} must belong to you and be readable only by you (chmod 600)")
    return parse_env_file(path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True)
    parser.add_argument("instance")
    parser.add_argument("--client", required=True, choices=["claude", "codex"])
    args = parser.parse_args(argv)
    if not os.path.isabs(args.spec):
        fail("--spec must be an absolute path")
    try:
        with open(args.spec, encoding="utf-8") as handle:
            spec = json.load(handle)
        entry = spec["instances"][args.instance]
    except FileNotFoundError:
        fail(f"spec {args.spec} not found (run scripts/install.py --mcp)")
    except KeyError:
        fail(f"instance {args.instance!r} is not in {args.spec} (run scripts/install.py --mcp)")
    except (OSError, ValueError) as exc:
        fail(f"cannot read spec {args.spec}: {exc}")
    env = dict(os.environ)
    for key in entry.get("unset") or []:   # never inherit another account's configuration or a legacy alias
        env.pop(key, None)
    allowed = set(entry.get("secret_keys") or [])   # the credentials file may only supply the server's secrets
    ignored = []
    for key, value in load_credentials(entry.get("credentials_env_file")).items():
        if key in allowed:
            env.setdefault(key, value)
        else:
            ignored.append(key)
    if ignored:
        print(f"run_mcp: ignoring non-secret keys in {entry.get('credentials_env_file')}: {', '.join(sorted(ignored))} "
              "(configuration belongs in the instance definition)", file=sys.stderr)
    env.update(entry.get("env") or {})
    command = entry["command"]
    argv_out = [command] + [a.replace("{client}", args.client) for a in entry.get("args", [])]
    try:
        os.execve(command, argv_out, env)
    except OSError as exc:
        fail(f"cannot start {command}: {exc}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
