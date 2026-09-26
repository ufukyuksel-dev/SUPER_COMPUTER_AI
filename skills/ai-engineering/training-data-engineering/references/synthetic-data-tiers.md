# Synthetic Data Tiers

Order of preference — cheaper tiers first; escalate only what they cannot decide:

1. **Deterministic code**: parsing, schema validation, hashing, exact dedup, format checks. Never spend model tokens on checks code can do.
2. **Cheap model**: high-volume labeling, classification, filtering, candidate generation. Accept noisy output; downstream gates catch errors.
3. **Strong teacher**: hard synthetic examples, correctness-critical answers, low-resource-language generation.
4. **Strong judge or human sample**: quality audit on a sampled subset; measures agreement and rejects below-threshold batches.

## Seeding and isolation

- Seeds and taxonomies come only from the training split. Validation examples never appear in generator prompts or judge context.
- Track lineage: every synthetic example records its seed example(s) and generation slot.

## Audit gates for synthetic batches

- Coverage: every taxonomy node has a minimum example count.
- Diversity: near-dedup rate within the synthetic batch below threshold; length/style distribution not collapsed.
- Correctness: judge or human agreement above threshold on the audit sample.
- Ratio: synthetic-to-real ratio stays within the project target.

## LoRA/QLoRA note

LoRA and QLoRA are not distinct dataset types; they usually consume the same SFT/chat data. The difference is weight-update and memory strategy, owned by skill training-peft.
