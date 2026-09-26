"""mcp/registry.json: generic, consistent with the servers on disk and the skills manifest, no secret values."""
import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REGISTRY = json.loads((REPO / "mcp" / "registry.json").read_text(encoding="utf-8"))
SKILLS = json.loads((REPO / "skills" / "manifest.json").read_text(encoding="utf-8"))["skills"]
SKILL_BUNDLES = {b for entry in SKILLS.values() for b in entry.get("bundles", [])}
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PLACEHOLDER = re.compile(r"\{(path|client)\}")
MACHINE_PATH = re.compile(r"(/Users/|/home/|[A-Za-z]:\\)")
SERVERS = REGISTRY["servers"]

# `NAME=` or `# NAME=` at the start of a line documents a variable in .env.example
EXAMPLE_VAR = re.compile(r"^#?\s*([A-Z][A-Z0-9_]{2,})=", re.M)
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)")
# how each runtime reads the environment; `${NAME` only in Spring YAML/Kotlin (in TypeScript it is a template string)
CODE_READS = {
    ".py": re.compile(r"""(?:os\.environ\.get\(|os\.environ\[|getenv\(|env_value\()\s*['"]([A-Z][A-Z0-9_]{2,})"""),
    ".ts": re.compile(r"""(?:process\.env|\benv)(?:\.|\[\s*['"])([A-Z][A-Z0-9_]{2,})|envFlag\(\s*[\w.]+\s*,\s*['"]([A-Z][A-Z0-9_]{2,})"""),
    ".kt": re.compile(r"""\$\{([A-Z][A-Z0-9_]{2,})|getenv\(\s*"([A-Z][A-Z0-9_]{2,})"""),
    ".yml": re.compile(r"""\$\{([A-Z][A-Z0-9_]{2,})"""),
}
CODE_ROOTS = {"premiere-pro": "src", "google-ads": ".", "jev": "src", "adb": "src/main"}
# variables the code reads that are not server configuration
NOT_CONFIG = {
    "premiere-pro": {"APPDATA": "Windows system folder used to locate Premiere",
                     "JEST_WORKER_ID": "set by the test runner only"},
}
SKIP_PARTS = {"__tests__", "node_modules", ".venv", "build", "dist", "tests"}


def code_env_reads(name):
    root = REPO / "mcp" / "servers" / name / CODE_ROOTS[name]
    found = set()
    for path in root.rglob("*"):
        pattern = CODE_READS.get(path.suffix)
        if not pattern or SKIP_PARTS & set(path.relative_to(root).parts) or path.name.startswith(("test_", "conftest")):
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8", errors="ignore")):
            found.add(next(g for g in match.groups() if g))
    return found


def launch_entries(server):
    yield server["launch"]["args"]
    for variant in (server.get("variants") or {}).values():
        yield variant["args"]


class RegistryTest(unittest.TestCase):
    def test_top_level_shape(self):
        self.assertEqual(REGISTRY["schema_version"], 1)
        self.assertEqual(set(REGISTRY), {"_comment", "schema_version", "servers", "external"})
        self.assertEqual(set(SERVERS), {"premiere-pro", "google-ads", "jev", "adb", "meta-ads", "tiktok-ads"})
        for name in list(SERVERS) + REGISTRY["external"]:
            self.assertRegex(name, NAME)
        self.assertFalse(set(SERVERS) & set(REGISTRY["external"]))

    def test_local_servers_exist_and_document_their_env(self):
        for name, s in SERVERS.items():
            if s["kind"] != "local":
                continue
            with self.subTest(server=name):
                self.assertEqual(s["transport"], "stdio")
                self.assertEqual(s["path"], f"mcp/servers/{name}")
                root = REPO / s["path"]
                for required in ("README.md", ".env.example"):
                    self.assertTrue((root / required).is_file(), required)
                example = set(EXAMPLE_VAR.findall((root / ".env.example").read_text(encoding="utf-8")))
                declared = set(s.get("env", {}))
                self.assertEqual(sorted(declared - example), [], f"not documented in {s['path']}/.env.example")
                self.assertEqual(sorted(example - declared), [], f"documented in .env.example but missing in the registry")
                for var in (s.get("legacy_env") or {}):
                    self.assertIn(var, s["env"])
                self.assertTrue(s["launch"]["command"] and "/" not in s["launch"]["command"], "command must be on PATH")
                for args in launch_entries(s):
                    self.assertTrue(any("{path}" in a for a in args), f"{name}: launch must reference {{path}}")
                    for arg in args:
                        self.assertIsInstance(arg, str)
                        self.assertNotRegex(arg, MACHINE_PATH)
                        self.assertEqual(re.sub(PLACEHOLDER, "", arg).count("{"), 0, f"unknown placeholder in {arg}")

    def test_remote_servers(self):
        for name, s in SERVERS.items():
            if s["kind"] != "remote":
                continue
            with self.subTest(server=name):
                self.assertEqual(s["transport"], "http")
                self.assertTrue(s["url"].startswith("https://"))
                self.assertTrue((REPO / s["docs"]).is_file())
                self.assertEqual(Path(s["docs"]).parent, Path("mcp/remote") / name)
                self.assertIn(s["auth"]["method"], {"oauth", "headers_helper"})
                if s["auth"]["method"] == "headers_helper":
                    helper = REPO / s["auth"]["helper"]
                    self.assertTrue(helper.is_file() and helper.stat().st_mode & 0o111, "helper must be executable")
                    self.assertTrue(s["auth"]["argument"]["default"].startswith("~/.config/super-computer-ai/credentials/"))
        self.assertEqual(sorted(p.name for p in (REPO / "mcp" / "remote").iterdir() if p.is_dir()),
                         sorted(n for n, s in SERVERS.items() if s["kind"] == "remote"))
        self.assertEqual(sorted(p.name for p in (REPO / "mcp" / "servers").iterdir() if p.is_dir()),
                         sorted(n for n, s in SERVERS.items() if s["kind"] == "local"))

    def test_every_variable_the_code_reads_is_declared(self):
        for name, s in SERVERS.items():
            if s["kind"] != "local":
                continue
            with self.subTest(server=name):
                reads = code_env_reads(name)
                self.assertTrue(reads, "scanner found no environment reads at all")
                known = set(s.get("env", {})) | set((s.get("legacy_env") or {}).values()) | set(NOT_CONFIG.get(name, {}))
                self.assertEqual(sorted(reads - known), [], "read by the code but not in mcp/registry.json")

    def test_secret_looking_variables_are_marked_secret(self):
        for name, s in SERVERS.items():
            for var, spec in (s.get("env") or {}).items():
                is_location = spec.get("kind") == "path" or var.endswith(("_FILE", "_DIR", "_PATH"))
                if SECRET_NAME.search(var) and not is_location:
                    with self.subTest(server=name, var=var):
                        self.assertTrue(spec.get("secret"), f"{var} looks like a secret; mark it secret: true")

    def test_secret_variables_never_carry_a_value(self):
        for name, s in SERVERS.items():
            for var, spec in (s.get("env") or {}).items():
                if spec.get("secret"):
                    with self.subTest(server=name, var=var):
                        self.assertEqual(set(spec) - {"required", "secret", "kind"}, set(),
                                         "a secret variable may not have a default or value")
        text = (REPO / "mcp" / "registry.json").read_text(encoding="utf-8")
        self.assertNotRegex(text, MACHINE_PATH)
        self.assertNotRegex(text, r"\b\d{3}-?\d{3}-?\d{4}\b", "looks like a Google Ads customer ID")

    def test_skills_and_bundles_match_the_manifest(self):
        for name, s in SERVERS.items():
            with self.subTest(server=name):
                self.assertTrue(s["bundles"] and set(s["bundles"]) <= SKILL_BUNDLES, s["bundles"])
                for skill in s["skills"]:
                    self.assertIn(skill, SKILLS)
                    self.assertTrue(set(SKILLS[skill]["bundles"]) & set(s["bundles"]), f"{skill} shares no bundle")


if __name__ == "__main__":
    unittest.main()
