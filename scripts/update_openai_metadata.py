#!/usr/bin/env python3
"""Regenerate harness metadata and bind it to the SKILL.md description."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


HASH_PREFIX = "# skill-description-sha256: "
TOOL_KEYS = {"type", "value", "description", "transport", "url"}
REQUIRED_TOOL_KEYS = {"type", "value", "description"}


class MetadataError(Exception):
    """Raised for actionable metadata failures."""


def skill_creator_home() -> Path:
    configured = os.environ.get("SKILL_CREATOR_HOME")
    vendored = Path(__file__).resolve().parents[1] / "third_party" / "openai-skill-creator"
    if configured:
        root = Path(configured).expanduser().resolve()
    elif (vendored / "scripts" / "generate_openai_yaml.py").is_file():
        root = vendored
    else:
        codex_root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        root = (codex_root / "skills" / ".system" / "skill-creator").expanduser().resolve()
    if not root.is_dir():
        raise MetadataError("FAIL: SKILL_CREATOR_HOME not found")
    generator = root / "scripts" / "generate_openai_yaml.py"
    if not generator.is_file():
        raise MetadataError("FAIL: SKILL_CREATOR_HOME not found")
    return root


def _decode_scalar(raw: str, label: str) -> str:
    value = raw.strip()
    if not value:
        raise MetadataError(f"FAIL: SKILL.md {label} is empty")
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise MetadataError(f"FAIL: SKILL.md invalid quoted {label}: {exc}") from exc
        if not isinstance(decoded, str):
            raise MetadataError(f"FAIL: SKILL.md {label} must be a string")
        return decoded.strip()
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'").strip()
    return value


def read_frontmatter(skill_md: Path) -> Tuple[str, str]:
    if not skill_md.is_file():
        raise MetadataError(f"FAIL: {skill_md}: missing SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        raise MetadataError(f"FAIL: {skill_md}: invalid frontmatter")
    lines = match.group(1).splitlines()
    name: Optional[str] = None
    description: Optional[str] = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("name:"):
            name = _decode_scalar(line.split(":", 1)[1], "name")
        elif line.startswith("description:"):
            raw = line.split(":", 1)[1].strip()
            if raw in {">", ">-", "|", "|-"}:
                block: List[str] = []
                index += 1
                while index < len(lines) and (lines[index].startswith(" ") or not lines[index]):
                    block.append(lines[index].lstrip())
                    index += 1
                description = (" " if raw.startswith(">") else "\n").join(block).strip()
                continue
            description = _decode_scalar(raw, "description")
        index += 1
    if not name or not description:
        raise MetadataError(f"FAIL: {skill_md}: name and description are required")
    return name, description


def load_tools(path: Path) -> List[Dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetadataError(f"FAIL: invalid --mcp-tools-json: {exc}") from exc
    if not isinstance(payload, list):
        raise MetadataError("FAIL: --mcp-tools-json must contain a JSON array")
    tools: List[Dict[str, str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise MetadataError(f"FAIL: dependencies.tools[{index}] must be an object")
        keys = set(item)
        missing = REQUIRED_TOOL_KEYS - keys
        unknown = keys - TOOL_KEYS
        if missing or unknown:
            detail = []
            if missing:
                detail.append("missing " + ", ".join(sorted(missing)))
            if unknown:
                detail.append("unknown " + ", ".join(sorted(unknown)))
            raise MetadataError(f"FAIL: dependencies.tools[{index}] " + "; ".join(detail))
        if item.get("type") != "mcp":
            raise MetadataError(f"FAIL: dependencies.tools[{index}].type must be mcp")
        normalized: Dict[str, str] = {}
        for key in ("type", "value", "description", "transport", "url"):
            if key not in item:
                continue
            value = item[key]
            if not isinstance(value, str) or not value.strip():
                raise MetadataError(f"FAIL: dependencies.tools[{index}].{key} must be a non-empty string")
            normalized[key] = value.strip()
        tools.append(normalized)
    return tools


def _quoted_yaml(payload: Dict[str, Any]) -> str:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise MetadataError("FAIL: PyYAML is required for --mcp-tools-json") from exc

    class Quoted(str):
        pass

    class Dumper(yaml.SafeDumper):
        pass

    Dumper.add_representer(
        Quoted,
        lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"'),
    )

    def quote_values(value: Any) -> Any:
        if isinstance(value, str):
            return Quoted(value)
        if isinstance(value, list):
            return [quote_values(item) for item in value]
        if isinstance(value, dict):
            return {key: quote_values(item) for key, item in value.items()}
        return value

    return yaml.dump(
        quote_values(payload),
        Dumper=Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def regenerate(args: argparse.Namespace) -> Path:
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    name, description = read_frontmatter(skill_dir / "SKILL.md")
    if skill_dir.name != name:
        raise MetadataError(f"FAIL: {skill_dir}: frontmatter name does not match directory")
    if not 25 <= len(args.short_description) <= 64:
        raise MetadataError("FAIL: short description must be 25-64 characters")
    if f"${name}" not in args.default_prompt:
        raise MetadataError(f"FAIL: default prompt must mention ${name}")

    tools: Optional[List[Dict[str, str]]] = None
    if args.mcp_tools_json:
        tools = load_tools(Path(args.mcp_tools_json).expanduser().resolve())

    creator = skill_creator_home()
    output = skill_dir / "agents" / "openai.yaml"
    previous = output.read_bytes() if output.exists() else None
    command = [
        sys.executable,
        str(creator / "scripts" / "generate_openai_yaml.py"),
        str(skill_dir),
        "--name",
        name,
        "--interface",
        f"display_name={args.display_name}",
        "--interface",
        f"short_description={args.short_description}",
        "--interface",
        f"default_prompt={args.default_prompt}",
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise MetadataError(f"FAIL: generate_openai_yaml.py failed: {detail}")
        generated = output.read_text(encoding="utf-8")
        if tools is not None:
            try:
                import yaml
            except ModuleNotFoundError as exc:
                raise MetadataError("FAIL: PyYAML is required for --mcp-tools-json") from exc
            payload = yaml.safe_load(generated)
            if not isinstance(payload, dict):
                raise MetadataError("FAIL: generated openai.yaml is invalid")
            payload["dependencies"] = {"tools": tools}
            generated = _quoted_yaml(payload)
        digest = hashlib.sha256(description.encode("utf-8")).hexdigest()
        output.write_text(f"{HASH_PREFIX}{digest}\n{generated}", encoding="utf-8")
    except Exception:
        if previous is None:
            output.unlink(missing_ok=True)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(previous)
        raise
    print(f"OK {output.relative_to(skill_dir.parent.parent.parent)}")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--short-description", required=True)
    parser.add_argument("--default-prompt", required=True)
    parser.add_argument("--mcp-tools-json")
    return parser


def main() -> int:
    try:
        regenerate(build_parser().parse_args())
        return 0
    except MetadataError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
