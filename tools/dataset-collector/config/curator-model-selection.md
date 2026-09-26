# Dataset-Curator Agent Model Selection

Selected: 2026-08-24. Applies to the AGENT itself; batch collector/generator/judge slots are
resolved per run in `routing-<run>.yaml` (executed via `collector/slots.py`) and are
independent of this choice.

| Platform | Field | Selected | Evidence |
|---|---|---|---|
| Claude Code | `agents/claude/dataset-curator.md` → `model: haiku` | Claude Haiku 4.5 (small-tier alias) | Pilot verified 2026-08-24: `claude -p --model haiku "Reply exactly: PILOT-OK"` → `PILOT-OK` (~6.4s). |
| Codex CLI | `agents/codex/dataset-curator.toml` → `model = "gpt-5.6-luna"` | GPT-5.6 luna (small tier of the current 5.6 family; also the model used in the official subagent docs example at developers.openai.com/codex/subagents.md) | Pilot verified 2026-08-24: `codex exec --ephemeral -m gpt-5.6-luna "Reply exactly: PILOT-OK"` → `PILOT-OK` (6,522 tokens, ~7.7s). |

Rejected: `gpt-5-mini` — real invocation on 2026-08-24 returned
`invalid_request_error: The 'gpt-5-mini' model is not supported when using Codex with a
ChatGPT account.` API-price pages are not evidence of Codex-CLI availability; selection is
now grounded in actual local invocations.

**Per-call overhead measurement (2026-08-24, isolated empty cwd + `--setting-sources project`):**
haiku ≈ 24.8k tokens/call, gpt-5.6-luna ≈ 21.7k tokens/call for a 22-char prompt — fixed CLI
harness overhead. **Decision (2026-08-24): no API adapter.** Cheap/high-volume work is sent to
Luna in batches of 50-200 records per slot call to amortize the overhead; hard examples go to
the teacher slot, a small sample to the judge (see model-routing-contract.md).

First real curation run: record run id, spend, and gate outcomes here to complete the pilot
record (quality side remains UNVERIFIED until then).

Override: edit the `model` field in either role file; note the change and reason in this file.
