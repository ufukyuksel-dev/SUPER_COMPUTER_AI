import hashlib
import json
import os
from datetime import datetime, timezone

PROVENANCE_FIELDS = (
    "url",
    "accessed_at",
    "license",
    "content_sha256",
    "collector_version",
    "source_id",
)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_raw(data_dir: str, content: bytes) -> str:
    """Store raw payload under a content-hash filename; returns the hash.

    Re-saving identical content is a no-op, which makes collection idempotent.
    """
    digest = sha256_hex(content)
    raw_dir = os.path.join(data_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, digest)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(content)
    return digest


def append_provenance(data_dir: str, record: dict) -> None:
    missing = [k for k in PROVENANCE_FIELDS if not record.get(k)]
    if missing:
        raise ValueError(f"provenance record missing fields: {missing}")
    path = os.path.join(data_dir, "provenance.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_error(data_dir: str, error: dict) -> None:
    error = dict(error)
    error.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    path = os.path.join(data_dir, "errors.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(error, ensure_ascii=False) + "\n")


def load_state(data_dir: str, source_id: str) -> dict:
    path = os.path.join(data_dir, "state", f"{source_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_state(data_dir: str, source_id: str, state: dict) -> None:
    state_dir = os.path.join(data_dir, "state")
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"{source_id}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def seen_hashes(data_dir: str) -> set:
    path = os.path.join(data_dir, "provenance.jsonl")
    seen = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    seen.add(json.loads(line)["content_sha256"])
    return seen
