# PEFT Experiment Recipes

Use these as versioned experiment records. Derive starting values from verified model/framework guidance or a bounded pilot; never copy a universal configuration.

## Common preflight

- Pin base model/revision, tokenizer/template, framework/library versions, dataset version, seed, precision, quantization, and hardware.
- Verify target-module names and adapter/quantization compatibility from the actual model and current framework.
- Establish data provenance, rights, deduplication, leakage-safe splits, baseline output, quality gates, and resource budget.
- Validate save, load, merge/export when required, resume, and inference compatibility on a tiny run.

## LoRA experiment record

| Field | Starting value and source | Search bounds | Reason | Observed result |
|---|---|---|---|---|
| Target modules/layers |  |  |  |  |
| Rank/capacity |  |  |  |  |
| Scaling/alpha |  |  |  |  |
| Dropout |  |  |  |  |
| Learning rate/schedule |  |  |  |  |
| Effective batch/accumulation |  |  |  |  |
| Sequence length/packing |  |  |  |  |
| Epoch/step budget |  |  |  |  |
| Precision/checkpointing |  |  |  |  |
| Checkpoint/eval cadence |  |  |  |  |

## QLoRA-specific gates

- Verify the base-weight quantization type, compute dtype, storage dtype, kernel/framework support, and preparation path.
- Account for adapter, optimizer, gradients, activations, checkpoints, allocator overhead, and margin; do not equate quantized weight size with training memory.
- Compare against a simpler LoRA or frozen-baseline path when feasible so quantization impact is observable.
- Test final adapter loading and any merge/export path in the intended inference runtime.

## Training gates

| Gate | Pass evidence | Stop/rollback condition |
|---|---|---|
| Data | Rights, lineage, schema, dedup, split audit | Unknown rights, leakage, corruption, unacceptable imbalance |
| Tiny run | Forward/backward, masks, logs, save/load/resume | Instability, invalid labels/masks, corrupt checkpoint |
| Pilot | Held-out improvement with resource envelope | Divergence, memorization, quality or safety regression |
| Scale | Versioned config, budget approval, stable checkpoint cadence | Budget breach, instability, worsening validation slices |
| Handoff | Reproducible checkpoint, blind predictions, provenance | Missing artifact/config/logs or test-set contamination |

Record rejected configurations, raw metrics, seeds/repeats, known regressions, and the reason for selecting a checkpoint. Report inconclusive comparisons as inconclusive.
