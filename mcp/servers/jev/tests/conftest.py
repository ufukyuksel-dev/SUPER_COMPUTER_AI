import os
import tempfile
from pathlib import Path

import pytest

# Hermetic by default: runtime state goes to a throwaway directory and no secrets are loaded unless the caller
# opts in explicitly with JEV_ENV_FILE (or an exported TYPESAFE_API_KEY) for the live, paid Jev tests.
os.environ.setdefault("JEV_STATE_DIR", tempfile.mkdtemp(prefix="jev-test-state-"))
os.environ.setdefault("JEV_ENV_FILE", os.devnull + ".jev-tests-no-secrets")

from jev import env  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fixture_url(name: str) -> str:
    return (FIXTURES / name).as_uri()


env.load()
needs_jev = pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="TYPESAFE_API_KEY not set")
