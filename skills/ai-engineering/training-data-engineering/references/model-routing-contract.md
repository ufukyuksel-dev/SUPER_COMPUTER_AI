# Model Routing Contract

Every dataset run references a versioned routing config (`tools/dataset-collector/config/routing-<run>.yaml`). No model names live in the skill; candidates are resolved at run time via skill ai-research + skill model-selection-hf and written here.

**Execution:** slot calls go through the slot executor — this is the only supported delegation path:

```bash
(cd tools/dataset-collector && python3 -m collector.slots config/routing-<run>.yaml <slot> "<bounded prompt>" \
  [--usage-log state/slot-usage.jsonl] [--timeout 300])
```

The executor logs EVERY attempt (success or failure, primary or fallback) to the usage log with
real CLI token usage and `est_cost_usd = tokens / 1e6 * price_per_1m_tokens_usd`, and enforces
`cost_cap_usd` as a hard stop against that log before any model call.

```yaml
run: sft-tr-support-v1
resolved_at: 2026-08-24        # date the candidates were researched
slots:
  collector:                   # cheap; high-volume fetch-adjacent labeling
    provider: anthropic | openai
    model: <model>
    revision: <revision-or-date>
    cost_cap_usd: 5                  # HARD stop: spend + max_cost_per_call_usd may never exceed it
    max_cost_per_call_usd: 0.25      # per-call reservation; also charged when a failed call's usage is unparsable
    price_per_1m_tokens_usd: <est>   # blended estimate recorded when candidates are researched
    batch_size: 64
    temperature: 0.0
    fallback: <cheaper-or-alternate-model>
    max_calls: <optional-attempt-cap>
  generator:                   # upgraded per task difficulty
    ...same fields...
  judge:                       # strong; different family than generator when possible
    ...same fields...
```

Rules:

- Collector may be cheap; generator and judge are upgraded based on task difficulty and language.
- Judge and generator should come from different model families; if impossible, record the risk in the run manifest.
- Cost caps are reservation-based hard stops: the executor refuses a call when logged spend + `max_cost_per_call_usd` would exceed `cost_cap_usd`, so no single call can overshoot the cap beyond the declared per-call maximum. Failed calls are charged their parsed usage when output exists, else the full reservation (`cost_basis: "reserved-unknown"`) — a failure is never free.
- Slot calls run in an empty temporary directory with repo/user context sources disabled. The CLI carries a fixed ~20-25k-token overhead per call (measured 2026-08-24), so **batch 50-200 records into one slot call** for cheap/high-volume work to amortize it; single-record calls are for hard teacher examples and judge audit samples only. No direct provider-API adapter is used (decision 2026-08-24).
- The usage log is the run manifest's model record: it lists the models actually used per attempt (including failed primaries and fallbacks) with tokens and estimated cost, so results are reproducible.
- The curator agent itself may run on a cheap model and delegate bounded sub-tasks (one example batch, fixed input/output contract) to stronger slot models.
