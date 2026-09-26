import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.adapters import Adapter
from collector.dedup import cross_split_check
from collector.ratelimit import retry_backoff
from collector.run import collect
from collector.storage import PROVENANCE_FIELDS


class MockAdapter(Adapter):
    """Serves fixed pages; can be told to fail the first N fetch calls."""

    def __init__(self, pages, fail_first=0):
        self.pages = pages  # {cursor_or_None: (records, next_cursor)}
        self.fail_first = fail_first
        self.calls = 0

    def fetch(self, cursor):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise ConnectionError("transient failure")
        return self.pages[cursor]


def record(url, text, license="CC-BY-4.0"):
    return {"url": url, "content": text.encode(), "license": license}


@pytest.fixture
def env(tmp_path):
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "sources:\n"
        "  - id: mock\n"
        "    type: api\n"
        "    endpoint: http://unused\n"
        "    rate_limit_per_min: 6000\n"
        "    license_note: test\n"
    )
    data_dir = tmp_path / "datasets"
    data_dir.mkdir()
    return str(sources), str(data_dir)


def provenance_lines(data_dir):
    path = os.path.join(data_dir, "provenance.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_resume_from_cursor_produces_no_duplicates(env):
    sources, data_dir = env
    pages = {
        None: ([record("u/1", "one"), record("u/2", "two")], "c1"),
        "c1": ([record("u/3", "three")], None),
    }
    # First run stops after page 1 (checkpoint saved with cursor c1).
    collect("mock", sources, data_dir, adapter=MockAdapter(pages), sleep_fn=lambda s: None, max_pages=1)
    assert len(provenance_lines(data_dir)) == 2
    # Second run resumes from c1 and must not re-store page-1 records.
    counts = collect("mock", sources, data_dir, adapter=MockAdapter(pages), sleep_fn=lambda s: None)
    lines = provenance_lines(data_dir)
    assert len(lines) == 3
    assert len({l["content_sha256"] for l in lines}) == 3
    assert counts["fetched"] == 1


def test_retry_backoff_delays_grow_then_succeeds(env):
    sources, data_dir = env
    delays = []
    pages = {None: ([record("u/1", "one")], None)}
    adapter = MockAdapter(pages, fail_first=2)
    counts = collect("mock", sources, data_dir, adapter=adapter, sleep_fn=delays.append)
    assert counts["fetched"] == 1
    backoffs = [d for d in delays if d >= 1.0]  # rate-limit waits are tiny
    assert backoffs == [1.0, 2.0]


def test_retry_gives_up_after_max_retries():
    calls = []

    def always_fails():
        calls.append(1)
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        retry_backoff(always_fails, retries=3, sleep_fn=lambda s: None)
    assert len(calls) == 4  # initial + 3 retries


def test_provenance_records_are_complete(env):
    sources, data_dir = env
    pages = {None: ([record("u/1", "one"), record("u/2", "two")], None)}
    collect("mock", sources, data_dir, adapter=MockAdapter(pages), sleep_fn=lambda s: None)
    lines = provenance_lines(data_dir)
    assert lines
    for line in lines:
        for field in PROVENANCE_FIELDS:
            assert line.get(field), f"missing {field}"


def test_cross_split_detects_exact_and_near_duplicates():
    train = [
        "the quick brown fox jumps over the lazy dog near the river bank today",
        "completely unrelated sentence about training language models efficiently",
    ]
    validation = [
        "the quick brown fox jumps over the lazy dog near the river bank today",  # exact
        "the quick brown fox jumps over the lazy dog near the river bank yesterday",  # near
        "another unrelated example about cooking pasta at home",
    ]
    findings = cross_split_check({"train": train, "validation": validation})
    kinds = {(f["kind"], f["indices"]) for f in findings}
    assert ("exact", (0, 0)) in kinds
    assert any(k == "near" and idx[0] == 0 for k, idx in kinds)
    clean = cross_split_check({"train": [train[1]], "validation": [validation[2]]})
    assert clean == []


def test_malformed_record_is_logged_and_run_continues(env):
    sources, data_dir = env
    pages = {None: ([{"url": "u/bad"}, record("u/2", "good two")], None)}  # first lacks content
    counts = collect("mock", sources, data_dir, adapter=MockAdapter(pages), sleep_fn=lambda s: None)
    assert counts == {"fetched": 1, "skipped": 0, "errors": 1}
    errors_path = os.path.join(data_dir, "errors.jsonl")
    assert os.path.exists(errors_path)
    with open(errors_path) as f:
        entries = [json.loads(line) for line in f if line.strip()]
    assert entries and entries[0]["url"] == "u/bad"
    assert len(provenance_lines(data_dir)) == 1


CODEX_JSONL = (
    '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
    '{"type":"turn.completed","usage":{"input_tokens":600000,"output_tokens":400000}}\n'
)


def slot_routing(cap_usd, price=1.0, max_calls=None, max_per_call=1.0):
    slot = {"provider": "openai", "model": "primary-x", "fallback": "fallback-y",
            "cost_cap_usd": cap_usd, "price_per_1m_tokens_usd": price,
            "max_cost_per_call_usd": max_per_call}
    if max_calls is not None:
        slot["max_calls"] = max_calls
    return {"slots": {"judge": slot}}


def usage_entries(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_slot_executor_logs_every_attempt_with_tokens_and_cost(tmp_path):
    from collector.slots import run_slot

    usage = str(tmp_path / "usage.jsonl")

    def fake_run(cmd, timeout_s):
        if "primary-x" in cmd:
            raise RuntimeError("primary down")
        return CODEX_JSONL

    out = run_slot(slot_routing(cap_usd=10.0, max_per_call=2.0), "judge", "p1",
                   run_fn=fake_run, usage_log=usage)
    assert out == "ok"
    entries = usage_entries(usage)
    # both attempts logged: failed primary AND successful fallback
    assert [e["status"] for e in entries] == ["error", "ok"]
    # failed call without parsable output is charged the full reservation, not zero
    assert entries[0]["model"] == "primary-x"
    assert entries[0]["est_cost_usd"] == pytest.approx(2.0)
    assert entries[0]["cost_basis"] == "reserved-unknown"
    ok = entries[1]
    assert ok["model"] == "fallback-y" and ok["fallback_used"] is True
    assert ok["tokens"] == 1_000_000  # real CLI usage, not character counts
    assert ok["est_cost_usd"] == pytest.approx(1.0)  # 1M tokens at $1/1M
    assert ok["cost_basis"] == "parsed"


def test_slot_executor_failed_call_with_output_charges_parsed_usage(tmp_path):
    from collector.slots import SlotCommandError, run_slot

    usage = str(tmp_path / "usage.jsonl")

    def fake_run(cmd, timeout_s):
        # e.g. timeout after the turn.completed event was already emitted
        raise SlotCommandError("timed out", stdout=CODEX_JSONL)

    with pytest.raises(RuntimeError, match="failed on all models"):
        run_slot(slot_routing(cap_usd=10.0, max_per_call=2.0), "judge", "p1",
                 run_fn=fake_run, usage_log=usage)
    for entry in usage_entries(usage):
        assert entry["status"] == "error"
        assert entry["tokens"] == 1_000_000
        assert entry["est_cost_usd"] == pytest.approx(1.0)  # parsed, not reservation
        assert entry["cost_basis"] == "parsed"


def test_slot_executor_reservation_prevents_overshoot(tmp_path):
    from collector.slots import run_slot

    usage = str(tmp_path / "usage.jsonl")
    calls = []

    def fake_run(cmd, timeout_s):
        calls.append(cmd)
        return CODEX_JSONL

    # cap 0.5 but a single call may cost up to 1.0: refused BEFORE any spend
    with pytest.raises(RuntimeError, match="would be exceeded"):
        run_slot(slot_routing(cap_usd=0.5, max_per_call=1.0), "judge", "p",
                 run_fn=fake_run, usage_log=usage)
    assert calls == []


def test_slot_executor_enforces_cost_cap_hard_stop(tmp_path):
    from collector.slots import run_slot

    usage = str(tmp_path / "usage.jsonl")
    calls = []

    def fake_run(cmd, timeout_s):
        calls.append(cmd)
        return CODEX_JSONL

    # zero cap: refused before any model call
    with pytest.raises(RuntimeError, match="cost cap"):
        run_slot(slot_routing(cap_usd=0.0), "judge", "p", run_fn=fake_run, usage_log=usage)
    assert calls == []

    # cap 2.0, reservation 1.0: first call spends ~$1.0; second would reserve
    # past the cap (1.0 + 1.0 > 2.0 is false → allowed; spend 2.0), third refused
    routing = slot_routing(cap_usd=2.0, max_per_call=1.0)
    run_slot(routing, "judge", "p1", run_fn=fake_run, usage_log=usage)
    run_slot(routing, "judge", "p2", run_fn=fake_run, usage_log=usage)
    assert len(calls) == 2
    with pytest.raises(RuntimeError, match="cost cap"):
        run_slot(routing, "judge", "p3", run_fn=fake_run, usage_log=usage)
    assert len(calls) == 2  # no extra model call


def test_slot_executor_max_calls_and_unknown_provider(tmp_path):
    from collector.slots import run_slot

    usage = str(tmp_path / "usage.jsonl")

    def fake_run(cmd, timeout_s):
        return CODEX_JSONL

    routing = slot_routing(cap_usd=100.0, max_calls=1)
    run_slot(routing, "judge", "p1", run_fn=fake_run, usage_log=usage)
    with pytest.raises(RuntimeError, match="max_calls"):
        run_slot(routing, "judge", "p2", run_fn=fake_run, usage_log=usage)

    with pytest.raises(ValueError, match="unknown provider"):
        run_slot({"slots": {"j": {"provider": "nope", "model": "m", "cost_cap_usd": 1,
                                  "price_per_1m_tokens_usd": 1, "max_cost_per_call_usd": 0.5}}},
                 "j", "p", run_fn=fake_run)


def test_slot_parsers_extract_text_and_tokens():
    from collector.slots import _parse_anthropic, _parse_openai

    claude_json = json.dumps({"type": "result", "result": "PILOT-OK",
                              "usage": {"input_tokens": 10, "output_tokens": 5,
                                        "cache_read_input_tokens": 3}})
    parsed = _parse_anthropic(claude_json)
    assert parsed == {"text": "PILOT-OK", "tokens": 18}

    parsed = _parse_openai(CODEX_JSONL + "not-json noise\n")
    assert parsed["text"] == "ok" and parsed["tokens"] == 1_000_000


def test_slot_executor_rechecks_budget_before_fallback(tmp_path):
    from collector.slots import run_slot

    usage = str(tmp_path / "usage.jsonl")
    calls = []

    def fake_run(cmd, timeout_s):
        calls.append(cmd)
        raise RuntimeError("primary down")  # no parsable output → reservation charged

    # cap=1, reservation=1, max_calls=1: primary's failed reservation exhausts the
    # budget, so the fallback must NOT be attempted (previously: 2 calls, $2 spend)
    routing = slot_routing(cap_usd=1.0, max_per_call=1.0, max_calls=1)
    with pytest.raises(RuntimeError, match="cost cap|max_calls"):
        run_slot(routing, "judge", "p", run_fn=fake_run, usage_log=usage)
    assert len(calls) == 1  # fallback never ran
    entries = usage_entries(usage)
    assert len(entries) == 1 and entries[0]["model"] == "primary-x"
    assert sum(e["est_cost_usd"] for e in entries) == pytest.approx(1.0)  # not $2


def test_default_run_cleans_up_temp_workdir(monkeypatch, tmp_path):
    import glob
    import tempfile as _tempfile

    from collector.slots import SlotCommandError, _default_run

    monkeypatch.setattr(_tempfile, "tempdir", str(tmp_path))
    _default_run([sys.executable, "-c", "print('hi')"], timeout_s=30)
    with pytest.raises(SlotCommandError):
        _default_run([sys.executable, "-c", "raise SystemExit(3)"], timeout_s=30)
    assert glob.glob(str(tmp_path / "slot-*")) == []  # removed on success AND failure
