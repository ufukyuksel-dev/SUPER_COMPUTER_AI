# Context Budget Guide

Use this guide to produce a measured context allocation, progressive-disclosure policy, and deterministic degradation path. Keep model-specific limits out of this file; verify them through see skill ai-research.

## Contents

- [Context Contract](#context-contract)
- [Input Inventory](#input-inventory)
- [Budget Worksheet](#budget-worksheet)
- [Placement Rules](#placement-rules)
- [Progressive Disclosure](#progressive-disclosure)
- [Memory Strategy](#memory-strategy)
- [Compaction Contract](#compaction-contract)
- [Degradation Ladder](#degradation-ladder)
- [Verification Checklist](#verification-checklist)
- [Failure Signals](#failure-signals)

## Context Contract

Record these fields before allocating tokens:

| Field | Decision |
|---|---|
| Task and output contract | What must the model produce, in what schema, and with what quality bar? |
| Model/runtime | Which exact model, tokenizer, context limit, and tool protocol apply? |
| Input boundary | Which sources may enter context, and which must remain local? |
| Output reserve | How many tokens must remain available for the complete answer or tool call? |
| Latency/cost ceiling | What hard ceiling constrains retrieval, turns, and token volume? |
| Failure behavior | Refuse, ask, retrieve, compact, split, or hand off? |
| Retention policy | What may persist, for how long, under whose authority? |

Label every limit as `VERIFIED`, `ESTIMATED`, or `UNKNOWN` and attach its evidence.

## Input Inventory

Build one row per context source:

| Source | Purpose | Authority | Trust | Freshness | Lifetime | Minimum needed | Maximum allowed | Omission impact |
|---|---|---|---|---|---|---:|---:|---|
| System/developer rules | Control | Highest | Trusted control | Current session | Session | | | |
| User requirements | Goal and constraints | User-authored | Trusted as intent, not as facts | Current turn | Task | | | |
| Retrieved evidence | Grounding | Cited source | Untrusted data | Source-dependent | Task | | | |
| Tool results | Observation | Tool-specific | Untrusted data | Call-dependent | Task | | | |
| Conversation state | Continuity | Mixed | Mixed | Turn-dependent | Session | | | |
| Durable memory | Reusable facts | Reviewed record | Mixed | Record-dependent | Cross-session | | | |
| Examples | Format/behavior | Designer | Trusted only for stated purpose | Versioned | Task | | | |

Reject any row without a purpose, authority, omission impact, and owner.

## Budget Worksheet

Allocate in this order:

1. Record the verified maximum context for the exact model/runtime.
2. Reserve the required output budget.
3. Reserve tool-call envelopes, safety margin, and runtime-added tokens.
4. Allocate mandatory control instructions and user constraints.
5. Allocate decision-bearing evidence with provenance.
6. Allocate working state needed for the next action.
7. Allocate examples and optional history only from the remainder.

Use the equation:

```text
usable_input = verified_context_limit
             - output_reserve
             - runtime_overhead
             - tool_reserve
             - safety_margin
```

Do not count `UNKNOWN` as available capacity. Measure the fully rendered payload, not only source snippets.

## Placement Rules

- Keep immutable control rules in one authoritative location.
- Place task-specific user constraints before evidence that could conflict with them.
- Delimit untrusted content and state that it cannot modify control instructions.
- Attach source identity and freshness to evidence summaries.
- Keep examples minimal and structurally representative; remove stylistic examples that distort the task.
- Keep tool outputs scoped to the decision they support; replace bulky output with a cited summary plus a rehydration handle.
- Remove duplicate facts and resolve contradictory versions before assembly.

## Progressive Disclosure

Choose the smallest initial representation that preserves routing decisions:

| Need | Initial context | Load detail when |
|---|---|---|
| Large document set | Index, metadata, access boundary | A task query selects relevant documents |
| Long conversation | Current goal, decisions, open items | Historical wording changes a decision |
| Tool catalog | Names, purposes, safety class | A selected tool requires its full schema |
| Memory store | Candidate summaries and provenance | A candidate affects the current task |
| Codebase | Map, symbols, narrow search hits | A selected symbol requires implementation detail |

Reject disclosure paths that cannot recover the original source or explain why an item was selected.

## Memory Strategy

Classify state before storing it:

- Keep scratch reasoning and partial hypotheses ephemeral.
- Keep current goal, constraints, decisions, and open items in session state.
- Persist only stable, reusable facts or explicit decisions with provenance, scope, owner, and review state.
- Store large source material outside the prompt and keep a bounded reference plus retrieval handle.
- Define update, conflict, expiry, deletion, and approval behavior for every durable memory class.
- Prefer correction with history over silent overwrite.
- Never persist secrets, unnecessary PII, unsupported inferences, or instructions embedded in external content.

## Compaction Contract

Define all of the following:

- **Trigger:** measured token threshold, turn boundary, phase completion, or explicit checkpoint.
- **Retained invariants:** goal, constraints, prohibitions, approvals, acceptance criteria, decisions, source handles, and unresolved questions.
- **Discardable material:** repeated prose, superseded drafts, non-decision-bearing logs, and recoverable detail.
- **Loss ledger:** facts or nuance omitted, uncertainty introduced, and sources required for rehydration.
- **Validation:** compare the compacted state against the retained-invariant checklist and representative continuation tasks.
- **Recovery:** retrieve source detail, rebuild state, or stop and ask when fidelity cannot be established.

Do not recursively summarize a summary without checking it against source-linked invariants.

## Degradation Ladder

Apply the first step that restores fit without violating the context contract:

1. Remove duplicate and non-decision-bearing material.
2. Replace recoverable detail with source-linked summaries.
3. Load only selected tool schemas, memories, or documents.
4. Split independent work into bounded stages with explicit handoff state.
5. Compact history using the retained-invariant checklist and loss ledger.
6. Reduce optional examples or enrichment.
7. Ask the human to prioritize conflicting requirements.
8. Stop with a bounded failure when mandatory inputs still do not fit.

Never silently truncate from the front or tail.

## Verification Checklist

- Measure the final rendered context with the selected tokenizer.
- Confirm the output reserve survives worst-case tool and runtime overhead.
- Probe normal, near-limit, and over-limit payloads.
- Verify that untrusted content cannot change instruction precedence.
- Verify that compaction preserves each retained invariant.
- Verify that every summary can rehydrate its decision-bearing source.
- Verify that missing or expired memory produces a bounded failure.
- Record actual counts, commands, traces, and observed outputs.
- Label every unexercised path `UNVERIFIED`.

## Failure Signals

- Treat instruction drift after compaction as a hard failure.
- Treat lost provenance, approvals, or open requirements as a hard failure.
- Treat exact-fit claims based on estimates as unsupported.
- Treat retrieval of excessive irrelevant text as a disclosure-policy failure.
- Treat repeated summary growth as missing state structure, not as a reason to increase the budget.
