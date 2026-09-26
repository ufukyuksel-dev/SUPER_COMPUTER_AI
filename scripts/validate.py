#!/usr/bin/env python3
"""Repository public-safety validator (stdlib only, Python 3.9+).

Two modes:
  default     working tree: files Git would commit (tracked + untracked, respecting .gitignore),
              contents read from disk
  --staged    index: exactly what the next commit contains (contents read from index blobs);
              used by the pre-commit hook

Checks:
  - required root files exist
  - forbidden file types: .env files (except .env.example) and ALL key/certificate containers
    (.pem, .p12, .pfx, .key, id_rsa, id_ed25519) — public certificates included, by policy
  - symlinks: target must be relative and stay inside the repository (the link is not followed)
  - no machine-specific absolute home paths (Unicode user names included)
  - no common secret/token patterns (gitleaks in CI/pre-commit is the broader scanner)

Reviewed exceptions: .public-safety-allowlist.json may exempt specific home-path tokens (by file and exact path
prefix, with a reason) — e.g. test fixtures of a path sanitizer. Secret patterns and forbidden files can never be
exempted; an entry that no longer matches anything is itself a finding (stale).

Findings never print the matched value. Exit codes: 0 clean, 1 findings, 2 usage/runtime error.
Later phases extend this with skill-manifest and MCP-registry checks.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, NamedTuple, Optional, Tuple

REQUIRED_ROOT_FILES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "THIRD_PARTY_NOTICES.md",
    ".gitignore",
)

MAX_TEXT_BYTES = 2_000_000
SYMLINK_MODE = "120000"
GITLINK_MODE = "160000"

# Patterns are assembled from pieces so this file does not match itself.
_PK = "-----BEGIN " + r"(?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
SECRET_PATTERNS = (
    ("private-key", re.compile(_PK)),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("meta-access-token", re.compile(r"\bEAA[A-Za-z0-9]{60,}")),
)

# /Users/<name>, /home/<name>, C:\Users\<name>. <name> must start with a word character (Unicode-aware),
# so documentation placeholders such as "/Users/..." are allowed.
HOME_PATH = re.compile(r"(?<![\w.])(?:/(?:Users|home)/[\w-][\w.-]*|[A-Za-z]:\\Users\\[\w-]+)")

ALLOWLIST_FILE = ".public-safety-allowlist.json"
ALLOWED_RULES = ("home-path",)

FORBIDDEN_NAME = re.compile(
    r"(?:^|/)(?:\.env(?:\.(?!example$)[^/]+)?|id_rsa|id_ed25519|id_ecdsa|[^/]*\.(?:pem|p12|pfx|key))$"
)


class Finding(NamedTuple):
    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: {self.rule}"


class Entry(NamedTuple):
    path: str
    is_symlink: bool
    load: object  # callable returning bytes (file content, or link target for symlinks)


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def working_tree_entries(root: Path) -> Iterator[Entry]:
    """Files Git would commit, read from the working tree."""
    out = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for rel in sorted({p for p in out.decode("utf-8").split("\0") if p}):
        path = root / rel
        if path.is_symlink():
            yield Entry(rel, True, lambda p=path: os.readlink(p).encode("utf-8"))
        elif path.is_file():
            yield Entry(rel, False, path.read_bytes)
        # deleted-but-tracked files: nothing to scan


def staged_entries(root: Path) -> Iterator[Entry]:
    """Exactly the next commit's content, read from index blobs."""
    out = _git(root, "ls-files", "-z", "--stage")
    for record in out.decode("utf-8").split("\0"):
        if not record:
            continue
        meta, rel = record.split("\t", 1)
        mode, sha, _stage = meta.split(" ")
        if mode == GITLINK_MODE:
            continue
        yield Entry(rel, mode == SYMLINK_MODE, lambda s=sha: _git(root, "cat-file", "blob", s))


def check_required(present: set) -> Iterable[Finding]:
    for name in REQUIRED_ROOT_FILES:
        if name not in present:
            yield Finding(name, 0, "missing required root file")


def check_symlink(rel: str, target: str) -> Iterable[Finding]:
    if target.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", target):
        yield Finding(rel, 0, "symlink with absolute target")
        return
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
    if resolved == ".." or resolved.startswith("../"):
        yield Finding(rel, 0, "symlink target escapes the repository")


class Allowlist:
    def __init__(self, entries: List[dict]):
        self.entries = entries
        self.used = [False] * len(entries)

    @classmethod
    def parse(cls, data: Optional[bytes]) -> "Tuple[Allowlist, List[Finding]]":
        if data is None:
            return cls([]), []
        try:
            payload = json.loads(data.decode("utf-8"))
        except ValueError as exc:
            return cls([]), [Finding(ALLOWLIST_FILE, 0, f"invalid JSON: {exc}")]
        problems: List[Finding] = []
        entries = []
        if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), list):
            return cls([]), [Finding(ALLOWLIST_FILE, 0, "must be {schema_version: 1, entries: [...]}")]
        for index, entry in enumerate(payload["entries"]):
            ok = (isinstance(entry, dict) and set(entry) == {"path", "rule", "match", "reason"}
                  and entry.get("rule") in ALLOWED_RULES
                  and all(isinstance(entry.get(k), str) and entry[k].strip() for k in ("path", "match", "reason"))
                  and HOME_PATH.fullmatch(entry["match"].rstrip("/")) is not None)
            if not ok:
                problems.append(Finding(ALLOWLIST_FILE, 0, f"entry {index}: needs path, rule (home-path), "
                                                           "match (a home-path prefix) and reason"))
                continue
            entries.append(entry)
        return cls(entries), problems

    def allows(self, rel: str, token: str) -> bool:
        for index, entry in enumerate(self.entries):
            prefix = entry["match"].rstrip("/")
            if entry["path"] == rel and (token == prefix or token.startswith(prefix + "/")):  # whole components only
                self.used[index] = True
                return True
        return False

    def stale(self) -> Iterable[Finding]:
        for entry, used in zip(self.entries, self.used):
            if not used:
                yield Finding(ALLOWLIST_FILE, 0, f"stale entry for {entry['path']} ({entry['match']}): matches nothing")


def check_content(rel: str, data: bytes, allow: "Optional[Allowlist]" = None) -> Iterable[Finding]:
    if len(data) > MAX_TEXT_BYTES or b"\0" in data[:8192]:
        return  # binary or very large: covered by gitleaks
    text = data.decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        tokens = [] if rel == ALLOWLIST_FILE else [m.group(0) for m in HOME_PATH.finditer(line)]  # validated by schema
        if tokens and not all(allow is not None and allow.allows(rel, t) for t in tokens):
            yield Finding(rel, lineno, "machine-specific absolute home path")
        for rule, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                yield Finding(rel, lineno, f"possible secret ({rule})")


def check_entry(entry: Entry, allow: "Optional[Allowlist]" = None) -> Iterable[Finding]:
    if FORBIDDEN_NAME.search(entry.path):
        yield Finding(entry.path, 0,
                      "forbidden file type (.env / key or certificate container); keep it in "
                      "~/.config/super-computer-ai/")
        return
    data = entry.load()
    if entry.is_symlink:
        yield from check_symlink(entry.path, data.decode("utf-8", errors="replace"))
    else:
        yield from check_content(entry.path, data, allow)


def validate(root: Path, staged: bool = False) -> List[Finding]:
    entries = list(staged_entries(root) if staged else working_tree_entries(root))
    if staged:
        present = {e.path for e in entries if not e.is_symlink}
    else:
        present = {name for name in REQUIRED_ROOT_FILES if (root / name).is_file()}
    findings = list(check_required(present))
    allow_entry = next((e for e in entries if e.path == ALLOWLIST_FILE and not e.is_symlink), None)
    allow, problems = Allowlist.parse(allow_entry.load() if allow_entry else None)
    findings.extend(problems)
    for entry in entries:
        findings.extend(check_entry(entry, allow))
    findings.extend(allow.stale())
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--staged", action="store_true", help="validate the index (next commit) instead of the working tree")
    args = parser.parse_args(argv)
    try:
        findings = validate(args.root.resolve(), staged=args.staged)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding)
    if findings:
        print(f"FAIL: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("OK: no findings" + (" (staged)" if args.staged else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
