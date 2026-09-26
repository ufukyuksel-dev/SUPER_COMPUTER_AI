"""Hermetic test environment: no test may read a real instance config or credentials.

Every test gets GOOGLE_ADS_CONFIG pointing at a temporary production-style config with fake identifiers; legacy
WORDFALL_* variables, the credential directory and the audit override are removed.
"""
import json

import pytest

import mutations

PROD = "1111111111"          # fake production customer
TEST_CLIENT = "2222222222"   # fake test-account customer
APPS = {"GOOGLE_APP_STORE": "com.example.game", "APPLE_APP_STORE": "1234567890"}
ENV_NAMES = ("GOOGLE_ADS_CONFIG", "WORDFALL_ADS_CONFIG", "GOOGLE_ADS_CREDENTIAL_DIR", "WORDFALL_ADS_CREDENTIAL_DIR",
             "GOOGLE_ADS_AUDIT_PATH")


def write_config(path, **overrides):
    data = {"customer_id": PROD, "production_customer_id": PROD, "apps": dict(APPS), **overrides}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


@pytest.fixture(autouse=True)
def instance_config(tmp_path, monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    mutations._warned.clear()
    path = write_config(tmp_path / "instance" / "config.json")
    monkeypatch.setenv("GOOGLE_ADS_CONFIG", str(path))
    return path
