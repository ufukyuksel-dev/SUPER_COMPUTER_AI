#!/usr/bin/env python3
"""Export selected skills into a public plugin directory (stdlib only, Python 3.9+).

Usage:
  python3 scripts/export_plugin.py --out ../shippilot --skill mobile-store-release --skill growth-loop \
      --deny wordfall

Each skill is copied from skills/<category>/<name>/ to <out>/skills/<name>/ with project-specific content removed:
  - a Markdown file whose first line is '<!-- private -->' is not exported
  - '<!-- private:start -->' ... '<!-- private:end -->' blocks are removed from exported Markdown files
The exported tree is then checked before anything in <out> is replaced: the public-safety rules of validate.py
(home paths, secret patterns, forbidden key files), every --deny word (case-insensitive) and relative Markdown links
that point to files which were not exported. Any finding aborts the export and leaves <out> unchanged.
Exit codes: 0 exported, 1 findings, 2 usage/runtime error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parents[1]
PRIVATE_FILE = "<!-- private -->"
BLOCK_START = "<!-- private:start -->"
BLOCK_END = "<!-- private:end -->"
LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)")


class ExportError(Exception):
    pass


def load_validate():
    spec = importlib.util.spec_from_file_location("scai_validate", REPO / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strip_private(text: str, rel: str) -> str:
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        marker = line.strip()
        if marker == BLOCK_START:
            if inside:
                raise ExportError(f"{rel}: nested {BLOCK_START}")
            inside = True
        elif marker == BLOCK_END:
            if not inside:
                raise ExportError(f"{rel}: {BLOCK_END} without {BLOCK_START}")
            inside = False
        elif not inside:
            out.append(line)
    if inside:
        raise ExportError(f"{rel}: unclosed {BLOCK_START}")
    return "".join(out)


def skill_source(root: Path, name: str) -> Path:
    manifest = json.loads((root / "skills" / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["skills"].get(name)
    if entry is None:
        raise ExportError(f"unknown skill '{name}'")
    if entry.get("status") != "active":
        raise ExportError(f"skill '{name}' is not active")
    source = root / "skills" / entry["category"] / name
    if not (source / "SKILL.md").is_file():
        raise ExportError(f"{source.relative_to(root)}: SKILL.md missing")
    return source


def export_skill(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(source)
        dest = target / rel
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            if text.splitlines()[:1] == [PRIVATE_FILE]:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(strip_private(text, str(rel)), encoding="utf-8")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def check_tree(tree: Path, deny: List[str], validate) -> List[str]:
    findings = []
    words = [w.lower() for w in deny]
    for path in sorted(p for p in tree.rglob("*") if p.is_file()):
        rel = path.relative_to(tree).as_posix()
        if validate.FORBIDDEN_NAME.search(rel):
            findings.append(f"{rel}: forbidden file type")
            continue
        data = path.read_bytes()
        findings.extend(str(f) for f in validate.check_content(rel, data))
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            findings.extend(f"{rel}:{lineno}: denied word" for w in words if w in low)
            if path.suffix == ".md":
                for target in LINK.findall(line):
                    if not (path.parent / target.split("#")[0]).exists():
                        findings.append(f"{rel}:{lineno}: link to a file that was not exported")
    return findings


def run(root: Path, out: Path, names: List[str], deny: List[str]) -> List[str]:
    validate = load_validate()
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for name in names:
            export_skill(skill_source(root, name), staging / name)
        findings = check_tree(staging, deny, validate)
        if findings:
            return findings
        for name in names:
            dest = out / "skills" / name
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging / name, dest)
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="plugin root; skills go to <out>/skills/<name>")
    parser.add_argument("--skill", action="append", required=True, help="skill name (repeatable)")
    parser.add_argument("--deny", action="append", default=[], help="word that must not appear (repeatable)")
    args = parser.parse_args(argv)
    try:
        findings = run(REPO, args.out, args.skill, args.deny)
    except (ExportError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"FINDING: {finding}", file=sys.stderr)
        print("ERROR: export aborted; output unchanged", file=sys.stderr)
        return 1
    print(f"OK: exported {len(args.skill)} skill(s) to {args.out / 'skills'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
