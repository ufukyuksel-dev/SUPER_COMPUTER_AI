#!/usr/bin/env python3
"""Scaffold a new skill in skills/<category>/<name>/ and register it in skills/manifest.json.

Stdlib only (PyYAML is needed only with --mcp-tools-json). All-or-nothing: on any failure the created skill
directory is removed and the manifest is restored byte for byte.

  strict profile (default for categories in STRICT_CATEGORIES): writes the full-contract scaffold and the
      hash-bound agents/openai.yaml (needs --display-name, --short-description, --default-prompt) and prints the
      routing row to add to instructions/global/30-ai-engineering-routing.md.
  basic profile: needs --description; agents/openai.yaml is generated only if the three interface flags are given.

Examples:
  python3 scripts/new_skill.py video-subtitles --category media --description "Create subtitles ... Use when ..."
  python3 scripts/new_skill.py vector-db-ops --category ai-engineering --display-name "Vector DB Ops" \\
      --short-description "Operate vector databases in production" --default-prompt 'Use $vector-db-ops to ...'
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STRICT_CATEGORIES = {"ai-engineering"}
PLATFORMS = ("claude", "codex")


class ScaffoldError(Exception):
    pass


def strict_body(name: str, display: str) -> str:
    description = (
        f"Use when handling {display.lower()} work that matches this scaffold. "
        "Do NOT use when a more specific active skill owns the concern."
    )
    return f"""---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
---

# {display}

## Overview

Replace this scaffold with concise decision guidance for the named concern.

## Workflow

1. Confirm the requested outcome and constraints.
2. Apply the concern-specific decision process.
3. Return evidence, decisions, and unresolved items.

## Failure Modes

- Do not invent missing evidence.
- Stop at the skill boundary and hand off adjacent concerns explicitly.

## Tool Requirements & Degradation

State every required tool before use. If a required tool is unavailable, declare the limitation, do not simulate a result, and ask the human for the narrowest viable next step.
"""


def basic_body(name: str, description: str) -> str:
    title = name.replace("-", " ").capitalize()
    return f"""---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
---

# {title}

Describe the workflow: inputs, steps, verification, and what to do when a required tool or credential is missing.
Keep project-specific private values (paths, account IDs) out of this file; read them from
`${{SCAI_HOME:-~/.config/super-computer-ai}}/private/skills/{name}/` when they exist.
"""


def validate_args(args: argparse.Namespace, manifest: dict) -> str:
    if not NAME_RE.fullmatch(args.name) or len(args.name) > 64:
        raise ScaffoldError(f"invalid skill name: {args.name}")
    if not NAME_RE.fullmatch(args.category):
        raise ScaffoldError(f"invalid category: {args.category}")
    profile = args.profile or ("strict" if args.category in STRICT_CATEGORIES else "basic")
    if args.category in STRICT_CATEGORIES and profile != "strict":
        raise ScaffoldError(f"category '{args.category}' requires the strict profile")
    if args.name in manifest["skills"] or any((REPO / "skills").glob(f"*/{args.name}")):
        raise ScaffoldError(f"skill '{args.name}' already exists")
    for bundle in args.bundle:
        if not NAME_RE.fullmatch(bundle):
            raise ScaffoldError(f"invalid bundle name: {bundle}")
    interface = [args.display_name, args.short_description, args.default_prompt]
    if profile == "strict" and not all(interface):
        raise ScaffoldError("strict skills need --display-name, --short-description and --default-prompt")
    if any(interface) and not all(interface):
        raise ScaffoldError("--display-name, --short-description and --default-prompt go together")
    if all(interface):
        if not 25 <= len(args.short_description) <= 64:
            raise ScaffoldError("short description must be 25-64 characters")
        if f"${args.name}" not in args.default_prompt:
            raise ScaffoldError(f"default prompt must mention ${args.name}")
    if profile == "basic" and not args.description:
        raise ScaffoldError("basic skills need --description (what it does and when to use it)")
    if args.description and len(args.description) > 1024:
        raise ScaffoldError("description exceeds 1024 characters")
    return profile


def scaffold(args: argparse.Namespace) -> List[str]:
    manifest_path = REPO / "skills" / "manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    profile = validate_args(args, manifest)
    skill_dir = REPO / "skills" / args.category / args.name
    created_category = not skill_dir.parent.exists()
    messages: List[str] = []
    try:
        (skill_dir / "references").mkdir(parents=True)
        body = strict_body(args.name, args.display_name) if profile == "strict" else basic_body(args.name, args.description)
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
        if args.display_name:
            command = [sys.executable, str(REPO / "scripts" / "update_openai_metadata.py"), str(skill_dir),
                       "--display-name", args.display_name, "--short-description", args.short_description,
                       "--default-prompt", args.default_prompt]
            if args.mcp_tools_json:
                command += ["--mcp-tools-json", args.mcp_tools_json]
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            if result.returncode != 0:
                raise ScaffoldError((result.stdout + result.stderr).strip() or "metadata generation failed")
        manifest["skills"][args.name] = {
            "category": args.category,
            "status": "active",
            "profile": profile,
            "platforms": args.platform or list(PLATFORMS),
            "bundles": args.bundle or [args.category],
        }
        manifest["skills"] = dict(sorted(manifest["skills"].items()))
        tmp = manifest_path.with_name(".manifest.json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, manifest_path)
    except BaseException:
        shutil.rmtree(skill_dir, ignore_errors=True)
        if created_category and skill_dir.parent.exists() and not any(skill_dir.parent.iterdir()):
            skill_dir.parent.rmdir()
        manifest_path.write_bytes(original)
        raise
    messages.append(f"OK: created skills/{args.category}/{args.name} ({profile})")
    if profile == "strict":
        messages.append("ADD this routing row to instructions/global/30-ai-engineering-routing.md:")
        messages.append(f"| `{args.name}` | TODO: describe the concern boundary |")
    messages.append("NEXT: edit SKILL.md, then run python3 scripts/skills/validate_skills.py and python3 scripts/install.py")
    return messages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("name")
    parser.add_argument("--category", required=True)
    parser.add_argument("--profile", choices=("strict", "basic"))
    parser.add_argument("--bundle", action="append", default=[], help="install bundle(s); default: the category")
    parser.add_argument("--platform", action="append", choices=PLATFORMS, default=[])
    parser.add_argument("--description")
    parser.add_argument("--display-name")
    parser.add_argument("--short-description")
    parser.add_argument("--default-prompt")
    parser.add_argument("--mcp-tools-json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        for line in scaffold(args):
            print(line)
    except (ScaffoldError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
