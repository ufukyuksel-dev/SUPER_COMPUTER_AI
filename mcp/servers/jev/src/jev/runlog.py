"""Per-run record: Jev's `done` opinion and the observed outcome are kept separately."""

from __future__ import annotations

import json
import time

from jev import paths

def runs_file():
    """Resolved at call time so JEV_STATE_DIR from the .env loaded at startup applies."""
    return paths.state_dir() / "runs.jsonl"


def record(goal: str, result: dict, expected: str | None = None) -> dict:
    """`expected` is a substring of the destination URL or title; `reached` is checked by code, not Jev."""
    reached = None
    if expected:
        e = expected.lower()
        reached = e in result["url"].lower() or e in result["title"].lower()
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "goal": goal,
        "expected_destination": expected,
        "final_url": result["url"],
        "status": result["status"],
        "jev_done": result["status"] == "done",
        "reached": reached,
        "step_count": len(result["steps"]),
    }
    path = runs_file()
    paths.ensure_dir(path.parent)
    with path.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
