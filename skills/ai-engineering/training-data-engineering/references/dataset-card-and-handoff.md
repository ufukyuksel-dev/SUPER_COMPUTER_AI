# Dataset Card and Handoff Contract

## Dataset card fields

- Name, version, date, objective (training goal + target format).
- Sources: per-source id, license/rights status, example counts.
- Pipeline summary: cleaning, filtering, dedup method and thresholds.
- Splits: sizes, split strategy (group/time/provenance keys), isolation guarantees.
- Synthetic share: ratio, tiers used, models used (from run manifest).
- Known limitations and rejected-example summary (counts by reason).

## Gate report table

| Gate | Threshold | Measured | Pass |
|---|---|---|---|
| Provenance completeness | ≥ N% | … | … |
| Schema validity | ≥ N% | … | … |
| Exact+near-duplicate rate | ≤ N% | … | … |
| Cross-split leakage | 0 | … | … |
| PII findings | 0 open | … | … |
| Slice coverage/balance | per-project | … | … |
| Synthetic-to-real ratio | per-project | … | … |
| Audit sample + judge agreement | ≥ N% | … | … |
| Token/record/cost budget | ≤ budget | … | … |

`training-ready` requires every row to pass. A failed row blocks the label and lists remediation.

## Handoff contract to skill training-peft

- Dataset version + paths to split files.
- Format spec: schema, chat template name, role conventions, truncation policy.
- Gate report (all-pass) + dataset card + provenance manifest reference.
- Open caveats the trainer must respect (e.g. slices below target balance).
- Consumer duties: revalidate format/chat-template with the real tokenizer and loader at load time; report mismatches back instead of patching data locally.
- Human approval reference for training start.
