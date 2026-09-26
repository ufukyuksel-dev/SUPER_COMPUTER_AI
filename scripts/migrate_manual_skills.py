#!/usr/bin/env python3
"""Read-only report: compare hand-copied skill directories with their managed version (plan §4.4.8).

For every entry under sources.manual-copies in scripts/migration/source_map.json, each recorded source directory
that still exists in HOME is compared with skills/<category>/<name>: missing/extra files and a unified diff of
changed files. Nothing is written. After reviewing the report, replace a copy with
`python3 scripts/install.py --adopt-manual <name>` (backed up, journaled, reversible with --rollback).
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]


def files(root: Path) -> Dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*"))
            if p.is_file() and p.name != ".DS_Store"}


def report(home: Path, max_lines: int) -> List[str]:
    manifest = json.loads((REPO / "skills" / "manifest.json").read_text(encoding="utf-8"))["skills"]
    manual = json.loads((REPO / "scripts" / "migration" / "source_map.json").read_text(encoding="utf-8"))
    out: List[str] = []
    for name, spec in sorted(manual["sources"]["manual-copies"]["skills"].items()):
        managed = REPO / "skills" / manifest[name]["category"] / name
        for raw in spec.get("sources") or [spec["source"]]:
            source = home / raw[2:] if raw.startswith("~/") else Path(raw)
            label = f"{name} <- {raw}"
            if source.is_symlink():
                out.append(f"== {label}: already a link ({source.resolve()}) — nothing to adopt")
                continue
            if not source.is_dir():
                out.append(f"== {label}: not present")
                continue
            ours, theirs = files(managed), files(source)
            out.append(f"== {label}: hand-copied directory present")
            for rel in sorted(set(theirs) - set(ours)):
                out.append(f"   only in copy:    {rel}")
            for rel in sorted(set(ours) - set(theirs)):
                out.append(f"   only in managed: {rel}")
            for rel in sorted(set(ours) & set(theirs)):
                a = theirs[rel].read_text(encoding="utf-8", errors="replace").splitlines()
                b = ours[rel].read_text(encoding="utf-8", errors="replace").splitlines()
                if a == b:
                    out.append(f"   identical:       {rel}")
                    continue
                diff = list(difflib.unified_diff(a, b, f"copy/{rel}", f"managed/{rel}", lineterm="", n=1))
                out.append(f"   differs:         {rel} ({len(diff)} diff lines)")
                out.extend("      " + line for line in diff[:max_lines])
                if len(diff) > max_lines:
                    out.append(f"      ... {len(diff) - max_lines} more lines (use --max-lines)")
            out.append(f"   to replace it:   python3 scripts/install.py --adopt-manual {name}")
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--max-lines", type=int, default=60)
    args = parser.parse_args(argv)
    for line in report(Path(args.home).expanduser(), args.max_lines):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
