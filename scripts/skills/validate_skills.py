#!/usr/bin/env python3
"""Validate skills and agent roles against skills/manifest.json and agents/manifest.json.

Layout: skills/<category>/<name>/SKILL.md; the path is derived from the manifest entry, never stored.
Profiles:
  strict  (AI-engineering skills) — full contract: 'Use when' + 'Do NOT use' triggers, required
          '## Tool Requirements & Degradation' heading, <=500 body lines, literal 'see skill <name>'
          cross-references, hash-bound agents/openai.yaml, routing row in
          instructions/global/30-ai-engineering-routing.md
  basic   — frontmatter name/description, name == directory, description <= 1024 chars,
          'see skill <name>' references resolve, agents/openai.yaml validated when present

Rules for every profile: skill-local markdown links ([text](references/x.md)) must resolve to an existing
file inside the skill directory; categories in STRICT_CATEGORIES must use the strict profile.

Layer 0 runs the official skill-creator quick_validate.py. Resolution order: $SKILL_CREATOR_HOME (must be valid
if set) -> the vendored copy in third_party/openai-skill-creator (checksum-verified) ->
$CODEX_HOME/skills/.system/skill-creator. --layer0 require (default) fails if none is usable; auto only warns;
skip is for unit-test fixtures. Requires PyYAML (requirements-dev.txt).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_RE = re.compile(r"\bsee skill\s+([a-z0-9]+(?:-[a-z0-9]+)*)\b", re.IGNORECASE)
HASH_RE = re.compile(r"^# skill-description-sha256: ([0-9a-f]{64})$")
REQUIRED_TOOL_KEYS = {"type", "value", "description"}
ALLOWED_TOOL_KEYS = REQUIRED_TOOL_KEYS | {"transport", "url"}
REQUIRED_BODY_HEADING = "## Tool Requirements & Degradation"

SKILLS_DIR = "skills"
SKILL_MANIFEST = "skills/manifest.json"
AGENT_MANIFEST = "agents/manifest.json"
ROUTING_FILE = "instructions/global/30-ai-engineering-routing.md"
MATRIX_FILE = "skills/ai-engineering/ai-system-design/references/capability-matrix.md"
PLATFORMS = ("claude", "codex")
PROFILES = ("strict", "basic")
STATUSES = ("active", "planned")
ROLE_FILE = {"claude": "agents/claude/{}.md", "codex": "agents/codex/{}.toml"}
STRICT_CATEGORIES = frozenset({"ai-engineering"})
VENDORED_CREATOR = Path(__file__).resolve().parents[2] / "third_party" / "openai-skill-creator"
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")  # code spans are not links


class ValidationSetupError(Exception):
    """Raised when validation cannot start."""


@dataclass(frozen=True)
class SkillDocument:
    path: Path
    name: str
    description: str
    body: str


@dataclass(frozen=True)
class SkillEntry:
    name: str
    category: str
    status: str
    profile: str
    platforms: Tuple[str, ...]
    bundles: Tuple[str, ...]

    def directory(self, repo: Path) -> Path:
        return repo / SKILLS_DIR / self.category / self.name


def _verify_vendored(root: Path) -> None:
    sums = root / "SHA256SUMS"
    if not sums.is_file():
        raise ValidationSetupError(f"FAIL: vendored skill-creator is missing {sums.name}")
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        target = root / name.strip()
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValidationSetupError(f"FAIL: vendored skill-creator file does not match SHA256SUMS: {name.strip()}")


def resolve_skill_creator_home() -> Optional[Path]:
    """Return a usable skill-creator root, None if none exists; raise if a configured/vendored one is broken."""
    configured = os.environ.get("SKILL_CREATOR_HOME")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not (root / "scripts" / "quick_validate.py").is_file():
            raise ValidationSetupError("FAIL: SKILL_CREATOR_HOME not found")
        return root
    if VENDORED_CREATOR.is_dir():
        _verify_vendored(VENDORED_CREATOR)
        return VENDORED_CREATOR
    codex_root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    root = (codex_root / "skills" / ".system" / "skill-creator").expanduser().resolve()
    if (root / "scripts" / "quick_validate.py").is_file():
        return root
    return None


def load_yaml_module() -> Any:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValidationSetupError(
            "FAIL: PyYAML is required; install requirements-dev.txt"
        ) from exc
    return yaml


def rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def add(errors: List[str], repo: Path, path: Path, reason: str) -> None:
    errors.append(f"FAIL {rel(path, repo)}: {reason}")


def _no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, repo: Path, errors: List[str]) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        add(errors, repo, path, "missing manifest")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (OSError, ValueError) as exc:
        add(errors, repo, path, f"invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        add(errors, repo, path, "manifest must be an object")
        return None
    return payload


def _string_tuple(value: Any, allowed: Optional[Sequence[str]] = None) -> Optional[Tuple[str, ...]]:
    if not isinstance(value, list) or not value:
        return None
    if any(not isinstance(item, str) or not NAME_RE.fullmatch(item) for item in value):
        return None
    if len(value) != len(set(value)):
        return None
    if allowed is not None and any(item not in allowed for item in value):
        return None
    return tuple(value)


def load_skill_manifest(repo: Path, errors: List[str]) -> Dict[str, SkillEntry]:
    path = repo / SKILL_MANIFEST
    payload = _read_json(path, repo, errors)
    if payload is None:
        return {}
    if set(payload) != {"schema_version", "skills"} or payload.get("schema_version") != 2:
        add(errors, repo, path, "must contain exactly schema_version (2) and skills")
        return {}
    skills = payload.get("skills")
    if not isinstance(skills, dict):
        add(errors, repo, path, "skills must be an object")
        return {}
    entries: Dict[str, SkillEntry] = {}
    required = {"category", "status", "profile", "platforms", "bundles"}
    for name, raw in skills.items():
        where = f"skills.{name}"
        if not NAME_RE.fullmatch(name):
            add(errors, repo, path, f"{where}: invalid skill name")
            continue
        if not isinstance(raw, dict) or set(raw) != required:
            add(errors, repo, path, f"{where}: must contain exactly " + ", ".join(sorted(required)))
            continue
        category = raw["category"]
        if not isinstance(category, str) or not NAME_RE.fullmatch(category):
            add(errors, repo, path, f"{where}.category must be a kebab-case name")
            continue
        if raw["status"] not in STATUSES:
            add(errors, repo, path, f"{where}.status must be one of {', '.join(STATUSES)}")
            continue
        if raw["profile"] not in PROFILES:
            add(errors, repo, path, f"{where}.profile must be one of {', '.join(PROFILES)}")
            continue
        platforms = _string_tuple(raw["platforms"], PLATFORMS)
        if platforms is None:
            add(errors, repo, path, f"{where}.platforms must be a non-empty unique subset of {', '.join(PLATFORMS)}")
            continue
        bundles = _string_tuple(raw["bundles"])
        if bundles is None:
            add(errors, repo, path, f"{where}.bundles must be a non-empty unique list of kebab-case names")
            continue
        profile = raw["profile"]
        if category in STRICT_CATEGORIES and profile != "strict":
            add(errors, repo, path, f"{where}.profile must be strict for category '{category}'")
            profile = "strict"  # keep validating the skill under the enforced profile
        entries[name] = SkillEntry(name, category, raw["status"], profile, platforms, bundles)
    return entries


def load_agent_manifest(repo: Path, errors: List[str]) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    path = repo / AGENT_MANIFEST
    payload = _read_json(path, repo, errors)
    if payload is None:
        return {}
    if set(payload) != {"schema_version", "roles"} or payload.get("schema_version") != 1:
        add(errors, repo, path, "must contain exactly schema_version (1) and roles")
        return {}
    roles = payload.get("roles")
    if not isinstance(roles, dict):
        add(errors, repo, path, "roles must be an object")
        return {}
    result: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {}
    for name, raw in roles.items():
        where = f"roles.{name}"
        if not NAME_RE.fullmatch(name) or not isinstance(raw, dict) or set(raw) != {"platforms", "bundles"}:
            add(errors, repo, path, f"{where}: kebab-case name with exactly platforms and bundles required")
            continue
        platforms = _string_tuple(raw["platforms"], PLATFORMS)
        bundles = _string_tuple(raw["bundles"])
        if platforms is None or bundles is None:
            add(errors, repo, path, f"{where}: platforms/bundles must be non-empty unique lists")
            continue
        result[name] = (platforms, bundles)
    return result


def parse_skill(path: Path, repo: Path, yaml: Any, errors: List[str]) -> Optional[SkillDocument]:
    if not path.is_file():
        add(errors, repo, path, "missing SKILL.md")
        return None
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)(.*)\Z", text, re.DOTALL)
    if not match:
        add(errors, repo, path, "missing closing frontmatter delimiter ---")
        return None
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        add(errors, repo, path, f"invalid frontmatter YAML: {exc}")
        return None
    if not isinstance(frontmatter, dict):
        add(errors, repo, path, "frontmatter must be a mapping")
        return None
    if set(frontmatter) != {"name", "description"}:
        add(errors, repo, path, "frontmatter must contain exactly name and description")
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not name.strip():
        add(errors, repo, path, "name must be a non-empty string")
        return None
    if not isinstance(description, str) or not description.strip():
        add(errors, repo, path, "description must be a non-empty string")
        return None
    return SkillDocument(path, name.strip(), description.strip(), match.group(2).lstrip("\r\n"))


def run_layer_zero(
    skill_dir: Path, creator: Path, repo: Path, errors: List[str]
) -> None:
    command = [sys.executable, str(creator / "scripts" / "quick_validate.py"), str(skill_dir)]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stdout or completed.stderr).strip().replace("\n", " | ")
        add(errors, repo, skill_dir / "SKILL.md", f"quick_validate.py: {detail}")


def validate_document(
    document: SkillDocument,
    directory_name: str,
    active: Set[str],
    planned: Set[str],
    repo: Path,
    errors: List[str],
    strict: bool = True,
) -> None:
    if document.name != directory_name:
        add(errors, repo, document.path, f"name '{document.name}' does not match directory '{directory_name}'")
    description = document.description
    if len(description) > 1024:
        add(errors, repo, document.path, "description exceeds 1024 characters")
    if not strict:
        validate_see_skill_references(document, active, planned, repo, errors)
        return
    if "Use when" not in description:
        add(errors, repo, document.path, "description must contain 'Use when'")
    if "Do NOT use" not in description:
        add(errors, repo, document.path, "description must contain a negative 'Do NOT use' trigger")
    body_lines = document.body.splitlines()
    if len(body_lines) > 500:
        add(errors, repo, document.path, f"body exceeds 500 lines ({len(body_lines)})")
    if REQUIRED_BODY_HEADING not in body_lines:
        add(errors, repo, document.path, f"missing required heading '{REQUIRED_BODY_HEADING}'")

    known = active | planned
    for target in sorted(known):
        target_pattern = re.compile(
            rf"(?<![a-z0-9-]){re.escape(target)}(?![a-z0-9-])",
            re.IGNORECASE,
        )
        for occurrence in target_pattern.finditer(document.body):
            line_start = document.body.rfind("\n", 0, occurrence.start()) + 1
            prefix = document.body[line_start:occurrence.start()]
            if not re.search(r"\bsee skill\s+$", prefix, re.IGNORECASE):
                add(
                    errors,
                    repo,
                    document.path,
                    f"cross-reference must use 'see skill {target}'",
                )
                break

    validate_see_skill_references(document, active, planned, repo, errors)


def validate_see_skill_references(
    document: SkillDocument, active: Set[str], planned: Set[str], repo: Path, errors: List[str]
) -> None:
    known = active | planned
    for match in REFERENCE_RE.finditer(document.body):
        target = match.group(1)
        if target not in known:
            add(errors, repo, document.path, f"cross-reference does not resolve: see skill {target}")
            continue
        if target in planned:
            line_start = document.body.rfind("\n", 0, match.start()) + 1
            line_end = document.body.find("\n", match.end())
            if line_end < 0:
                line_end = len(document.body)
            line = document.body[line_start:line_end].lower()
            if "when available, else" not in line:
                add(errors, repo, document.path, f"planned reference requires 'when available, else': see skill {target}")


def validate_openai_yaml(
    skill_dir: Path,
    document: Optional[SkillDocument],
    skill_name: str,
    repo: Path,
    yaml: Any,
    errors: List[str],
) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        add(errors, repo, path, "missing agents/openai.yaml")
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    match = HASH_RE.fullmatch(lines[0]) if lines else None
    if not match:
        add(errors, repo, path, "missing skill-description-sha256 comment")
    elif document is not None:
        expected = hashlib.sha256(document.description.encode("utf-8")).hexdigest()
        if match.group(1) != expected:
            add(errors, repo, path, "openai.yaml stale — regenerate")
    yaml_text = "\n".join(lines[1:] if match else lines)
    try:
        payload = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        add(errors, repo, path, f"invalid YAML: {exc}")
        return
    if not isinstance(payload, dict):
        add(errors, repo, path, "metadata must be a mapping")
        return

    document_node = yaml.compose(yaml_text)

    def validate_scalar_style(node: Any, node_path: str) -> None:
        if isinstance(node, yaml.nodes.MappingNode):
            for key_node, value_node in node.value:
                key_name = str(key_node.value)
                if key_node.style is not None:
                    add(
                        errors,
                        repo,
                        path,
                        f"YAML key must be unquoted: {node_path + '.' if node_path else ''}{key_name}",
                    )
                child_path = f"{node_path}.{key_name}" if node_path else key_name
                validate_scalar_style(value_node, child_path)
        elif isinstance(node, yaml.nodes.SequenceNode):
            for index, item in enumerate(node.value):
                validate_scalar_style(item, f"{node_path}[{index}]")
        elif (
            isinstance(node, yaml.nodes.ScalarNode)
            and node.tag == "tag:yaml.org,2002:str"
            and node.style not in {'"', "'"}
        ):
            add(errors, repo, path, f"YAML string value must be quoted: {node_path}")

    if document_node is not None:
        validate_scalar_style(document_node, "")

    allowed_top = {"interface", "dependencies", "policy"}
    unknown_top = set(payload) - allowed_top
    if unknown_top:
        add(errors, repo, path, "unknown top-level keys: " + ", ".join(sorted(unknown_top)))
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        add(errors, repo, path, "interface mapping is required")
    else:
        required = {"display_name", "short_description", "default_prompt"}
        allowed_interface = required | {
            "icon_small",
            "icon_large",
            "brand_color",
        }
        unknown_interface = set(interface) - allowed_interface
        if unknown_interface:
            add(
                errors,
                repo,
                path,
                "interface has unknown keys: "
                + ", ".join(sorted(str(item) for item in unknown_interface)),
            )
        missing = required - set(interface)
        if missing:
            add(errors, repo, path, "interface missing: " + ", ".join(sorted(missing)))
        for key in allowed_interface & set(interface):
            if not isinstance(interface[key], str) or not interface[key].strip():
                add(errors, repo, path, f"interface.{key} must be a non-empty string")
        short = interface.get("short_description")
        if isinstance(short, str) and not 25 <= len(short) <= 64:
            add(errors, repo, path, "interface.short_description must be 25-64 characters")
        prompt = interface.get("default_prompt")
        if isinstance(prompt, str) and f"${skill_name}" not in prompt:
            add(errors, repo, path, f"interface.default_prompt must mention ${skill_name}")
        brand = interface.get("brand_color")
        if isinstance(brand, str) and not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand):
            add(errors, repo, path, "interface.brand_color must be a six-digit hex color")
        for icon_key in ("icon_small", "icon_large"):
            icon = interface.get(icon_key)
            if not isinstance(icon, str):
                continue
            if not icon.startswith("./assets/") or ".." in Path(icon).parts:
                add(
                    errors,
                    repo,
                    path,
                    f"interface.{icon_key} must be a relative ./assets/ path",
                )
            elif not (skill_dir / icon[2:]).is_file():
                add(errors, repo, path, f"interface.{icon_key} asset does not exist")
    dependencies = payload.get("dependencies")
    if dependencies is not None:
        if not isinstance(dependencies, dict) or set(dependencies) != {"tools"}:
            add(errors, repo, path, "dependencies must contain only tools")
        else:
            tools = dependencies.get("tools")
            if not isinstance(tools, list):
                add(errors, repo, path, "dependencies.tools must be an array")
            else:
                for index, tool in enumerate(tools):
                    if not isinstance(tool, dict):
                        add(errors, repo, path, f"dependencies.tools[{index}] must be an object")
                        continue
                    missing = REQUIRED_TOOL_KEYS - set(tool)
                    unknown = set(tool) - ALLOWED_TOOL_KEYS
                    if missing or unknown:
                        detail = []
                        if missing:
                            detail.append("missing " + ", ".join(sorted(missing)))
                        if unknown:
                            detail.append("unknown " + ", ".join(sorted(unknown)))
                        add(errors, repo, path, f"dependencies.tools[{index}] " + "; ".join(detail))
                    if tool.get("type") != "mcp":
                        add(errors, repo, path, f"dependencies.tools[{index}].type must be mcp")
                    for key, value in tool.items():
                        if key in ALLOWED_TOOL_KEYS and (not isinstance(value, str) or not value.strip()):
                            add(errors, repo, path, f"dependencies.tools[{index}].{key} must be a non-empty string")
    policy = payload.get("policy")
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) != {"allow_implicit_invocation"}:
            add(errors, repo, path, "policy may contain only allow_implicit_invocation")
        elif not isinstance(policy.get("allow_implicit_invocation"), bool):
            add(errors, repo, path, "policy.allow_implicit_invocation must be boolean")




def validate_matrix(repo: Path, known: Set[str], errors: List[str]) -> None:
    path = repo / MATRIX_FILE
    if "ai-system-design" not in known or not path.is_file():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    found_owner_column = False
    owners: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.lstrip().startswith("|"):
            index += 1
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        lowered = [re.sub(r"[`*_]", "", cell).strip().lower() for cell in cells]
        owner_index = next(
            (i for i, cell in enumerate(lowered) if cell in {"responsible skill", "owner", "sorumlu skill"}),
            None,
        )
        if owner_index is None:
            index += 1
            continue
        found_owner_column = True
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            if owner_index < len(row):
                owners.extend(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", row[owner_index]))
            index += 1
    if not found_owner_column:
        add(errors, repo, path, "missing Responsible skill matrix column")
        return
    if not owners:
        add(errors, repo, path, "Responsible skill column contains no skill owners")
    for owner in sorted(set(owners)):
        if owner not in known:
            add(errors, repo, path, f"matrix responsible skill does not resolve: {owner}")


def validate_local_links(skill_dir: Path, repo: Path, errors: List[str]) -> None:
    """Every relative markdown link in the skill's .md files must hit an existing file inside the skill."""
    root = skill_dir.resolve()
    for md in sorted(skill_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in MARKDOWN_LINK_RE.finditer(INLINE_CODE_RE.sub("", line)):
                target = match.group(1)
                if target.startswith("#") or URL_SCHEME_RE.match(target) or target.startswith("//"):
                    continue
                path_part = target.split("#", 1)[0].split("?", 1)[0]
                if not path_part:
                    continue
                if path_part.startswith("/") or path_part.startswith("~"):
                    add(errors, repo, md, f"line {lineno}: link must be relative to the skill: {target}")
                    continue
                resolved = (md.parent / path_part).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError:
                    add(errors, repo, md, f"line {lineno}: link leaves the skill directory: {target}")
                    continue
                if not resolved.exists():
                    add(errors, repo, md, f"line {lineno}: link target does not exist: {target}")


def discover_skill_dirs(repo: Path) -> Dict[str, List[Path]]:
    """name -> directories found at skills/<category>/<name>/ (more than one = duplicate name)."""
    found: Dict[str, List[Path]] = {}
    root = repo / SKILLS_DIR
    if not root.is_dir():
        return found
    for category in sorted(root.iterdir()):
        if not category.is_dir() or category.name.startswith("."):
            continue
        for skill_dir in sorted(category.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                found.setdefault(skill_dir.name, []).append(skill_dir)
    return found


def validate_roles(repo: Path, errors: List[str]) -> None:
    roles = load_agent_manifest(repo, errors)
    for platform, pattern in ROLE_FILE.items():
        directory = (repo / pattern).parent
        suffix = Path(pattern).suffix
        on_disk = {p.stem for p in directory.glob("*" + suffix)} if directory.is_dir() else set()
        declared = {name for name, (platforms, _) in roles.items() if platform in platforms}
        for name in sorted(declared - on_disk):
            add(errors, repo, repo / pattern.format(name), "declared role file is missing")
        for name in sorted(on_disk - declared):
            add(errors, repo, repo / pattern.format(name), f"role file is not declared for {platform} in {AGENT_MANIFEST}")


def validate_repo(repo: Path, layer0: str = "require") -> Tuple[List[str], List[str]]:
    """Return (errors, notices)."""
    yaml = load_yaml_module()
    errors: List[str] = []
    notices: List[str] = []
    creator = None if layer0 == "skip" else resolve_skill_creator_home()
    if layer0 == "require" and creator is None:
        raise ValidationSetupError("FAIL: SKILL_CREATOR_HOME not found")
    if creator is None and layer0 != "skip":
        notices.append("NOTICE: Layer 0 (skill-creator quick_validate.py) skipped: SKILL_CREATOR_HOME not found")

    entries = load_skill_manifest(repo, errors)
    active = {n for n, e in entries.items() if e.status == "active"}
    planned = {n for n, e in entries.items() if e.status == "planned"}
    disk = discover_skill_dirs(repo)

    for name, dirs in sorted(disk.items()):
        if len(dirs) > 1:
            for directory in dirs:
                add(errors, repo, directory, f"skill name '{name}' is used in more than one category")
    for name in sorted(active):
        expected = entries[name].directory(repo)
        if not expected.is_dir():
            add(errors, repo, expected, "active skill is missing from disk")
    for name, dirs in sorted(disk.items()):
        entry = entries.get(name)
        for directory in dirs:
            if entry is None or entry.status != "active":
                add(errors, repo, directory, "on-disk skill is not active in manifest")
            elif directory != entry.directory(repo):
                add(errors, repo, directory, f"skill is in category '{directory.parent.name}' but manifest says '{entry.category}'")
    for name in sorted(planned):
        if entries[name].directory(repo).exists():
            add(errors, repo, entries[name].directory(repo), "planned skill must not exist on disk")

    routing_path = repo / ROUTING_FILE
    routing_text = routing_path.read_text(encoding="utf-8") if routing_path.is_file() else ""
    for name in sorted(active):
        entry = entries[name]
        skill_dir = entry.directory(repo)
        if not skill_dir.is_dir():
            continue
        strict = entry.profile == "strict"
        if strict and f"| `{name}` |" not in routing_text:
            add(errors, repo, routing_path, f"missing routing row for strict skill {name}")
        if creator is not None:
            run_layer_zero(skill_dir, creator, repo, errors)
        document = parse_skill(skill_dir / "SKILL.md", repo, yaml, errors)
        if document is not None:
            validate_document(document, name, active, planned, repo, errors, strict=strict)
        if strict or (skill_dir / "agents" / "openai.yaml").exists():
            validate_openai_yaml(skill_dir, document, name, repo, yaml, errors)
        validate_local_links(skill_dir, repo, errors)
    validate_matrix(repo, active | planned, errors)
    validate_roles(repo, errors)
    return errors, notices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]),
                        help="Repository root (default: this script's repository)")
    parser.add_argument("--layer0", choices=("auto", "require", "skip"), default="require")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    try:
        errors, notices = validate_repo(repo, args.layer0)
    except ValidationSetupError as exc:
        print(str(exc))
        return 1
    for notice in notices:
        print(notice, file=sys.stderr)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
