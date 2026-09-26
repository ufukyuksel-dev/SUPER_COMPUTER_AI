"""Slot executor: run one bounded prompt against a routing-config slot model.

This is how the curator actually delegates to collector/generator/judge tiers.
Every attempt (success or failure, primary or fallback) is appended to a JSONL
usage log with token usage and estimated cost, and the slot's `cost_cap_usd`
is enforced as a reservation-based hard stop: a call is refused unless the
logged spend PLUS the slot's `max_cost_per_call_usd` reservation fits the cap,
so a single call can never overshoot the cap by more than the declared
per-call maximum. Failed calls are never assumed free: their usage is parsed
from whatever output exists, else the full reservation is charged
(`cost_basis: "reserved-unknown"`).

Calls run in an empty temporary working directory with project/user setting
sources disabled where supported, so slot calls do not pay this repo's agent
context overhead.

CLI (run from tools/dataset-collector): python3 -m collector.slots <routing.yaml> <slot> "<prompt>"
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import yaml

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class SlotCommandError(RuntimeError):
    """Command failure that may still carry partial stdout with usage info."""

    def __init__(self, message, stdout=""):
        super().__init__(message)
        self.stdout = stdout or ""


def _anthropic_cmd(model, prompt):
    # --setting-sources project + empty cwd → no user/project context loaded
    return ["claude", "-p", "--no-session-persistence", "--setting-sources", "project",
            "--model", model, "--output-format", "json", prompt]


def _parse_anthropic(stdout):
    obj = json.loads(stdout)
    usage = obj.get("usage", {}) or {}
    tokens = 0
    for key in ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            tokens += value
    return {"text": obj.get("result", ""), "tokens": tokens}


def _openai_cmd(model, prompt):
    return ["codex", "exec", "--ephemeral", "--skip-git-repo-check",
            "-s", "read-only", "--json", "-m", model, prompt]


def _parse_openai(stdout):
    # JSONL events per event-taxonomy.md: item.completed (agent_message), turn.completed (usage)
    text, tokens = "", 0
    for line in _ANSI_RE.sub("", stdout).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {}) or {}
            if item.get("type") == "agent_message":
                text = item.get("text", text)
        elif event.get("type") == "turn.completed":
            usage = event.get("usage", {}) or {}
            total = usage.get("total_tokens")
            if isinstance(total, int):
                tokens = total
            else:
                tokens = sum(v for v in usage.values() if isinstance(v, int))
    return {"text": text, "tokens": tokens}


PROVIDERS = {
    "anthropic": {"cmd": _anthropic_cmd, "parse": _parse_anthropic},
    "openai": {"cmd": _openai_cmd, "parse": _parse_openai},
}


def load_routing(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _default_run(cmd, timeout_s):
    workdir = tempfile.mkdtemp(prefix="slot-")  # isolate from repo agent context
    try:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                                  stdin=subprocess.DEVNULL, cwd=workdir)
        except subprocess.TimeoutExpired as exc:
            out = exc.output
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            raise SlotCommandError(f"slot command timed out after {timeout_s}s", stdout=out or "")
        if proc.returncode != 0:
            raise SlotCommandError(
                f"slot command failed ({proc.returncode}): {proc.stderr.strip()[:500]}",
                stdout=proc.stdout,
            )
        return proc.stdout
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _read_usage(usage_log, slot_name):
    """Return (attempt_count, est_spend_usd) already logged for this slot."""
    attempts, spend = 0, 0.0
    if usage_log and os.path.exists(usage_log):
        with open(usage_log) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("slot") == slot_name:
                    attempts += 1
                    spend += float(entry.get("est_cost_usd") or 0.0)
    return attempts, spend


def _log(usage_log, entry):
    if not usage_log:
        return
    os.makedirs(os.path.dirname(usage_log) or ".", exist_ok=True)
    entry = dict(entry)
    entry["at"] = datetime.now(timezone.utc).isoformat()
    with open(usage_log, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_slot(routing, slot_name, prompt, run_fn=None, usage_log=None, timeout_s=300):
    """Execute one prompt on the named slot's model; fall back once if defined.

    Contract enforcement (see model-routing-contract.md):
    - reservation-based hard cap: refuse when logged spend + `max_cost_per_call_usd`
      would exceed `cost_cap_usd` — no call can overshoot the cap by more than
      the declared per-call maximum;
    - every attempt logged; failed attempts charge parsed usage when output is
      available, else the full per-call reservation (`reserved-unknown`);
    - optional `max_calls` is a secondary attempt-count stop.

    Returns the model output text.
    """
    run_fn = run_fn or _default_run
    slot = routing["slots"][slot_name]
    provider_name = slot["provider"]
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"unknown provider '{provider_name}' for slot '{slot_name}'")

    cost_cap = float(slot["cost_cap_usd"])
    price_per_1m = float(slot["price_per_1m_tokens_usd"])
    reservation = float(slot["max_cost_per_call_usd"])
    max_calls = slot.get("max_calls")
    attempts, spend = _read_usage(usage_log, slot_name)

    def check_budget():
        # re-checked before EVERY model attempt, fallback included
        if spend + reservation > cost_cap:
            raise RuntimeError(
                f"slot '{slot_name}' cost cap would be exceeded "
                f"(est ${spend:.4f} + reservation ${reservation:.4f} > cap ${cost_cap:.4f}); run paused"
            )
        if max_calls is not None and attempts >= max_calls:
            raise RuntimeError(f"slot '{slot_name}' reached max_calls={max_calls}; run paused")

    models = [slot["model"]]
    if slot.get("fallback"):
        models.append(slot["fallback"])
    last_error = None
    for model in models:
        check_budget()
        cmd = provider["cmd"](model, prompt)
        base = {"slot": slot_name, "provider": provider_name, "model": model,
                "fallback_used": model != slot["model"], "prompt_chars": len(prompt)}
        try:
            parsed = provider["parse"](run_fn(cmd, timeout_s))
            tokens = parsed["tokens"]
            _log(usage_log, {**base, "status": "ok", "tokens": tokens,
                             "est_cost_usd": tokens / 1e6 * price_per_1m,
                             "cost_basis": "parsed", "output_chars": len(parsed["text"])})
            return parsed["text"]
        except Exception as exc:
            last_error = exc
            tokens = 0
            try:
                tokens = provider["parse"](getattr(exc, "stdout", "") or "")["tokens"]
            except Exception:
                tokens = 0
            if tokens > 0:
                cost, basis = tokens / 1e6 * price_per_1m, "parsed"
            else:
                # never assume a failed call was free: charge the reservation
                tokens, cost, basis = None, reservation, "reserved-unknown"
            _log(usage_log, {**base, "status": "error", "tokens": tokens,
                             "est_cost_usd": cost, "cost_basis": basis,
                             "error": str(exc)[:500]})
            spend += cost
            attempts += 1
    raise RuntimeError(f"slot '{slot_name}' failed on all models: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="Run a prompt on a routing-config slot model.")
    parser.add_argument("routing")
    parser.add_argument("slot")
    parser.add_argument("prompt")
    parser.add_argument("--usage-log", default="state/slot-usage.jsonl")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    routing = load_routing(args.routing)
    sys.stdout.write(run_slot(routing, args.slot, args.prompt,
                              usage_log=args.usage_log, timeout_s=args.timeout))


if __name__ == "__main__":
    main()
