import os

import yaml

COLLECTOR_VERSION = "0.1.0"


class SourceConfig:
    def __init__(self, raw: dict):
        self.id = raw["id"]
        self.type = raw.get("type", "api")
        self.endpoint = raw.get("endpoint", "")
        self.rate_limit_per_min = int(raw.get("rate_limit_per_min", 60))
        self.license_note = raw.get("license_note", "")
        self.auth_env = raw.get("auth_env")

    def auth_token(self):
        """Resolved at runtime from the environment; never persisted."""
        if not self.auth_env:
            return None
        return os.environ.get(self.auth_env)


def load_sources(path: str) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    sources = {}
    for raw in data.get("sources", []):
        cfg = SourceConfig(raw)
        sources[cfg.id] = cfg
    return sources
