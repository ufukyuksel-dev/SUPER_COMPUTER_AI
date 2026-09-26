"""MCP client registration for scripts/install.py (plan phase 2F). Stdlib only, Python 3.9+.

Model: mcp/registry.json (generic servers) + the private overlay's mcp/instances.json (account-specific instances)
-> instances -> one entry per (client, scope, instance) in Claude's ~/.claude.json (user or local scope) and Codex's
config.toml. Entries are edited one at a time; every other byte of those files is preserved.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLIENTS = ("claude", "codex")
OVERLAY_KEYS = {"server", "env", "helper_args", "clients", "claude_scope", "codex"}
CODEX_KEYS = {"enabled_tools", "disabled_tools"}
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|AUTH)", re.I)
MASK_PATTERNS = [
    re.compile(r"EA[0-9A-Za-z]{40,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(Bearer\s+)[^\s\"']+", re.I),
    re.compile(r"(\b[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*[=:]\s*[\"']?)[^\s\"',}]+"),
]


class McpError(Exception):
    """A problem that must stop the run as a conflict (nothing written)."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mask(text: str) -> str:
    for pattern in MASK_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + "***", text)
    return text


# ------------------------------------------------------------------------------------------ registry and overlay


def load_registry(repo: Path) -> Dict[str, Any]:
    path = repo / "mcp" / "registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise McpError(f"cannot read {path}: {exc}") from exc
    if data.get("schema_version") != 1:
        raise McpError(f"{path}: unsupported schema_version")
    return data


@dataclass
class Instance:
    name: str
    server: str
    origin: str                      # "overlay" | "default"
    clients: Tuple[str, ...]
    claude_scope: str                # "user" | "local:<abs path>"
    env: Dict[str, str] = field(default_factory=dict)
    helper_args: List[str] = field(default_factory=list)
    codex: Dict[str, List[str]] = field(default_factory=dict)
    args: Optional[List[str]] = None  # variant args override the server's launch args


@dataclass
class OverlayResult:
    instances: Dict[str, Instance]
    invalid: Dict[str, str]          # instance name -> reason (defined but unusable)
    servers_defined: set             # servers with at least one overlay definition (valid or not)
    present: bool                    # overlay instances file exists
    error: Optional[str] = None      # overlay unreadable as a whole


def _expand(value: str, home: Path) -> str:
    if value == "~" or value.startswith("~/"):
        return str(home) + value[1:]
    return value


def _scope(raw: Any, home: Path) -> str:
    if raw in (None, "user"):
        return "user"
    if isinstance(raw, str) and raw.startswith("local:"):
        path = Path(_expand(raw[len("local:"):], home))
        if not path.is_absolute():
            raise ValueError(f"claude_scope {raw!r}: the local path must be absolute or start with ~/")
        return "local:" + os.path.normpath(str(path))
    raise ValueError(f"claude_scope {raw!r}: expected 'user' or 'local:<path>'")


def load_overlay(overlay_dir: Path, registry: Dict[str, Any], home: Path) -> OverlayResult:
    servers = registry["servers"]
    reserved = set(servers) | {v for s in servers.values() for v in (s.get("variants") or {})}
    path = overlay_dir / "mcp" / "instances.json"
    result = OverlayResult({}, {}, set(), path.is_file())
    if not path.exists():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["instances"]
        if data.get("schema_version") != 1 or not isinstance(items, dict):
            raise ValueError("expected {\"schema_version\": 1, \"instances\": {...}}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.error = f"{path}: {exc}"
        return result
    for name, spec in sorted(items.items()):
        server = spec.get("server") if isinstance(spec, dict) else None
        if isinstance(server, str):
            result.servers_defined.add(server)
        try:
            if not isinstance(spec, dict):
                raise ValueError("definition must be an object")
            if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
                raise ValueError("instance names are kebab-case")
            if name in reserved:
                raise ValueError(f"name clashes with registry server/variant '{name}'")
            unknown = set(spec) - OVERLAY_KEYS
            if unknown:
                raise ValueError(f"unknown keys {sorted(unknown)}")
            if server not in servers:
                raise ValueError(f"unknown server {server!r}")
            reg = servers[server]
            env = spec.get("env") or {}
            for var, value in env.items():
                if var not in (reg.get("env") or {}):
                    raise ValueError(f"env {var} is not declared for server {server}")
                if (reg["env"][var] or {}).get("secret"):
                    raise ValueError(f"env {var} is secret; it belongs in the credentials directory, not the overlay")
                if not isinstance(value, str):
                    raise ValueError(f"env {var} must be a string")
            for var, vspec in (reg.get("env") or {}).items():
                vspec = vspec or {}
                if vspec.get("secret"):
                    continue
                value = env.get(var)
                if vspec.get("required") and "default" not in vspec and not (isinstance(value, str) and value.strip()):
                    raise ValueError(f"env {var} is required for server {server} and must not be empty")
                if value is not None and vspec.get("kind") == "path" and not Path(_expand(value, home)).is_absolute():
                    raise ValueError(f"env {var} must be an absolute path (or start with ~/), got {value!r}")
            helper_args = spec.get("helper_args") or []
            if helper_args and (reg.get("auth") or {}).get("method") != "headers_helper":
                raise ValueError("helper_args only apply to headers_helper servers")
            clients = tuple(spec.get("clients") or CLIENTS)
            if not set(clients) <= set(CLIENTS) or not clients:
                raise ValueError(f"clients must be a subset of {list(CLIENTS)}")
            codex = spec.get("codex") or {}
            if set(codex) - CODEX_KEYS:
                raise ValueError(f"codex keys must be among {sorted(CODEX_KEYS)}")
            for key, value in codex.items():
                if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                    raise ValueError(f"codex.{key} must be a list of strings")
            inst = Instance(name, server, "overlay", clients, _scope(spec.get("claude_scope"), home),
                            {k: _expand(v, home) for k, v in env.items()},
                            [_expand(a, home) for a in helper_args], dict(codex))
            missing = missing_references(inst, reg)
            if missing:
                raise ValueError(f"referenced path does not exist: {missing}")
            result.instances[name] = inst
        except ValueError as exc:
            result.invalid[name] = str(exc)
    return result


def missing_references(inst: Instance, reg: Dict[str, Any]) -> Optional[str]:
    """First required path the instance points at that does not exist (None if all exist)."""
    for var, spec in (reg.get("env") or {}).items():
        if (spec or {}).get("kind") == "path" and spec.get("required") and var in inst.env:
            if not Path(inst.env[var]).exists():
                return inst.env[var]
    auth = reg.get("auth") or {}
    if auth.get("method") == "headers_helper":
        token = inst.helper_args[0] if inst.helper_args else None
        if token and not Path(token).is_file():
            return token
    return None


def default_instances(registry: Dict[str, Any], server: str, home: Path, credentials: Path) -> Tuple[List[Instance], Optional[str]]:
    """Default instance(s) of a server, or ([], reason) if it cannot run without account-specific configuration."""
    reg = registry["servers"][server]
    for var, spec in (reg.get("env") or {}).items():
        spec = spec or {}
        if spec.get("required") and not spec.get("secret") and "default" not in spec:
            return [], f"{server}: needs account-specific {var}; define an instance in the private overlay"
    helper_args: List[str] = []
    auth = reg.get("auth") or {}
    if auth.get("method") == "headers_helper":
        default = (auth.get("argument") or {}).get("default")
        if default:
            default = _expand(default, home)
            if default.startswith(str(home / ".config" / "super-computer-ai")) and credentials != home / ".config" / "super-computer-ai":
                default = str(credentials) + default[len(str(home / ".config" / "super-computer-ai")):]
            helper_args = [default]
    out = [Instance(server, server, "default", CLIENTS, "user", {}, helper_args)]
    for variant, spec in sorted((reg.get("variants") or {}).items()):
        out.append(Instance(variant, server, "default", CLIENTS, "user", {}, [], {}, list(spec["args"])))
    for inst in out:
        missing = missing_references(inst, reg)
        if missing:
            return [], f"{server}: default credential file {missing} does not exist"
    return out, None


def load_mcp_map(overlay_dir: Path) -> Dict[str, Dict[str, Any]]:
    """'<client>/<scope>/<name>' -> {"sha256": ..., "retire": bool}."""
    path = overlay_dir / "migration" / "mcp_map.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["entries"]
        if data.get("schema_version") != 1 or not isinstance(entries, dict):
            raise ValueError("expected {\"schema_version\": 1, \"entries\": {...}}")
    except (OSError, ValueError, KeyError) as exc:
        raise McpError(f"{path}: {exc}") from exc
    return entries


# ------------------------------------------------------------------------------------------ entry rendering


def resolve_python(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        if Path("/usr/bin/python3").is_file():
            return "/usr/bin/python3"
        raise McpError("the installer runs inside a virtualenv; pass --python <interpreter> for the MCP entries")
    return sys.executable


def claude_entry(inst: Instance, reg: Dict[str, Any], repo: Path, python: str, spec_path: Path) -> Dict[str, Any]:
    if reg["kind"] == "local":
        return {"type": "stdio", "command": python,
                "args": [str(repo / "scripts" / "run_mcp.py"), "--spec", str(spec_path), inst.name, "--client", "claude"],
                "env": {}}
    entry: Dict[str, Any] = {"type": "http", "url": reg["url"]}
    if (reg.get("auth") or {}).get("method") == "headers_helper":
        entry["headersHelper"] = " ".join(_shell_quote(a) for a in
                                          [python, str(repo / reg["auth"]["helper"])] + inst.helper_args)
    return entry


def codex_entry(inst: Instance, reg: Dict[str, Any], repo: Path, python: str, spec_path: Path) -> Dict[str, Any]:
    if reg["kind"] == "local":
        return {"command": python,
                "args": [str(repo / "scripts" / "run_mcp.py"), "--spec", str(spec_path), inst.name, "--client", "codex"]}
    entry: Dict[str, Any] = {"url": reg["url"]}
    if (reg.get("auth") or {}).get("method") == "headers_helper":
        entry["http_headers_helper"] = " ".join(_shell_quote(a) for a in
                                                [python, str(repo / reg["auth"]["helper"])] + inst.helper_args)
    for key in ("enabled_tools", "disabled_tools"):
        if key in inst.codex:
            entry[key] = list(inst.codex[key])
    return entry


def _shell_quote(value: str) -> str:
    return value if re.match(r"^[A-Za-z0-9_@%+=:,./-]+$", value) else "'" + value.replace("'", "'\"'\"'") + "'"


def spec_record(inst: Instance, reg: Dict[str, Any], repo: Path, credentials: Path) -> Dict[str, Any]:
    """Launch spec of a local instance: absolute, install-time-resolved values only (the wrapper reads nothing else)."""
    launch = reg["launch"]
    command = shutil.which(launch["command"])
    if not command:
        raise ValueError(f"command {launch['command']!r} not found on PATH")
    server_path = str(repo / reg["path"])
    args = [a.replace("{path}", server_path) for a in (inst.args if inst.args is not None else launch["args"])]
    return {"server": inst.server, "command": os.path.realpath(command), "args": args, "env": dict(sorted(inst.env.items())),
            "unset": inherited_to_clear(inst, reg),
            "secret_keys": sorted(var for var, v in (reg.get("env") or {}).items() if (v or {}).get("secret")),
            "credentials_env_file": str(credentials / "credentials" / inst.server / ".env")}


def inherited_to_clear(inst: Instance, reg: Dict[str, Any]) -> List[str]:
    """Variables the wrapper removes from the inherited environment so an instance never runs with another account's
    exported configuration: every legacy alias, and — for account-specific servers (a required non-secret variable) —
    each optional non-secret variable the instance does not set itself."""
    declared = reg.get("env") or {}
    clear = set((reg.get("legacy_env") or {}).values())
    account_specific = any((v or {}).get("required") and not (v or {}).get("secret") and "default" not in (v or {})
                           for v in declared.values())
    if account_specific:
        clear |= {var for var, v in declared.items() if not (v or {}).get("secret") and var not in inst.env}
    return sorted(clear - set(inst.env))


def missing_build_output(spec: Dict[str, Any], reg: Dict[str, Any], repo: Path) -> Optional[str]:
    server_path = str(repo / reg["path"])
    for arg in spec["args"]:
        if arg.startswith(server_path + "/") and not Path(arg).exists():
            return arg
    return None


# ------------------------------------------------------------------------------------------ Claude JSON editing


def claude_canonical(entry: Dict[str, Any]) -> str:
    """Exact, order-preserving form: what is stored and restored (rollback must be byte-identical)."""
    return json.dumps(entry, separators=(",", ":"), ensure_ascii=False)


def entry_fingerprint(fmt: str, canonical: str) -> str:
    """Order-independent fingerprint used by the private mcp_map (Claude: sorted keys; Codex: the exact text)."""
    if fmt == "claude-json":
        canonical = json.dumps(json.loads(canonical), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha(canonical.encode("utf-8"))


def claude_load(raw: bytes) -> Tuple[Dict[str, Any], str]:
    """Parse ~/.claude.json and prove it can be written back byte for byte; returns (document, trailing text)."""
    text = raw.decode("utf-8")
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise McpError(f"Claude config is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise McpError("Claude config is not a JSON object")
    dumped = json.dumps(doc, indent=2, ensure_ascii=False)
    for tail in ("", "\n"):
        if dumped + tail == text:
            return doc, tail
    raise McpError("Claude config would not round-trip byte for byte (unexpected formatting); refusing to edit it")


def claude_dump(doc: Dict[str, Any], tail: str) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + tail).encode("utf-8")


def claude_container(doc: Dict[str, Any], scope: str, create: bool) -> Optional[Dict[str, Any]]:
    """user: ~/.claude.json top level; local:<dir>: ~/.claude.json projects[dir]; project:<dir>: <dir>/.mcp.json top
    level (a repository file — the installer only ever removes reviewed legacy entries from it, never adds)."""
    if scope == "user" or scope.startswith("project:"):
        holder = doc
    else:
        project = scope[len("local:"):]
        holder = (doc.get("projects") or {}).get(project)
        if not isinstance(holder, dict):
            if create:
                raise McpError(f"Claude has no local-scope entry for {project}; open Claude Code there once, then rerun")
            return None
    servers = holder.get("mcpServers")
    if servers is None:
        if not create:
            return None
        servers = holder["mcpServers"] = {}
    if not isinstance(servers, dict):
        raise McpError("Claude mcpServers is not an object")
    return servers


def claude_get(raw: Optional[bytes], scope: str, name: str) -> Optional[str]:
    if raw is None:
        return None
    doc, _ = claude_load(raw)
    servers = claude_container(doc, scope, create=False)
    if servers is None or name not in servers:
        return None
    return claude_canonical(servers[name])


def claude_set(raw: Optional[bytes], scope: str, name: str, canonical: Optional[str],
               layout: Dict[str, Any]) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """Return (new file bytes or None = delete the file, layout used). layout: created_container, created_file."""
    if raw is None:
        if canonical is None:
            return None, layout
        doc, tail, layout = {}, "", dict(layout, created_file=True)
    else:
        doc, tail = claude_load(raw)
    if canonical is not None:
        holder_had = claude_container(doc, scope, create=False) is not None
        servers = claude_container(doc, scope, create=True)
        if not holder_had:
            layout = dict(layout, created_container=True)
        index = layout.get("index")
        if name not in servers and isinstance(index, int) and index < len(servers):
            items = list(servers.items())       # restore a removed entry at its original position (rollback)
            items.insert(index, (name, json.loads(canonical)))
            servers.clear()
            servers.update(items)
        else:
            servers[name] = json.loads(canonical)
    else:
        servers = claude_container(doc, scope, create=False)
        if servers is not None and name in servers:
            layout = dict(layout, index=list(servers).index(name))
            del servers[name]
            if not servers and layout.get("created_container"):
                holder = doc if scope == "user" else doc["projects"][scope[len("local:"):]]
                del holder["mcpServers"]
        if layout.get("created_file") and doc == {}:
            return None, layout
    return claude_dump(doc, tail), layout


# ------------------------------------------------------------------------------------------ Codex TOML editing


HEADER = re.compile(r"^[ \t]*(\[\[?)(.*?)(\]\]?)[ \t]*(#.*)?$")


def _parse_key(text: str) -> List[str]:
    parts, i, n = [], 0, len(text)
    while i < n:
        while i < n and text[i] in " \t":
            i += 1
        if i >= n:
            break
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            parts.append(json.loads(text[i:j + 1]))
            i = j + 1
        elif text[i] == "'":
            j = text.index("'", i + 1)
            parts.append(text[i + 1:j])
            i = j + 1
        else:
            m = re.match(r"[A-Za-z0-9_-]+", text[i:])
            if not m:
                raise McpError(f"unsupported TOML table header key: [{text}]")
            parts.append(m.group(0))
            i += len(m.group(0))
        while i < n and text[i] in " \t":
            i += 1
        if i < n:
            if text[i] != ".":
                raise McpError(f"unsupported TOML table header key: [{text}]")
            i += 1
    return parts


def codex_check_shape(text: str) -> None:
    if '"""' in text or "'''" in text:
        raise McpError("Codex config contains multi-line strings; refusing to edit it (unsupported shape)")
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^mcp_servers\s*[.=]", stripped):
            raise McpError("Codex config defines mcp_servers with dotted/inline keys; refusing to edit it")
        m = HEADER.match(line)
        if m and not stripped.startswith("#"):
            path = _parse_key(m.group(2))
            if path == ["mcp_servers"]:
                raise McpError("Codex config has a bare [mcp_servers] table; refusing to edit it")
            if m.group(1) == "[[" and path[:1] == ["mcp_servers"]:
                raise McpError("Codex config has an array of tables under mcp_servers; refusing to edit it")


def _chunks(text: str) -> List[Tuple[int, int, Optional[List[str]]]]:
    """(start, end, header path or None) for the preamble and each table."""
    offsets, pos = [], 0
    for line in text.splitlines(keepends=True):
        offsets.append((pos, line))
        pos += len(line)
    starts: List[Tuple[int, Optional[List[str]]]] = [(0, None)]
    for start, line in offsets:
        m = HEADER.match(line.rstrip("\r\n"))
        if m and not line.lstrip().startswith("#"):
            starts.append((start, _parse_key(m.group(2))))
    out = []
    for index, (start, path) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        if index == 0 and end == 0:
            continue
        out.append((start, end, path))
    return out


def _trim_trailing(text: str, start: int, end: int) -> int:
    """End offset of a group without its trailing blank and comment-only lines (they stay where they are)."""
    body = text[start:end]
    lines = body.splitlines(keepends=True)
    while len(lines) > 1 and (not lines[-1].strip() or lines[-1].lstrip().startswith("#")):
        lines.pop()
    return start + sum(len(line) for line in lines)


def codex_group(text: str, name: str) -> Optional[Tuple[int, int]]:
    codex_check_shape(text)
    spans = [(s, e) for s, e, p in _chunks(text) if p and p[:2] == ["mcp_servers", name]]
    if not spans:
        return None
    for (s1, e1), (s2, _) in zip(spans, spans[1:]):
        if e1 != s2:
            raise McpError(f"Codex config: tables of mcp_servers.{name} are not contiguous; refusing to edit them")
    return spans[0][0], _trim_trailing(text, spans[0][0], spans[-1][1])


def _insertable(text: str, offset: int) -> bool:
    """A table group can be put back at offset without capturing foreign keys: offset is at a line start and only
    blank/comment lines follow until the next table header (or the end of the file)."""
    if not (0 <= offset <= len(text)) or (offset and text[offset - 1] != "\n"):
        return False
    for line in text[offset:].splitlines():
        stripped = line.strip()
        if HEADER.match(line) and not stripped.startswith("#"):
            return True
        if stripped and not stripped.startswith("#"):
            return False
    return True


def _toml_str(value: str) -> str:
    if "\x7f" in value:
        raise McpError("value contains DEL")
    return json.dumps(value, ensure_ascii=False)


def codex_render(name: str, entry: Dict[str, Any]) -> str:
    key = name if BARE_KEY.match(name) else _toml_str(name)
    lines = [f"[mcp_servers.{key}]"]
    for k, v in entry.items():
        if isinstance(v, list):
            lines.append(f"{k} = [" + ", ".join(_toml_str(x) for x in v) + "]")
        else:
            lines.append(f"{k} = {_toml_str(v)}")
    return "\n".join(lines) + "\n"


def codex_get(raw: Optional[bytes], name: str) -> Optional[str]:
    if raw is None:
        return None
    text = raw.decode("utf-8")
    span = codex_group(text, name)
    return None if span is None else text[span[0]:span[1]]


def codex_set(raw: Optional[bytes], name: str, group: Optional[str],
              layout: Dict[str, Any]) -> Tuple[Optional[bytes], Dict[str, Any]]:
    text = raw.decode("utf-8") if raw is not None else None
    if text is None:
        if group is None:
            return None, layout
        return group.encode("utf-8"), dict(layout, created_file=True, sep="")
    span = codex_group(text, name)
    if group is not None:
        offset, sep_removed = layout.get("offset"), layout.get("sep_removed")
        if span:
            new = text[:span[0]] + group + text[span[1]:]
        elif isinstance(offset, int) and sep_removed is not None and _insertable(text, offset):
            new = text[:offset] + sep_removed + group + text[offset:]   # undo of a removal: back to its exact place
        else:
            sep = ""
            if text and not text.endswith("\n"):
                sep += "\n"
            if (text + sep).strip() and not (text + sep).endswith("\n\n"):
                sep += "\n"
            new, layout = text + sep + group, dict(layout, sep=sep)
    else:
        if span is None:
            return raw, layout
        start, sep = span[0], layout.get("sep", "")
        removed = sep if sep and text[:start].endswith(sep) else ""   # the separator we added when appending it
        start -= len(removed)
        new = text[:start] + text[span[1]:]
        layout = dict(layout, offset=start, sep_removed=removed)
        if layout.get("created_file") and new == "":
            return None, layout
    _verify_toml(text, new, name, group)
    return new.encode("utf-8"), layout


def _verify_toml(before: str, after: str, name: str, group: Optional[str]) -> None:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        return
    try:
        old, new = tomllib.loads(before), tomllib.loads(after)
    except tomllib.TOMLDecodeError as exc:
        raise McpError(f"Codex config edit would not parse: {exc}") from exc
    expected = json.loads(json.dumps(old))
    servers = expected.setdefault("mcp_servers", {})
    if group is None:
        servers.pop(name, None)
        if not servers:
            expected.pop("mcp_servers")
    else:
        servers[name] = tomllib.loads(group)["mcp_servers"][name]
    if json.loads(json.dumps(new)) != expected:
        raise McpError(f"Codex config edit changed more than mcp_servers.{name}; refusing to write it")


# ------------------------------------------------------------------------------------------ entry access by format


def entry_get(fmt: str, raw: Optional[bytes], scope: str, name: str) -> Optional[str]:
    return claude_get(raw, scope, name) if fmt == "claude-json" else codex_get(raw, name)


def entry_set(fmt: str, raw: Optional[bytes], scope: str, name: str, canonical: Optional[str],
              layout: Dict[str, Any]) -> Tuple[Optional[bytes], Dict[str, Any]]:
    if fmt == "claude-json":
        return claude_set(raw, scope, name, canonical, layout)
    return codex_set(raw, name, canonical, layout)


# ------------------------------------------------------------------------------------------ writers and swaps


def client_processes(ps_output: str) -> List[str]:
    """Claude Code / Codex processes in `ps -axww -o pid=,args=` output (full command lines; `comm` is truncated by ps
    and must not be used). Covers the CLIs (native, npm and SDK-embedded `claude`, `codex`) and the desktop apps that
    run sessions (Claude.app, the ChatGPT/Codex app)."""
    found = []
    for line in ps_output.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        pid, args = parts
        low = args.lower()
        exe = args.split(" --", 1)[0]                 # an app path may contain spaces; options start with --
        base = os.path.basename(args.split()[0]).lower()
        if (base in ("claude", "codex") or "@anthropic-ai/claude-code" in low or "@openai/codex" in low
                or "/claude.app/contents/" in low or "/chatgpt.app/contents/frameworks/codex" in low
                or "/codex.app/contents/" in low):
            found.append(f"{os.path.basename(exe.rstrip('/')) or base} (pid {pid})")
    return found


def summarize_clients(found: List[str]) -> str:
    """'Claude, Codex (14 processes)' — distinct program names instead of every helper process."""
    names = sorted({item.split(" (pid")[0] for item in found})
    return f"{', '.join(names[:6])}{', …' if len(names) > 6 else ''} ({len(found)} processes)"


UNVERIFIABLE = "<process list could not be verified>"


def running_clients(run: Any = None) -> List[str]:
    """Claude Code / Codex processes that may write their config files concurrently. Fails CLOSED: if the process
    list cannot be obtained or does not look complete (non-zero exit, empty or malformed output, or our own process
    missing from it), a non-empty result is returned so the caller refuses to write. ps's own messages are never
    echoed (they could contain command lines)."""
    if run is None and os.environ.get("SCAI_TEST_MODE") == "1":
        value = os.environ.get("SCAI_TEST_CLIENT_PROCS", "")
        return [p for p in value.split(",") if p]
    run = run or subprocess.run
    try:
        result = run(["ps", "-axww", "-o", "pid=,args="], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError, ValueError):
        return [UNVERIFIABLE]
    out = result.stdout if isinstance(result.stdout, str) else ""
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    pids = set()
    for line in lines:
        head = line.split(None, 1)[0]
        if not head.isdigit():
            return [UNVERIFIABLE]
        pids.add(int(head))
    if result.returncode != 0 or not lines or os.getpid() not in pids:
        return [UNVERIFIABLE]
    return client_processes(out)


_LIBC = None


def _libc():
    global _LIBC
    if _LIBC is None:
        _LIBC = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
    return _LIBC


def swap_available() -> bool:
    if os.environ.get("SCAI_TEST_MODE") == "1" and os.environ.get("SCAI_TEST_NO_SWAP") == "1":
        return False
    libc = _libc()
    return hasattr(libc, "renamex_np") if sys.platform == "darwin" else hasattr(libc, "renameat2")


def atomic_swap(a: Path, b: Path) -> None:
    """Exchange two existing paths atomically (neither ever disappears)."""
    if not swap_available():
        raise McpError("atomic file swap is not available on this system; refusing to write client config files")
    libc = _libc()
    if sys.platform == "darwin":
        result = libc.renamex_np(os.fsencode(str(a)), os.fsencode(str(b)), ctypes.c_uint(0x2))  # RENAME_SWAP
    else:
        result = libc.renameat2(ctypes.c_int(-100), os.fsencode(str(a)), ctypes.c_int(-100), os.fsencode(str(b)),
                                ctypes.c_uint(2))  # AT_FDCWD, RENAME_EXCHANGE
    if result != 0:
        err = ctypes.get_errno()
        raise OSError(err, f"atomic swap failed: {os.strerror(err)}", str(b))
