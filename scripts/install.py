#!/usr/bin/env python3
"""Install SUPER_COMPUTER_AI skills, agent roles and global instructions into Claude Code and Codex.

Stdlib only, Python 3.9+. What it manages (and nothing else):
  skills     <claude>/skills/<name>   and  ~/.agents/skills/<name>    -> skills/<category>/<name>
             (+ <codex>/skills/<name> only with --codex-legacy-skills-dir)
  roles      <claude>/agents/<role>.md  and  <codex>/agents/<role>.toml -> agents/{claude,codex}/...
  block      one sentinel-delimited block in <claude>/CLAUDE.md and <codex>/AGENTS.md, rendered from
             instructions/global/*.md (a first-line marker '<!-- bundles: a, b -->' limits a file to bundles)
  mcp        (--mcp, a cutover action: Claude Code and Codex must be closed) one entry per MCP instance in Claude's
             ~/.claude.json (user or local scope) and <codex>/config.toml, from mcp/registry.json plus the private
             overlay's mcp/instances.json; local servers start through scripts/run_mcp.py and a launch spec in the
             state directory. Entries are edited one at a time; every other byte of those files is kept.
<claude> = $CLAUDE_CONFIG_DIR or ~/.claude, <codex> = $CODEX_HOME or ~/.codex (with --home: <home>/.claude, ...).

Safety model (plan §4.4):
  * Ownership: an existing path is changed only if the installer's ownership record (or a legacy installer
    record, verified against the real link target) says we own it in exactly its current state. Anything else
    is a conflict and nothing is written.
  * Every run is a write-ahead journal of single-target steps (planned -> intent -> done) persisted with
    fsync. --resume finishes an interrupted run; --rollback undoes it. Recovery is three-state: current ==
    before -> apply, current == after -> already applied, anything else -> conflict (never overwrite).
  * One exclusive lock (flock) per state directory; an open journal blocks new runs.
  * State (journals, blobs, backups) lives in ~/.local/state/super-computer-ai with dirs 0700 / files 0600.

Exit codes: 0 ok, 1 drift (--check), 2 conflict, 3 filesystem/usage error, 4 blocked (lock or open journal).
"""
from __future__ import annotations

import argparse
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.dont_write_bytecode = True  # the installer never writes into the checkout, not even __pycache__ (plan §8.3 i)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scai_mcp as mcp  # noqa: E402  (stdlib-only sibling module)

REPO = Path(__file__).resolve().parents[1]
BEGIN = "<!-- super-computer-ai:managed:begin -->"
END = "<!-- super-computer-ai:managed:end -->"
LEGACY_BEGIN = "<!-- ai-developer:managed:begin -->"
LEGACY_END = "<!-- ai-developer:managed:end -->"
BUNDLE_MARKER = re.compile(r"^<!--\s*bundles:\s*([a-z0-9, -]+?)\s*-->\s*$")
RECORD_VERSION = 1
EXIT_OK, EXIT_DRIFT, EXIT_CONFLICT, EXIT_ERROR, EXIT_BLOCKED = 0, 1, 2, 3, 4
ABSENT: Dict[str, Any] = {"type": "absent"}


class InstallError(Exception):
    exit_code = EXIT_ERROR


class Conflict(InstallError):
    exit_code = EXIT_CONFLICT


class Blocked(InstallError):
    exit_code = EXIT_BLOCKED


# --------------------------------------------------------------------------------------------- environment


@dataclass(frozen=True)
class Homes:
    home: Path
    claude: Path
    codex: Path
    agents: Path
    state: Path
    claude_json: Path   # Claude Code's own config (MCP entries): ~/.claude.json, or $CLAUDE_CONFIG_DIR/.claude.json
    scai: Path          # $SCAI_HOME or ~/.config/super-computer-ai (credentials/, private/); with --home: <home>/...

    @classmethod
    def resolve(cls, home_arg: Optional[str]) -> "Homes":
        if home_arg:
            home = Path(home_arg).expanduser().resolve()
            return cls(home, home / ".claude", home / ".codex", home / ".agents",
                       home / ".local" / "state" / "super-computer-ai", home / ".claude.json",
                       home / ".config" / "super-computer-ai")
        home = Path(os.path.realpath(Path.home()))
        env = os.environ
        claude_dir = Path(os.path.realpath(Path(env["CLAUDE_CONFIG_DIR"]).expanduser())) if env.get("CLAUDE_CONFIG_DIR") \
            else None
        return cls(
            home,
            claude_dir or home / ".claude",
            Path(os.path.realpath(Path(env["CODEX_HOME"]).expanduser())) if env.get("CODEX_HOME") else home / ".codex",
            home / ".agents",
            home / ".local" / "state" / "super-computer-ai",
            (claude_dir / ".claude.json") if claude_dir else home / ".claude.json",
            Path(os.path.realpath(Path(env["SCAI_HOME"]).expanduser())) if env.get("SCAI_HOME")
            else home / ".config" / "super-computer-ai",
        )

    @property
    def codex_toml(self) -> Path:
        return self.codex / "config.toml"

    @property
    def mcp_spec(self) -> Path:
        return self.state / "mcp" / "instances.json"

    def anchors(self) -> List[Path]:
        """Trusted roots: HOME and explicitly configured client roots (already realpath-resolved)."""
        roots = [self.home]
        for root in (self.claude, self.codex):
            if self.home not in root.parents and root != self.home:
                roots.append(root)
        return roots

    def redirected(self, path: Path) -> Optional[str]:
        """Why writing at path could escape the managed roots (symlinked ancestor), or None if it is safe."""
        anchor = max((a for a in self.anchors() if a in path.parents), key=lambda a: len(a.parts), default=None)
        if anchor is None:
            return f"{path} is outside the managed roots"
        current = anchor
        for part in path.relative_to(anchor).parts[:-1]:
            current = current / part
            if current.is_symlink():
                return f"{path}: ancestor {current} is a symlink (redirected path; refusing to write through it)"
            if current.exists() and not current.is_dir():
                return f"{path}: ancestor {current} is not a directory"
        return None

    @property
    def record(self) -> Path:
        return self.state / "ownership.json"

    @property
    def journals(self) -> Path:
        return self.state / "journals"

    @property
    def blobs(self) -> Path:
        return self.state / "blobs"

    @property
    def backups(self) -> Path:
        return self.state / "backups"


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.scai-tmp-{os.getpid()}")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fchmod(fd, mode)  # explicit: the process umask (077) must not change the recorded mode
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> Optional[str]:
    """SHA-256 of a regular file's content, None if it does not exist (symlinks and directories are not files)."""
    if path.is_symlink() or not path.is_file():
        return None if not (path.is_symlink() or path.exists()) else "not-a-file"
    return _sha(path.read_bytes())


def _tree_sha(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path).as_posix()
        mode = oct(stat.S_IMODE(item.lstat().st_mode))
        if item.is_symlink():
            digest.update(f"L {rel} {os.readlink(item)}\n".encode())
        elif item.is_file():
            digest.update(f"F {rel} {mode} {_sha(item.read_bytes())}\n".encode())
        else:
            digest.update(f"D {rel} {mode}\n".encode())
    return digest.hexdigest()


def _mode_manifest(root: Path) -> Dict[str, int]:
    """Original modes of a directory tree ('.' = the directory itself); symlinks carry no mode."""
    modes = {".": stat.S_IMODE(root.lstat().st_mode)}
    for item in sorted(root.rglob("*")):
        if not item.is_symlink():
            modes[item.relative_to(root).as_posix()] = stat.S_IMODE(item.lstat().st_mode)
    return modes


def _privatize(root: Path) -> None:
    """Backup storage: directories 0700, files 0600 (original modes live in the journal's manifest). Idempotent."""
    for index, item in enumerate(sorted(root.rglob("*"), reverse=True)):
        if not item.is_symlink():
            os.chmod(item, 0o700 if item.is_dir() else 0o600)
        if index == 0:
            _fault("privatize:partial")
    os.chmod(root, 0o700)


def _backup_intact(root: Path, before: Dict[str, Any], modes: Dict[str, int]) -> bool:
    """True if a (possibly partially privatized) backup still holds exactly the journaled original: every entry's
    mode is either its original mode or the private mode, and the tree hash computed with the ORIGINAL modes
    equals the journaled 'before' hash."""
    if before.get("mode") is not None and modes.get(".") != before["mode"]:
        return False
    if stat.S_IMODE(root.lstat().st_mode) not in (modes.get("."), 0o700):
        return False
    digest = hashlib.sha256()
    seen = set()
    for item in sorted(root.rglob("*")):
        rel = item.relative_to(root).as_posix()
        if item.is_symlink():
            digest.update(f"L {rel} {os.readlink(item)}\n".encode())
            continue
        if rel not in modes:
            return False
        seen.add(rel)
        actual = stat.S_IMODE(item.lstat().st_mode)
        private = 0o700 if item.is_dir() else 0o600
        if actual not in (modes[rel], private):
            return False
        mode = oct(modes[rel])
        if item.is_file():
            digest.update(f"F {rel} {mode} {_sha(item.read_bytes())}\n".encode())
        else:
            digest.update(f"D {rel} {mode}\n".encode())
    if seen != set(modes) - {"."}:
        return False
    return digest.hexdigest() == before.get("sha256")


def _restore_modes(root: Path, modes: Dict[str, int]) -> None:
    for rel, mode in sorted(modes.items(), key=lambda kv: kv[0].count("/"), reverse=True):
        target = root if rel == "." else root / rel
        if target.exists() and not target.is_symlink():
            os.chmod(target, mode)


EMPTY_DIR_SHA = hashlib.sha256().hexdigest()
NEW_DIR_MODE = 0o755
NEW_FILE_MODE = 0o644


def observe_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Current state of one MCP client entry (not the whole file)."""
    path = Path(entry["file"])
    raw = path.read_bytes() if path.is_file() else None
    try:
        canonical = mcp.entry_get(entry["format"], raw, entry["scope"], entry["name"])
    except mcp.McpError as exc:
        raise Conflict(f"{path}: {exc}") from exc
    if canonical is None:
        return dict(ABSENT)
    return {"type": "entry", "sha256": _sha(canonical.encode("utf-8"))}


def observe(path: Path) -> Dict[str, Any]:
    """Current state of a path, comparable with plan states."""
    if path.is_symlink():
        return {"type": "link", "to": os.readlink(path)}
    if not path.exists():
        return dict(ABSENT)
    mode = stat.S_IMODE(path.lstat().st_mode)
    if path.is_dir():
        return {"type": "dir", "sha256": _tree_sha(path), "mode": mode}
    return {"type": "file", "sha256": _sha(path.read_bytes()), "mode": mode}


def same_state(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    keys = ("type", "to", "sha256", "mode")
    return all(a.get(k) == b.get(k) for k in keys)


def describe(state: Dict[str, Any]) -> str:
    if state["type"] == "entry":
        return f"mcp entry sha256:{state['sha256'][:12]}"
    if state["type"] == "link":
        return f"link -> {state['to']}"
    if state["type"] in ("file", "dir"):
        return f"{state['type']} sha256:{state['sha256'][:12]} mode:{oct(state.get('mode', 0))}"
    return "absent"


# --------------------------------------------------------------------------------------------- repository model


@dataclass
class Catalog:
    skills: Dict[str, Dict[str, Any]]
    roles: Dict[str, Dict[str, Any]]
    instruction_files: List[Tuple[str, Optional[Tuple[str, ...]], str]]  # (name, bundles|None, body)
    source_map: Dict[str, Any]

    @property
    def bundles(self) -> List[str]:
        names = set()
        for entry in list(self.skills.values()) + list(self.roles.values()):
            names.update(entry["bundles"])
        for _, bundles, _ in self.instruction_files:
            names.update(bundles or ())
        return sorted(names)


def load_catalog(repo: Path) -> Catalog:
    try:
        skills = json.loads((repo / "skills" / "manifest.json").read_text(encoding="utf-8"))["skills"]
        roles = json.loads((repo / "agents" / "manifest.json").read_text(encoding="utf-8"))["roles"]
        source_map = json.loads((repo / "scripts" / "migration" / "source_map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise InstallError(f"cannot read repository manifests: {exc}") from exc
    files = []
    for path in sorted((repo / "instructions" / "global").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        match = BUNDLE_MARKER.match(first)
        bundles = tuple(b.strip() for b in match.group(1).split(",") if b.strip()) if match else None
        files.append((path.name, bundles, (rest if match else text).strip()))
    return Catalog({n: e for n, e in skills.items() if e.get("status") == "active"}, roles, files, source_map)


def render_block(catalog: Catalog, selected: Sequence[str]) -> str:
    parts = [
        "<!-- Generated by SUPER_COMPUTER_AI scripts/install.py from instructions/global/. "
        "Do not edit here: change the repository and rerun the installer. -->"
    ]
    for name, bundles, body in catalog.instruction_files:
        if bundles is None or set(bundles) & set(selected):
            parts.append(body)
    return BEGIN + "\n" + "\n\n".join(parts) + "\n" + END


def _find_block(text: str, begin: str, end: str) -> Optional[Tuple[int, int]]:
    b, e = text.count(begin), text.count(end)
    if b == 0 and e == 0:
        return None
    if b != 1 or e != 1 or text.find(begin) > text.find(end):
        raise Conflict(f"malformed managed block ({begin!r} x{b}, {end!r} x{e})")
    return text.find(begin), text.find(end) + len(end)


def replace_block(text: str, new_block: Optional[str], legacy_owned: bool,
                  prefix: str = "", suffix: str = "") -> Tuple[str, str, str]:
    """Set our block to new_block (None = remove) and return (text, prefix, suffix).

    prefix/suffix are the exact separators this installer added around an appended block; they are stored in
    the ownership record so removal restores the surrounding foreign text byte for byte. A legacy block is
    replaced in place (no separators added).
    """
    ours = _find_block(text, BEGIN, END)
    legacy = _find_block(text, LEGACY_BEGIN, LEGACY_END) if legacy_owned else None
    if legacy and ours:
        text = text[: legacy[0]] + text[legacy[1]:]
        ours, legacy = _find_block(text, BEGIN, END), None
    span = ours or legacy
    if span is None:
        if new_block is None:
            return text, prefix, suffix
        prefix = ("\n" if text and not text.endswith("\n") else "") + ("\n" if text.strip() else "")
        suffix = "\n"
        return text + prefix + new_block + suffix, prefix, suffix
    start, stop = span
    if new_block is None:
        if prefix and text[max(0, start - len(prefix)):start] == prefix:
            start -= len(prefix)
        if suffix and text[stop:stop + len(suffix)] == suffix:
            stop += len(suffix)
        return text[:start] + text[stop:], "", ""
    if legacy:
        prefix, suffix = "", ""
    return text[:start] + new_block + text[stop:], prefix, suffix


def block_inner_sha(text: str) -> Optional[str]:
    span = _find_block(text, BEGIN, END)
    return None if span is None else _sha(text[span[0]:span[1]].encode("utf-8"))


# --------------------------------------------------------------------------------------------- ownership


def load_record(homes: Homes) -> Optional[Dict[str, Any]]:
    if not homes.record.exists():
        return None
    try:
        record = json.loads(homes.record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"unreadable ownership record {homes.record}: {exc}") from exc
    if record.get("schema_version") != RECORD_VERSION:
        raise InstallError(f"unsupported ownership record version in {homes.record}")
    return record


@dataclass
class Legacy:
    """Links/blocks owned by the two legacy installers, verified against their actual link targets."""
    links: Dict[str, str] = field(default_factory=dict)   # path -> expected current link target
    names: Dict[str, str] = field(default_factory=dict)   # path -> skill/role name (for bundle checks)
    block_files: List[str] = field(default_factory=list)
    records: List[Path] = field(default_factory=list)


def _canon(raw: str) -> Path:
    """Canonical form of a link path: resolve the parent directory, never the link itself."""
    path = Path(raw).expanduser()
    return Path(os.path.realpath(path.parent)) / path.name


def load_legacy(homes: Homes, catalog: Catalog) -> Legacy:
    legacy = Legacy()
    smap = catalog.source_map["sources"]
    ad_record = homes.agents / "ai-developer-install.json"
    if ad_record.is_file():
        data = json.loads(ad_record.read_text(encoding="utf-8"))
        root = Path(data["repo_root"])
        skill_names = set(smap["AI_Developer"]["skills"]["names"])
        role_names = set(smap["AI_Developer"]["roles"]["names"])
        roles = smap["AI_Developer"]["roles"]
        for raw in data.get("links", []):
            path = _canon(raw)
            name = path.name
            if path.parent in (homes.claude / "skills", homes.agents / "skills") and name in skill_names:
                expected = root / smap["AI_Developer"]["skills"]["from"].format(name=name)
            elif path.parent == homes.claude / "agents" and path.suffix == ".md" and path.stem in role_names:
                expected, name = root / roles["claude"]["from"].format(name=path.stem), path.stem
            elif path.parent == homes.codex / "agents" and path.suffix == ".toml" and path.stem in role_names:
                expected, name = root / roles["codex"]["from"].format(name=path.stem), path.stem
            else:
                continue  # not part of the source map: never adopted
            legacy.links[str(path)] = str(expected)
            legacy.names[str(path)] = name
        legacy.block_files = [str(_canon(p)) for p in data.get("instruction_files", [])]
        legacy.records.append(ad_record)
    as_record = homes.home / ".ai-skills-install.json"
    if as_record.is_file():
        data = json.loads(as_record.read_text(encoding="utf-8"))
        names = smap["AI_SKILLS"]["skills"]["names"]
        for raw_path, raw_target in data.items():
            path = _canon(raw_path)
            if path.name in names and path.parent in (homes.claude / "skills", homes.codex / "skills"):
                legacy.links[str(path)] = raw_target
                legacy.names[str(path)] = path.name
        legacy.records.append(as_record)
    return legacy


# --------------------------------------------------------------------------------------------- planning


@dataclass
class Step:
    target: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    why: str
    backup: Optional[str] = None  # dir moves: where the directory goes
    entry: Optional[Dict[str, Any]] = None  # MCP entry steps: {format, file, scope, name, layout}; target = file


@dataclass
class Plan:
    steps: List[Step]
    conflicts: List[str]
    notices: List[str]
    record: Dict[str, Any]
    selected: List[str]
    infos: List[str] = field(default_factory=list)   # informational only (never drift)


def desired_links(catalog: Catalog, homes: Homes, repo: Path, selected: Sequence[str],
                  codex_legacy: bool) -> Dict[str, Tuple[str, str]]:
    """path -> (link target, item name)."""
    want: Dict[str, Tuple[str, str]] = {}
    chosen = set(selected)
    for name, entry in sorted(catalog.skills.items()):
        if not chosen & set(entry["bundles"]):
            continue
        source = str(repo / "skills" / entry["category"] / name)
        if "claude" in entry["platforms"]:
            want[str(homes.claude / "skills" / name)] = (source, name)
        if "codex" in entry["platforms"]:
            want[str(homes.agents / "skills" / name)] = (source, name)
            if codex_legacy:
                want[str(homes.codex / "skills" / name)] = (source, name)
    for name, entry in sorted(catalog.roles.items()):
        if not chosen & set(entry["bundles"]):
            continue
        if "claude" in entry["platforms"]:
            want[str(homes.claude / "agents" / f"{name}.md")] = (str(repo / "agents" / "claude" / f"{name}.md"), name)
        if "codex" in entry["platforms"]:
            want[str(homes.codex / "agents" / f"{name}.toml")] = (str(repo / "agents" / "codex" / f"{name}.toml"), name)
    return want


def select_bundles(catalog: Catalog, record: Optional[Dict[str, Any]], add: Sequence[str],
                   remove: Sequence[str]) -> Tuple[List[str], bool]:
    """Return (selected bundles, select_all). 'all' (the first-install default or --bundle all) is kept symbolic so
    bundles added to the repository later are picked up; --remove-bundle turns it into an explicit list."""
    known = set(catalog.bundles) | {"all"}
    for name in list(add) + list(remove):
        if name not in known:
            raise InstallError(f"unknown bundle '{name}' (known: {', '.join(catalog.bundles)}, all)")
    if record is None:
        select_all = not add or "all" in add
        base = set(catalog.bundles) if select_all else set(add)
    else:
        select_all = bool(record.get("select_all")) or "all" in add
        base = (set(catalog.bundles) if select_all else set(record.get("selected_bundles", []))) | (set(add) - {"all"})
    if remove:
        select_all = False
        base -= set(catalog.bundles) if "all" in remove else set(remove)
    return sorted(base), select_all


@dataclass
class McpOptions:
    enabled: Optional[bool] = None          # --mcp / --no-mcp (None = keep the recorded choice)
    overlay: Optional[str] = None           # --overlay DIR
    remove: Sequence[str] = ()              # --remove-mcp INSTANCE
    python: Optional[str] = None            # --python for the generated entries


def plan_mcp(repo: Path, homes: Homes, owned: Dict[str, Dict[str, Any]], selected: Sequence[str], enabled: bool,
             opts: McpOptions, conflicts: List[str], notices: List[str], infos: List[str],
             ensure_parents: Any) -> Tuple[List[Step], List[Step], Dict[str, Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Plan MCP entries. Returns (entry steps, trailing steps, record items, desired spec file state or None).

    Never touches entries this installer does not own unless the private mcp_map lists their exact fingerprint."""
    owned_entries = {k: v for k, v in owned.items() if v.get("type") == "entry"}
    if not enabled and not owned_entries:
        return [], [], {}, None
    overlay_dir = Path(opts.overlay).expanduser() if opts.overlay else homes.scai / "private"
    removals = set(opts.remove)
    desired: Dict[str, Dict[str, Any]] = {}
    spec_instances: Dict[str, Dict[str, Any]] = {}
    try:
        registry = mcp.load_registry(repo)
        mcp_map = mcp.load_mcp_map(overlay_dir)
    except mcp.McpError as exc:
        conflicts.append(str(exc))
        return [], [], {}, None
    servers = registry["servers"]
    owned_instances = {v["instance"] for v in owned_entries.values()}
    if enabled:
        overlay = mcp.load_overlay(overlay_dir, registry, homes.home)
        if overlay.error:
            conflicts.append(f"private overlay unreadable: {overlay.error}")
            return [], [], {}, None
        chosen = [n for n, s in sorted(servers.items()) if set(s["bundles"]) & set(selected)]
        instances: List[mcp.Instance] = []
        for server in chosen:
            owned_overlay = any(v["server"] == server and v["origin"] == "overlay" for v in owned_entries.values())
            if server in overlay.servers_defined or owned_overlay:
                instances += [i for i in overlay.instances.values() if i.server == server]
                continue
            defaults, reason = mcp.default_instances(registry, server, homes.home, homes.scai)
            if reason:
                infos.append(f"MCP {reason}")
            instances += defaults
        for name, reason in sorted(overlay.invalid.items()):
            if name in removals:
                continue
            if name in owned_instances:
                conflicts.append(f"MCP instance '{name}' is installed but its overlay definition is now invalid ({reason}); "
                                 f"fix it, or remove it explicitly with --remove-mcp {name}")
            else:
                notices.append(f"MCP instance '{name}' not installed: {reason}")
        for value in owned_entries.values():
            name = value["instance"]
            if (value["origin"] == "overlay" and name not in overlay.instances and name not in overlay.invalid
                    and name not in removals and value["server"] in chosen):
                conflicts.append(f"MCP instance '{name}' is installed but no longer defined in the overlay "
                                 f"({overlay_dir / 'mcp' / 'instances.json'}); remove it explicitly with --remove-mcp {name}")
        python = mcp.resolve_python(opts.python)
        for inst in instances:
            if inst.name in removals:
                continue
            reg = servers[inst.server]
            if reg["kind"] == "local":
                try:
                    spec = mcp.spec_record(inst, reg, repo, homes.scai)
                except ValueError as exc:
                    if inst.name in owned_instances:
                        conflicts.append(f"MCP instance '{inst.name}' is installed but cannot be launched: {exc}")
                    else:
                        notices.append(f"MCP instance '{inst.name}' not installed: {exc}")
                    continue
                missing = mcp.missing_build_output(spec, reg, repo)
                if missing:
                    notices.append(f"MCP instance '{inst.name}': {missing} does not exist yet; build it with "
                                   f"`{reg.get('build')}` in {reg['path']}")
                spec_instances[inst.name] = spec
            for client in inst.clients:
                if client == "claude":
                    fmt, file, scope = "claude-json", homes.claude_json, inst.claude_scope
                    canonical = mcp.claude_canonical(mcp.claude_entry(inst, reg, repo, python, homes.mcp_spec))
                else:
                    fmt, file, scope = "codex-toml", homes.codex_toml, "user"
                    canonical = mcp.codex_render(inst.name, mcp.codex_entry(inst, reg, repo, python, homes.mcp_spec))
                desired[f"mcp:{client}:{scope}:{inst.name}"] = {
                    "format": fmt, "file": str(file), "scope": scope, "name": inst.name, "canonical": canonical,
                    "client": client, "instance": inst.name, "server": inst.server, "origin": inst.origin}
    conflicted = {c.split("'")[1] for c in conflicts if c.startswith("MCP instance '")}

    # simulate the edits file by file (validates them now and yields the layout each entry will have)
    raws: Dict[str, Optional[bytes]] = {}

    def raw_of(file: str) -> Optional[bytes]:
        if file not in raws:
            raws[file] = Path(file).read_bytes() if Path(file).is_file() else None
        return raws[file]

    steps: List[Step] = []
    tail: List[Step] = []
    items: Dict[str, Dict[str, Any]] = {}

    def current(d: Dict[str, Any]) -> Optional[str]:
        return mcp.entry_get(d["format"], raw_of(d["file"]), d["scope"], d["name"])

    def simulate(d: Dict[str, Any], canonical: Optional[str], layout: Dict[str, Any]) -> Dict[str, Any]:
        new, used = mcp.entry_set(d["format"], raw_of(d["file"]), d["scope"], d["name"], canonical, layout)
        raws[d["file"]] = new
        return used

    def state(canonical: Optional[str]) -> Dict[str, Any]:
        if canonical is None:
            return dict(ABSENT)
        return {"type": "entry", "sha256": _sha(canonical.encode("utf-8")), "content": canonical}

    for key, d in sorted(desired.items()):
        try:
            cur = current(d)
            spec = {k: d[k] for k in ("format", "file", "scope", "name")}
            record = {"type": "entry", "sha256": _sha(d["canonical"].encode("utf-8")), "client": d["client"],
                      "instance": d["instance"], "server": d["server"], "origin": d["origin"], **spec}
            if cur == d["canonical"]:
                items[key] = dict(record, layout=owned.get(key, {}).get("layout", {}))
                continue
            exact = _sha(cur.encode("utf-8")) if cur is not None else None
            fingerprint = mcp.entry_fingerprint(d["format"], cur) if cur is not None else None
            mapped = mcp_map.get(f"{d['client']}/{d['scope']}/{d['name']}", {})
            if cur is not None and not (key in owned_entries and owned_entries[key]["sha256"] == exact) \
                    and mapped.get("sha256") != fingerprint:
                conflicts.append(f"{d['file']}: {d['client']} MCP entry '{d['name']}' ({d['scope']}) exists and is not "
                                 f"owned by this installer (fingerprint sha256:{fingerprint}); review it and list it in "
                                 f"private/migration/mcp_map.json to let the installer replace it")
                continue
            if cur is None and raw_of(d["file"]) is None:
                ensure_parents(d["file"])
            layout = simulate(d, d["canonical"], owned.get(key, {}).get("layout", {}) if cur is not None else {})
            verb = "add" if cur is None else ("update" if key in owned_entries else "adopt")
            steps.append(Step(d["file"], state(cur), state(d["canonical"]),
                              f"{verb} mcp {d['client']}:{d['scope']}:{d['name']}", entry=dict(spec, layout=layout)))
            items[key] = dict(record, layout=layout)
        except mcp.McpError as exc:
            conflicts.append(f"{d['file']}: {exc}")

    # owned entries that are no longer wanted
    for key, value in sorted(owned_entries.items()):
        if key in desired:
            continue
        spec = {k: value[k] for k in ("format", "file", "scope", "name")}
        if value["instance"] in conflicted:
            items[key] = value  # kept exactly as installed until the conflict is resolved
            continue
        try:
            cur = current(value)
            if cur is None:
                continue
            if _sha(cur.encode("utf-8")) != value["sha256"]:
                conflicts.append(f"{value['file']}: MCP entry '{value['name']}' changed since install; not removing it")
                items[key] = value
                continue
            layout = simulate(value, None, value.get("layout", {}))
            steps.append(Step(value["file"], state(cur), dict(ABSENT),
                              f"remove mcp {value['client']}:{value['scope']}:{value['name']}",
                              entry=dict(spec, layout=value.get("layout", {}))))
        except mcp.McpError as exc:
            conflicts.append(f"{value['file']}: {exc}")

    # legacy names retired by the private mcp_map (exact fingerprint only)
    if enabled:
        for mkey, mapped in sorted(mcp_map.items()):
            if not mapped.get("retire"):
                if "/project:" in mkey:
                    conflicts.append(f"mcp_map key {mkey!r}: project-scope entries can only be retired (add \"retire\": true)")
                continue
            client, _, rest = mkey.partition("/")
            scope, _, name = rest.rpartition("/")        # a local scope contains '/' itself: local:/path/to/project
            kind, _, where = scope.partition(":")
            if client not in mcp.CLIENTS or not name or not (
                    scope == "user" or (client == "claude" and kind in ("local", "project") and where.startswith("/")
                                        and where == os.path.normpath(where))):
                conflicts.append(f"mcp_map key {mkey!r}: expected <claude|codex>/<user|local:/abs/path|project:/abs/path>/<name>")
                continue
            if f"mcp:{client}:{scope}:{name}" in desired:
                continue
            # project:<dir> = the repository file <dir>/.mcp.json (retire only: the installer never adds entries there)
            file = (Path(where) / ".mcp.json" if kind == "project" else homes.claude_json) if client == "claude" \
                else homes.codex_toml
            d = {"format": "claude-json" if client == "claude" else "codex-toml", "file": str(file), "scope": scope,
                 "name": name}
            try:
                cur = current(d)
                if cur is None:
                    continue
                fingerprint = mcp.entry_fingerprint(d["format"], cur)
                if fingerprint != mapped.get("sha256"):
                    conflicts.append(f"{file}: legacy MCP entry '{name}' ({scope}) differs from its reviewed fingerprint "
                                     f"(now sha256:{fingerprint}); not retiring it")
                    continue
                simulate(d, None, {})
                steps.append(Step(str(file), state(cur), dict(ABSENT), f"retire legacy mcp {client}:{scope}:{name}",
                                  entry=dict(d, layout={})))
            except mcp.McpError as exc:
                conflicts.append(f"{file}: {exc}")

    spec_state = None
    if enabled:
        body = json.dumps({"schema_version": 1, "instances": spec_instances}, indent=2, sort_keys=True) + "\n"
        spec_state = {"type": "file", "sha256": _sha(body.encode()), "content": body, "mode": 0o600}
    return steps, tail, items, spec_state


def build_plan(repo: Path, homes: Homes, catalog: Catalog, add: Sequence[str], remove: Sequence[str],
               codex_legacy: Optional[bool], uninstall: bool, adopt_manual: Sequence[str],
               mcp_opts: Optional[McpOptions] = None) -> Plan:
    record = load_record(homes)
    legacy = Legacy() if uninstall else load_legacy(homes, catalog)  # uninstall never touches legacy items
    selected, select_all = ([], False) if uninstall else select_bundles(catalog, record, add, remove)
    if codex_legacy is None:
        codex_legacy = bool(record and record.get("options", {}).get("codex_legacy_skills_dir"))
    owned: Dict[str, Dict[str, Any]] = dict(record.get("items", {})) if record else {}
    steps: List[Step] = []
    conflicts: List[str] = []
    notices: List[str] = []
    projected: Dict[str, Dict[str, Any]] = {}

    def current(path: str) -> Dict[str, Any]:
        return projected[path] if path in projected else observe(Path(path))

    def ensure_parents(path: str) -> None:
        """Journal creation of missing ancestor directories (top-down) so rollback can remove them again."""
        missing = []
        parent = Path(path).parent
        while parent != homes.home and current(str(parent))["type"] == "absent":
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            key = str(directory)
            mode = 0o700 if (directory == homes.state or homes.state in directory.parents) else NEW_DIR_MODE
            empty = {"type": "dir", "sha256": EMPTY_DIR_SHA, "mode": mode}
            steps.append(Step(key, dict(ABSENT), empty, "create directory"))
            projected[key] = empty

    def add_step(path: str, after: Dict[str, Any], why: str, backup: Optional[str] = None) -> None:
        before = current(path)
        if same_state(before, after):
            return
        if after["type"] != "absent":
            ensure_parents(path)
        steps.append(Step(path, before, after, why, backup))
        projected[path] = after

    # manual copies (explicit opt-in only): move the hand-copied directory to a backup, then link normally
    manual = catalog.source_map["sources"]["manual-copies"]["skills"]
    for name in adopt_manual:
        if name not in manual:
            raise InstallError(f"--adopt-manual {name}: not a recorded manual copy ({', '.join(sorted(manual))})")
        spec = manual[name]
        for raw in spec.get("sources") or [spec["source"]]:
            path = homes.home / raw[2:] if raw.startswith("~/") else Path(raw)
            state = observe(path)
            if state["type"] == "dir":
                add_step(str(path), dict(ABSENT), f"back up hand-copied '{name}'", backup="pending")
            elif state["type"] != "absent":
                conflicts.append(f"{path}: expected a hand-copied directory for '{name}', found {describe(state)}")

    want = {} if uninstall else desired_links(catalog, homes, repo, selected, codex_legacy)

    # legacy links outside the selection would stay owned by a retired installer: refuse
    if legacy.records and not uninstall:
        for path, name in sorted(legacy.names.items()):
            wanted_paths = {p for p, (_, n) in want.items() if n == name}
            legacy_codex = Path(path).parent == homes.codex / "skills"
            if not wanted_paths and not (legacy_codex and any(n == name for _, n in want.values())):
                conflicts.append(f"{path}: owned by a legacy installer but '{name}' is not in the selected bundles; "
                                 "select its bundle (default: all) to migrate it")

    def is_owned(path: str) -> bool:
        state = current(path)
        if path in projected:
            return True
        if path in owned and same_state(state, owned[path]):
            return True
        if path in legacy.links and state["type"] == "link" and state["to"] == legacy.links[path]:
            return True
        return False

    # links we want
    for path, (target, name) in sorted(want.items()):
        state = current(path)
        desired = {"type": "link", "to": target}
        if same_state(state, desired):
            continue
        if state["type"] == "absent" or is_owned(path):
            add_step(path, desired, f"install {name}")
        else:
            conflicts.append(f"{path}: {describe(state)} is not owned by this installer (wanted {target})")

    # owned or legacy-owned links we no longer want
    for path in sorted(set(owned) | set(legacy.links)):
        if path in want or (path in owned and owned[path].get("type") == "block"):
            continue
        if path in owned and owned[path].get("type") in ("file", "entry"):
            continue
        state = current(path)
        if state["type"] == "absent":
            continue
        if is_owned(path):
            add_step(path, dict(ABSENT), "remove no longer selected/legacy link")
        elif path in owned:
            conflicts.append(f"{path}: changed since install ({describe(state)}); not removing")
        else:
            conflicts.append(f"{path}: recorded by a legacy installer as a link to {legacy.links[path]} but is now "
                             f"{describe(state)}; refusing to retire the legacy record")

    # managed instruction blocks
    block = None if uninstall else render_block(catalog, selected)
    separators: Dict[str, Tuple[str, str]] = {}
    for path in (homes.claude / "CLAUDE.md", homes.codex / "AGENTS.md"):
        key = str(path)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        try:
            ours = block_inner_sha(text)
            legacy_block = key in legacy.block_files and _find_block(text, LEGACY_BEGIN, LEGACY_END) is not None
            recorded = owned.get(key, {}).get("block_sha256")
            if ours is not None and ours != recorded:
                raise Conflict(f"{path}: managed block exists but differs from the recorded version (edited by hand?)")
            new_text, prefix, suffix = replace_block(text, block, legacy_block,
                                                     owned.get(key, {}).get("prefix", ""),
                                                     owned.get(key, {}).get("suffix", ""))
            separators[key] = (prefix, suffix)
        except Conflict as exc:
            conflicts.append(str(exc))
            continue
        if new_text == text:
            continue
        # delete the file only if it becomes empty AND this installer created it; otherwise keep it (even empty)
        if not new_text and owned.get(key, {}).get("created"):
            after = dict(ABSENT)
        else:
            mode = stat.S_IMODE(path.stat().st_mode) if path.is_file() else NEW_FILE_MODE
            after = {"type": "file", "sha256": _sha(new_text.encode("utf-8")), "content": new_text, "mode": mode}
        add_step(key, after, "update managed instruction block")

    for name, spec in sorted(manual.items()):
        for raw in spec.get("sources") or [spec["source"]]:
            candidate = homes.home / raw[2:] if raw.startswith("~/") else Path(raw)
            if candidate.is_dir() and not candidate.is_symlink() and str(candidate) not in projected:
                notices.append(f"hand-copied copy of '{name}' still present: {candidate} "
                               f"(review with scripts/migrate_manual_skills.py, then --adopt-manual {name})")

    # MCP client entries (per entry; plan phase 2F)
    mcp_opts = mcp_opts or McpOptions()
    mcp_enabled = False if uninstall else (mcp_opts.enabled if mcp_opts.enabled is not None
                                           else bool(record and record.get("options", {}).get("mcp")))
    spec_key = str(homes.mcp_spec)
    infos: List[str] = []
    entry_steps, _, mcp_items, spec_state = plan_mcp(repo, homes, owned, selected, mcp_enabled, mcp_opts, conflicts,
                                                     notices, infos, ensure_parents)
    if spec_state is not None:
        if observe(homes.mcp_spec)["type"] == "absent" or is_owned(spec_key):
            add_step(spec_key, spec_state, "MCP launch spec")    # written before the entries that point at it
        else:
            conflicts.append(f"{homes.mcp_spec}: exists but is not the version this installer wrote; not overwriting it")
    steps.extend(entry_steps)
    if spec_state is None and spec_key in owned and observe(homes.mcp_spec)["type"] != "absent":
        if is_owned(spec_key):
            add_step(spec_key, dict(ABSENT), "remove MCP launch spec")   # after the entries that pointed at it
        else:
            conflicts.append(f"{homes.mcp_spec}: changed since install; not removing it")

    # no path we might touch may sit behind a symlinked ancestor (would write outside the managed roots)
    touched = set(want) | {s.target for s in steps} | {str(homes.claude / "CLAUDE.md"), str(homes.codex / "AGENTS.md"),
                                                       str(homes.record)}
    for path in sorted(touched):
        reason = homes.redirected(Path(path))
        if reason:
            conflicts.append(reason)

    # new ownership record
    items: Dict[str, Dict[str, Any]] = {}
    for path, (target, _) in want.items():
        items[path] = {"type": "link", "to": target}
    for path in (homes.claude / "CLAUDE.md", homes.codex / "AGENTS.md"):
        key = str(path)
        final = projected.get(key)
        text = final.get("content", "") if final else (path.read_text(encoding="utf-8") if path.is_file() else "")
        sha = block_inner_sha(text) if text else None
        if sha:
            created = owned.get(key, {}).get("created", not path.exists())
            prefix, suffix = separators.get(key, (owned.get(key, {}).get("prefix", ""),
                                                  owned.get(key, {}).get("suffix", "")))
            items[key] = {"type": "block", "block_sha256": sha, "created": created,
                          "prefix": prefix, "suffix": suffix}
    items.update(mcp_items)
    if spec_state is not None:
        items[spec_key] = {k: v for k, v in spec_state.items() if k != "content"}
    new_record = {
        "schema_version": RECORD_VERSION,
        "repo_root": str(repo),
        "selected_bundles": selected,
        "select_all": select_all,
        "options": {"codex_legacy_skills_dir": bool(codex_legacy), "mcp": mcp_enabled},
        "items": items,
    }
    return Plan(steps, conflicts, notices, new_record, selected, infos)


def finalize_plan(plan: Plan, homes: Homes, catalog: Catalog, journal_id: str, uninstall: bool) -> List[Step]:
    """Append record steps (ownership record + legacy record retirement); resolve backup locations."""
    steps = list(plan.steps)
    for step in steps:
        if step.backup == "pending":
            step.backup = str(homes.backups / journal_id / hashlib.sha256(step.target.encode()).hexdigest()[:16])
    legacy = Legacy() if uninstall else load_legacy(homes, catalog)
    stamp = journal_id
    for record_path in legacy.records:
        data = record_path.read_bytes()
        moved = record_path.with_name(record_path.name + f".migrated-{stamp}")
        steps.append(Step(str(moved), observe(moved), {"type": "file", "sha256": _sha(data),
                                                        "mode": stat.S_IMODE(record_path.stat().st_mode),
                                                        "content": data.decode("utf-8")}, "keep legacy record"))
        steps.append(Step(str(record_path), observe(record_path), dict(ABSENT), "retire legacy record"))
    if uninstall:
        after = dict(ABSENT)
    else:
        body = json.dumps(plan.record, indent=2, sort_keys=True) + "\n"
        after = {"type": "file", "sha256": _sha(body.encode()), "content": body, "mode": 0o600}
    if not same_state(observe(homes.record), after):
        steps.append(Step(str(homes.record), observe(homes.record), after, "ownership record"))
    return steps  # may be only the ownership record (e.g. selection became symbolic 'all'): still journaled


# --------------------------------------------------------------------------------------------- journal engine


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _fault(point: str) -> None:
    if os.environ.get("SCAI_TEST_MODE") == "1" and os.environ.get("SCAI_FAULT") == point:
        os._exit(99)


class Journal:
    def __init__(self, homes: Homes, path: Path, data: Dict[str, Any]):
        self.homes, self.path, self.data = homes, path, data

    @classmethod
    def create(cls, homes: Homes, journal_id: str, steps: List[Step], kind: str) -> "Journal":
        _ensure_private_dir(homes.journals)
        _ensure_private_dir(homes.blobs)
        records = []
        for index, step in enumerate(steps):
            records.append({
                "id": index,
                "target": step.target,
                "why": step.why,
                "before": cls._store(homes, step.target, step.before),
                "after": cls._store(homes, step.target, step.after),
                "backup": step.backup,
                "entry": step.entry,
                "state": "planned",
                "rb": None,
            })
        data = {"id": journal_id, "kind": kind, "status": "open", "rollback_started": False,
                "repo_root": str(REPO), "steps": records}
        journal = cls(homes, homes.journals / f"journal-{journal_id}.json", data)
        journal.save()
        return journal

    @staticmethod
    def _store(homes: Homes, target: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Replace inline content by a private blob; capture current file content for 'before' states."""
        state = dict(state)
        if state["type"] in ("file", "entry"):
            content = state.pop("content", None)
            data = content.encode("utf-8") if content is not None else Path(target).read_bytes()
            blob = homes.blobs / state["sha256"]
            if not blob.exists():
                _atomic_write(blob, data)
        return state

    def save(self) -> None:
        _atomic_write(self.path, (json.dumps(self.data, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    @staticmethod
    def open_journals(homes: Homes) -> List[Path]:
        if not homes.journals.is_dir():
            return []
        found = []
        for path in sorted(homes.journals.glob("journal-*.json")):
            try:
                if json.loads(path.read_text(encoding="utf-8")).get("status") in ("open", "rolling_back"):
                    found.append(path)
            except (OSError, ValueError):
                found.append(path)
        return found

    @classmethod
    def load(cls, homes: Homes, path: Path) -> "Journal":
        return cls(homes, path, json.loads(path.read_text(encoding="utf-8")))

    # ---- applying a state to one target
    def _check_parents(self, target: Path) -> None:
        reason = self.homes.redirected(target)
        if reason:
            raise Conflict(reason)

    def _observe(self, step: Dict[str, Any]) -> Dict[str, Any]:
        return observe_entry(step["entry"]) if step.get("entry") else observe(Path(step["target"]))

    # ---- MCP client entries: one entry per step, the file written by atomic swap / link / rename (plan 2F §5a)
    def _swap_tmp(self, step: Dict[str, Any], key: str) -> Path:
        file = Path(step["entry"]["file"])
        suffix = "-rb" if key == "rb_swap" else ""
        return file.with_name(f".{file.name}.scai-swap-{self.data['id']}-{step['id']}{suffix}")

    def _set_entry(self, step: Dict[str, Any], state: Dict[str, Any], rollback: bool) -> None:
        spec = step["entry"]
        key, fault = ("rb_swap", f"rb:{step['id']}") if rollback else ("swap", f"{step['id']}")
        clients = mcp.running_clients()
        if clients:
            raise Blocked(f"Claude Code / Codex is running ({mcp.summarize_clients(clients)}); close every session and IDE extension, "
                          "then rerun from a plain terminal (client config files are only written while they are closed)")
        file = Path(spec["file"])
        self._test_edit(fault, spec)
        canonical = None if state["type"] == "absent" else (self.homes.blobs / state["sha256"]).read_bytes().decode("utf-8")
        layout = step.get("layout_applied", spec.get("layout", {})) if rollback else spec.get("layout", {})
        raw = file.read_bytes() if file.is_file() else None
        backups = self.data.setdefault("client_backups", {})
        if raw is not None and str(file) not in backups:  # manual safety net: whole file before our first write
            blob = self.homes.blobs / _sha(raw)
            if not blob.exists():
                _atomic_write(blob, raw)
            backups[str(file)] = _sha(raw)
            self.save()
        # the entry must still be exactly what the journal expects, judged from the SAME bytes the candidate is built
        # from (forward: 'before', rollback: 'after'); a change made after the step's first check is never overwritten
        source = step["after"] if rollback else step["before"]
        try:
            current = mcp.entry_get(spec["format"], raw, spec["scope"], spec["name"])
            cur_state = dict(ABSENT) if current is None else {"type": "entry", "sha256": _sha(current.encode("utf-8"))}
            if same_state(cur_state, state):
                return
            if not same_state(cur_state, source):
                raise Conflict(f"{file}: MCP entry '{spec['name']}' changed while the installer was working on it "
                               f"(is {describe(cur_state)}, expected {describe(source)}); nothing written, journal "
                               f"{self.path.name} left open")
            new, used = mcp.entry_set(spec["format"], raw, spec["scope"], spec["name"], canonical, dict(layout or {}))
        except mcp.McpError as exc:
            raise Conflict(f"{file}: {exc}") from exc
        if not rollback:
            step["layout_applied"] = used   # how the forward write placed/removed the entry: rollback undoes exactly that
        if new == raw:
            return
        self._write_client(step, key, fault, file, raw, new)

    def _write_client(self, step: Dict[str, Any], key: str, fault: str, file: Path, raw: Optional[bytes],
                      new: Optional[bytes]) -> None:
        tmp = self._swap_tmp(step, key)
        if tmp.exists() or tmp.is_symlink():
            raise Conflict(f"{tmp}: unexpected leftover file; resolve it by hand")
        if not mcp.swap_available() and raw is not None and new is not None:
            raise Conflict(f"{file}: atomic swap is not available on this system; refusing to write client config files")
        mode = "create" if raw is None else ("delete" if new is None else "swap")
        base = _sha(raw) if raw is not None else "absent"
        candidate = _sha(new) if new is not None else "absent"
        if new is not None:
            file_mode = stat.S_IMODE(file.stat().st_mode) if raw is not None else 0o600
            _atomic_write(tmp, new, file_mode)
            _atomic_write(self.homes.blobs / candidate, new)
        step[key] = {"mode": mode, "file": str(file), "tmp": str(tmp), "base": base, "candidate": candidate,
                     "state": "prepared"}
        self.save()
        _fault(f"{fault}:entry-after-prepare")
        self._test_touch(fault, file)
        if mode == "swap":
            mcp.atomic_swap(tmp, file)
        elif mode == "create":
            try:
                os.link(tmp, file)
            except FileExistsError:
                step[key]["state"] = "abandoning"   # intent before removing our candidate (crash-safe)
                self.save()
                tmp.unlink()
                _fsync_dir(file.parent)
                step[key]["state"] = "abandoned"
                self.save()
                raise Conflict(f"{file}: was created by another process meanwhile; left untouched")
        else:
            os.rename(file, tmp)
        _fsync_dir(file.parent)
        _fault(f"{fault}:entry-after-swap")
        expected_tmp = candidate if mode == "create" else base
        if _file_sha(tmp) != expected_tmp:
            _fault(f"{fault}:entry-after-detect")
            self._race(step, key)
        step[key]["state"] = "verified"
        self.save()
        _fault(f"{fault}:entry-after-verify-record")
        tmp.unlink()
        _fsync_dir(file.parent)
        _fault(f"{fault}:entry-after-tmp-unlink")
        step[key]["state"] = "done"
        self.save()

    def _race(self, step: Dict[str, Any], key: str) -> None:
        sw = step[key]
        tmp, file = Path(sw["tmp"]), Path(sw["file"])
        if sw["mode"] == "delete":
            # our rename moved a newer version away: put it back without overwriting anything, keep every copy
            try:
                os.link(tmp, file)
                tmp.unlink()
                sw["state"] = "abandoned"
                self.save()
                raise Conflict(f"{file}: changed while the installer was removing its entry; the new version was "
                               "restored untouched. Rerun once Claude Code / Codex are closed")
            except FileExistsError:
                pass
        sw["state"] = "concurrent"
        self.save()
        raise Conflict(f"{file}: another process wrote it while the installer was updating an MCP entry. Nothing was "
                       f"deleted: {file} now holds the installer's version, {tmp} holds the concurrent version. Merge "
                       f"them by hand, delete {tmp}, then run --resume or --rollback {self.path.name}")

    def _reconcile(self, step: Dict[str, Any], key: str) -> None:
        """Finish or refuse an interrupted client-file write (plan 2F §5a reconciliation table)."""
        sw = step.get(key)
        if not step.get("entry") or not sw or sw["state"] in ("done", "abandoned"):
            return
        tmp, file = Path(sw["tmp"]), Path(sw["file"])
        live, kept = _file_sha(file), _file_sha(tmp)
        base, cand, mode = sw["base"], sw["candidate"], sw["mode"]
        expected_tmp = cand if mode == "create" else base
        fault = f"{'rb:' if key == 'rb_swap' else ''}{step['id']}"

        def finish() -> None:              # 'verified' is already persisted: a crash here is resolved by rows 5/6
            if kept is not None:
                tmp.unlink()
                _fsync_dir(file.parent)
            _fault(f"{fault}:reconcile-after-finish-unlink")
            sw["state"] = "done"
            self.save()

        def abandon() -> None:             # intent first, then remove our own candidate, then record the result
            sw["state"] = "abandoning"
            self.save()
            if kept is not None:
                if kept != cand:
                    raise Conflict(f"{tmp}: unknown content; kept for review (journal {self.path.name})")
                tmp.unlink()
                _fsync_dir(file.parent)
            _fault(f"{fault}:reconcile-after-unlink")
            sw["state"] = "abandoned"
            self.save()

        if sw["state"] == "abandoning":                         # crash during a previous cleanup
            if kept is None or kept == cand:
                return abandon()
            raise Conflict(f"{tmp}: unknown content; kept for review (journal {self.path.name})")

        if sw["state"] == "verified":                           # rows 5, 6, 7, 12, 13
            if kept is None or kept == expected_tmp:
                return finish()
            raise Conflict(f"{tmp}: unknown content next to {file}; kept for review (journal {self.path.name})")
        if sw["state"] == "concurrent":                         # row 2 (already recorded)
            if kept is None:
                sw["state"] = "done"                             # the human merged and removed the copy
                self.save()
                return None
            raise Conflict(f"{tmp}: concurrent version of {file} still awaiting a manual merge "
                           f"(journal {self.path.name}); delete it once merged")
        if mode == "swap":
            if live == cand and kept == base:                   # row 1
                sw["state"] = "verified"
                self.save()
                return finish()
            if live == cand and kept is not None and kept not in (base, cand):   # row 2
                self._race(step, key)
            if kept == cand and live != cand:                    # rows 3, 4
                return abandon()
        elif mode == "create":
            if live is None and kept == cand:                   # row 8
                return abandon()
            if live == cand and kept == cand:                   # row 9
                sw["state"] = "verified"
                self.save()
                return finish()
            if live is not None and live != cand and kept == cand:   # row 10
                abandon()
                raise Conflict(f"{file}: was created by another process meanwhile; left untouched")
        else:  # delete: our rename moves the live file to tmp
            if live == base and kept is None:
                return abandon()
            if live is None and kept == base:
                sw["state"] = "verified"
                self.save()
                return finish()
            if live is None and kept is not None:
                self._race(step, key)
        raise Conflict(f"{file}: interrupted MCP entry write in an unexpected state (file sha256:{(live or 'absent')[:12]}, "
                       f"{tmp.name} sha256:{(kept or 'absent')[:12]}); nothing deleted (journal {self.path.name})")

    @staticmethod
    def _test_edit(fault: str, spec: Dict[str, Any]) -> None:
        """Test hook (SCAI_TEST_MODE only): a user edits the very entry between the step's check and the write."""
        if os.environ.get("SCAI_TEST_MODE") != "1" or os.environ.get("SCAI_TEST_EDIT_ENTRY") != fault:
            return
        file = Path(spec["file"])
        raw = file.read_bytes() if file.is_file() else None
        edit = '{"command":"USER-EDIT"}' if spec["format"] == "claude-json" else '[mcp_servers.x]\ncommand = "USER-EDIT"\n'
        if spec["format"] == "codex-toml":
            edit = edit.replace("mcp_servers.x", f"mcp_servers.{spec['name']}")
        new, _ = mcp.entry_set(spec["format"], raw, spec["scope"], spec["name"], edit, {})
        file.write_bytes(new)

    @staticmethod
    def _test_touch(fault: str, file: Path) -> None:
        """Test hook (SCAI_TEST_MODE only): simulate Claude/Codex writing the file right before the swap."""
        if os.environ.get("SCAI_TEST_MODE") != "1" or os.environ.get("SCAI_TEST_TOUCH") != fault:
            return
        if not file.exists():
            file.write_bytes(b"# created by someone else\n")
            return
        raw = file.read_bytes()
        if file.suffix == ".toml":
            data = raw + b"# written concurrently\n"
        else:
            doc = json.loads(raw)
            doc["concurrentWrite"] = True
            data = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
        other = file.with_name(file.name + ".concurrent-writer")
        other.write_bytes(data)
        os.chmod(other, stat.S_IMODE(file.stat().st_mode))
        os.replace(other, file)

    def _set(self, step: Dict[str, Any], state: Dict[str, Any], rollback: bool = False) -> None:
        if step.get("entry"):
            self._check_parents(Path(step["target"]))
            return self._set_entry(step, state, rollback)
        target = Path(step["target"])
        self._check_parents(target)
        if state["type"] == "absent":
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir() and not step.get("backup"):
                os.rmdir(target)  # a directory this installer created; empty again at this point
            elif target.is_dir():
                backup = Path(step["backup"])
                if "backup_modes" not in step:  # persist original modes before the move (crash-safe)
                    step["backup_modes"] = _mode_manifest(target)
                    self.save()
                _ensure_private_dir(backup.parent)
                os.rename(target, backup)
                _privatize(backup)
                step["backup_privatized"] = True
                self.save()
            _fsync_dir(target.parent)
        elif state["type"] == "link":
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.scai-tmp-{os.getpid()}")
            if tmp.is_symlink() or tmp.exists():
                tmp.unlink()
            os.symlink(state["to"], tmp)
            os.replace(tmp, target)
            _fsync_dir(target.parent)
        elif state["type"] == "file":
            data = (self.homes.blobs / state["sha256"]).read_bytes()
            _atomic_write(target, data, state["mode"])
        elif state["type"] == "dir" and not step.get("backup"):
            target.mkdir()
            os.chmod(target, state.get("mode", NEW_DIR_MODE))
            _fsync_dir(target.parent)
        elif state["type"] == "dir":
            _restore_modes(Path(step["backup"]), step.get("backup_modes", {}))
            os.rename(step["backup"], target)
            _fsync_dir(target.parent)
        else:
            raise InstallError(f"unknown state type {state['type']}")

    def forward(self) -> None:
        if self.data["rollback_started"]:
            raise Blocked(f"{self.path.name}: rollback already started; use --rollback to finish it")
        for step in self.data["steps"]:
            if step["state"] == "done":
                continue
            self._reconcile(step, "swap")
            cur = self._observe(step)
            if same_state(cur, step["after"]):
                if step.get("backup") and step["after"]["type"] == "absent" and Path(step["backup"]).is_dir():
                    if not _backup_intact(Path(step["backup"]), step["before"], step.get("backup_modes", {})):
                        raise Conflict(f"{step['backup']}: backup differs from the journaled original")
                    _privatize(Path(step["backup"]))
                    step["backup_privatized"] = True
                step["state"] = "done"
                self.save()
                continue
            if not same_state(cur, step["before"]):
                raise Conflict(f"{step['target']}: is {describe(cur)}, expected {describe(step['before'])} "
                               f"(changed outside the installer); journal {self.path.name} left open")
            step["state"] = "intent"
            self.save()
            _fault(f"{step['id']}:after-intent")
            self._set(step, step["after"])
            _fault(f"{step['id']}:after-apply")
            step["state"] = "done"
            self.save()
            _fault(f"{step['id']}:after-done")
        self.data["status"] = "complete"
        self.save()

    def rollback(self) -> None:
        if not self.data["rollback_started"]:
            for step in self.data["steps"]:
                if step["state"] == "intent":
                    self._reconcile(step, "swap")
                    cur = self._observe(step)
                    if same_state(cur, step["after"]):
                        step["state"] = "done"
                    elif same_state(cur, step["before"]):
                        step["state"] = "skipped"
                    else:
                        raise Conflict(f"{step['target']}: is {describe(cur)}, neither before nor after; "
                                       "rollback refused, nothing written")
                elif step["state"] == "planned":
                    step["state"] = "skipped"
            self.data["rollback_started"] = True
            self.data["status"] = "rolling_back"  # blocks new runs and --resume until finished
            self.save()
        for step in reversed(self.data["steps"]):
            if step["state"] != "done" or step["rb"] == "done":
                continue
            self._reconcile(step, "rb_swap")
            cur = self._observe(step)
            if same_state(cur, step["before"]):
                step["rb"] = "done"
                self.save()
                continue
            if not same_state(cur, step["after"]):
                raise Conflict(f"{step['target']}: is {describe(cur)}, expected {describe(step['after'])}; "
                               f"rollback stopped, journal {self.path.name} left open")
            step["rb"] = "intent"
            self.save()
            _fault(f"rb:{step['id']}:after-intent")
            self._set(step, step["before"], rollback=True)
            _fault(f"rb:{step['id']}:after-apply")
            step["rb"] = "done"
            self.save()
            _fault(f"rb:{step['id']}:after-done")
        self.data["status"] = "rolled_back"
        self.save()


def harden_legacy_backups(homes: Homes) -> List[str]:
    """Make backup storage private for every journal step whose privatization is not recorded as complete
    ('backup_privatized'). Crash-safe and idempotent:
      1. no manifest yet (journals from older versions): require tree hash == journaled 'before' hash, then persist
         the original mode manifest;
      2. manifest present: require _backup_intact() (original content; each mode original or already private);
      3. chmod to 0700/0600, then persist backup_privatized=True.
    Any content difference is a conflict and the backup is left untouched."""
    done: List[str] = []
    if not homes.journals.is_dir():
        return done
    for path in sorted(homes.journals.glob("journal-*.json")):
        journal = Journal.load(homes, path)
        for step in journal.data["steps"]:
            backup = Path(step["backup"]) if step.get("backup") else None
            if (not backup or step.get("backup_privatized") or not backup.is_dir()
                    or step["before"].get("type") != "dir"):
                continue
            if "backup_modes" not in step:
                if _tree_sha(backup) != step["before"]["sha256"]:
                    raise Conflict(f"{backup}: backup differs from the journaled original; not touching it")
                step["backup_modes"] = _mode_manifest(backup)
                journal.save()  # manifest is durable before any chmod
                _fault("harden:after-manifest")
            if not _backup_intact(backup, step["before"], step["backup_modes"]):
                raise Conflict(f"{backup}: backup differs from the journaled original; not touching it")
            _privatize(backup)
            step["backup_privatized"] = True
            journal.save()
            done.append(str(backup))
    return done


class Lock:
    def __init__(self, homes: Homes):
        self.homes = homes
        self.fd: Optional[int] = None

    def __enter__(self) -> "Lock":
        _ensure_private_dir(self.homes.state)
        self.fd = os.open(str(self.homes.state / "install.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self.fd)
            self.fd = None
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise Blocked("another installer run holds the lock") from exc
            raise
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


# --------------------------------------------------------------------------------------------- commands


def print_plan(plan: Plan, steps: Iterable[Step]) -> None:
    """Paths, names and short hashes only — never entry values (they are masked again defensively)."""
    for step in steps:
        print(mcp.mask(f"  {step.why}: {step.target}\n      {describe(step.before)}  ->  {describe(step.after)}"))
    for notice in plan.notices:
        print(mcp.mask(f"NOTICE: {notice}"))
    for info in plan.infos:
        print(mcp.mask(f"INFO: {info}"))


def mcp_options(args: argparse.Namespace) -> McpOptions:
    return McpOptions(enabled=args.mcp, overlay=args.overlay, remove=tuple(args.remove_mcp), python=args.python)


def cmd_status(homes: Homes, after: Optional[str]) -> int:
    """Journals with the command that fits their state. --after NAME: only journals written after NAME (e.g. the
    last journal before a cutover began); still-unfinished older journals are listed separately. Exit 4 if any journal
    is open or rolling back, else 0. Read-only."""
    paths = sorted(homes.journals.glob("journal-*.json")) if homes.journals.is_dir() else []
    unfinished = False
    shown = 0
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            status, kind = data.get("status"), data.get("kind", "install")
        except (OSError, ValueError):
            status, kind = "unreadable", "?"
        newer = after is None or path.name > after
        pending = status in ("open", "rolling_back", "unreadable")
        unfinished = unfinished or pending
        if not newer and not pending:
            continue
        tag = "" if newer else "  (existed before --after)"
        if status == "open":
            hint = f"finish: python3 scripts/install.py --resume   |   undo: python3 scripts/install.py --rollback {path.name}"
        elif status == "rolling_back":
            hint = f"rollback in progress — finish it: python3 scripts/install.py --rollback {path.name} — resuming is not possible for a rollback"
        elif status == "complete":
            hint = f"undo this {kind}: python3 scripts/install.py --rollback {path.name}"
        elif status == "rolled_back":
            hint = "already rolled back; nothing to do"
        else:
            hint = "unreadable journal; inspect it by hand"
        print(f"{path.name}  {status}{tag}\n    {hint}")
        shown += 1
    if not shown:
        print("no journals" + (f" after {after}" if after else ""))
    return EXIT_BLOCKED if unfinished else EXIT_OK


def cmd_list(catalog: Catalog, homes: Homes) -> int:
    record = load_record(homes)
    selected = set(record.get("selected_bundles", [])) if record else set()
    try:
        servers = mcp.load_registry(REPO)["servers"]
    except mcp.McpError:
        servers = {}
    for bundle in catalog.bundles:
        skills = [n for n, e in sorted(catalog.skills.items()) if bundle in e["bundles"]]
        roles = [n for n, e in sorted(catalog.roles.items()) if bundle in e["bundles"]]
        mcps = [n for n, e in sorted(servers.items()) if bundle in e.get("bundles", [])]
        mark = "*" if bundle in selected else " "
        print(f"{mark} {bundle}: skills={', '.join(skills) or '-'}; roles={', '.join(roles) or '-'}; "
              f"mcp={', '.join(mcps) or '-'} (with --mcp)")
    return EXIT_OK


def run(args: argparse.Namespace) -> int:
    homes = Homes.resolve(args.home)
    os.umask(0o077)
    if args.status:                                  # journals only: must work even if the checkout is broken
        return cmd_status(homes, args.after)
    catalog = load_catalog(REPO)
    if args.list:
        return cmd_list(catalog, homes)
    if args.check or args.dry_run:
        open_journals = Journal.open_journals(homes)
        if open_journals:
            print(f"BLOCKED: open journal {open_journals[0].name}; use --resume or --rollback")
            return EXIT_BLOCKED
        plan = build_plan(REPO, homes, catalog, args.bundle, args.remove_bundle, args.codex_legacy_skills_dir,
                          args.uninstall, args.adopt_manual, mcp_options(args))
        steps = finalize_plan(plan, homes, catalog, "dry-run", args.uninstall) if not plan.conflicts else plan.steps
        for conflict in plan.conflicts:
            print(mcp.mask(f"CONFLICT: {conflict}"))
        if plan.conflicts:
            return EXIT_CONFLICT
        if args.dry_run:
            print(f"Plan ({len(steps)} steps, bundles: {', '.join(plan.selected) or '-'}):")
            print_plan(plan, steps)
            return EXIT_OK
        if steps or plan.notices:
            print(f"DRIFT: {len(steps)} pending step(s)")
            print_plan(plan, steps)
            return EXIT_DRIFT
        print("OK: installation matches the repository")
        return EXIT_OK

    state_reason = homes.redirected(homes.state / "install.lock")
    if state_reason:
        raise Conflict(f"state directory: {state_reason}")
    if not homes.state.exists() and not (args.rollback or args.resume or args.prune_state):
        # nothing installed yet: plan read-only first so a conflict leaves HOME completely untouched
        preview = build_plan(REPO, homes, catalog, args.bundle, args.remove_bundle, args.codex_legacy_skills_dir,
                             args.uninstall, args.adopt_manual, mcp_options(args))
        if preview.conflicts:
            for conflict in preview.conflicts:
                print(mcp.mask(f"CONFLICT: {conflict}"))
            print("Nothing was written.")
            return EXIT_CONFLICT
    with Lock(homes):
        for hardened in harden_legacy_backups(homes):
            print(f"Secured backup storage (0700/0600, original modes kept in journal): {hardened}")
        if args.rollback:
            path = Path(args.rollback)
            if not path.is_absolute():
                path = homes.journals / path
            journal = Journal.load(homes, path)
            journal.rollback()
            print(f"Rolled back {path.name}")
            return EXIT_OK
        open_journals = Journal.open_journals(homes)
        if args.resume:
            if not open_journals:
                print("Nothing to resume")
                return EXIT_OK
            journal = Journal.load(homes, open_journals[0])
            journal.forward()
            print(f"Resumed and completed {journal.path.name}")
            return EXIT_OK
        if open_journals:
            raise Blocked(f"open journal {open_journals[0].name}: run --resume or --rollback {open_journals[0].name}")
        if args.prune_state:
            removed = 0
            for path in sorted(homes.journals.glob("journal-*.json")) if homes.journals.is_dir() else []:
                path.unlink()
                removed += 1
            for directory in (homes.blobs, homes.backups):
                if directory.is_dir():
                    shutil.rmtree(directory)
            print(f"Pruned {removed} journal(s), blobs and backups")
            return EXIT_OK
        plan = build_plan(REPO, homes, catalog, args.bundle, args.remove_bundle, args.codex_legacy_skills_dir,
                          args.uninstall, args.adopt_manual, mcp_options(args))
        if plan.conflicts:
            for conflict in plan.conflicts:
                print(mcp.mask(f"CONFLICT: {conflict}"))
            print("Nothing was written.")
            return EXIT_CONFLICT
        if any(step.entry for step in plan.steps):
            clients = mcp.running_clients()
            if clients:
                print(f"BLOCKED: Claude Code / Codex is running ({mcp.summarize_clients(clients)}). MCP client entries are only "
                      "written while every session and IDE extension is closed; run this from a plain terminal.")
                print("Nothing was written.")
                return EXIT_BLOCKED
        journal_id = _now()
        steps = finalize_plan(plan, homes, catalog, journal_id, args.uninstall)
        if not steps:
            print("OK: already up to date")
            for notice in plan.notices:
                print(mcp.mask(f"NOTICE: {notice}"))
            return EXIT_OK
        journal = Journal.create(homes, journal_id, steps, "uninstall" if args.uninstall else "install")
        journal.forward()
        print(f"Applied {len(steps)} step(s); journal {journal.path.name}")
        for notice in plan.notices:
            print(mcp.mask(f"NOTICE: {notice}"))
        print("Start a NEW Claude Code / Codex session to pick up the changes.")
        return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--home", help="install into this HOME instead of the real one (isolation/testing)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report drift/conflicts, write nothing")
    mode.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    mode.add_argument("--list", action="store_true", help="list bundles and their contents")
    mode.add_argument("--status", action="store_true",
                      help="list journals with the fitting --resume/--rollback command (exit 4 if one is unfinished)")
    mode.add_argument("--resume", action="store_true", help="finish an interrupted run")
    mode.add_argument("--rollback", metavar="JOURNAL", help="undo a run (journal file name or path)")
    mode.add_argument("--uninstall", action="store_true", help="remove everything this installer owns")
    mode.add_argument("--prune-state", action="store_true", help="delete finished journals, blobs and backups")
    parser.add_argument("--bundle", action="append", default=[], help="add a bundle to the selection (repeatable)")
    parser.add_argument("--remove-bundle", action="append", default=[], help="remove a bundle from the selection")
    parser.add_argument("--codex-legacy-skills-dir", dest="codex_legacy_skills_dir", action="store_true",
                        default=None, help="also link Codex skills into <codex>/skills (duplicate discovery risk)")
    parser.add_argument("--adopt-manual", action="append", default=[], metavar="SKILL",
                        help="back up a recorded hand-copied skill directory and replace it by the managed link")
    mcp_group = parser.add_mutually_exclusive_group()
    mcp_group.add_argument("--mcp", dest="mcp", action="store_true", default=None,
                           help="register MCP servers of the selected bundles in Claude Code and Codex (remembered; "
                                "Claude Code and Codex must be closed)")
    mcp_group.add_argument("--no-mcp", dest="mcp", action="store_false", help="remove every MCP entry this installer owns")
    parser.add_argument("--overlay", metavar="DIR",
                        help="private overlay directory (default: $SCAI_HOME/private or ~/.config/super-computer-ai/private)")
    parser.add_argument("--remove-mcp", action="append", default=[], metavar="INSTANCE",
                        help="explicitly remove an installed MCP instance (e.g. one whose overlay definition is gone)")
    parser.add_argument("--python", metavar="PATH", help="interpreter written into generated MCP entries")
    parser.add_argument("--after", metavar="JOURNAL", help="with --status: only journals written after this one")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except InstallError as exc:
        kind = 'CONFLICT' if isinstance(exc, Conflict) else 'BLOCKED' if isinstance(exc, Blocked) else 'ERROR'
        print(mcp.mask(f"{kind}: {exc}"))
        return exc.exit_code
    except mcp.McpError as exc:
        print(mcp.mask(f"CONFLICT: {exc}"))
        return EXIT_CONFLICT
    except OSError as exc:
        print(f"ERROR: filesystem failure: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
