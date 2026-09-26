---
name: training-peft
description: "Use when adapting or training models on an already-curated dataset — method selection across continued pretraining, full-parameter fine-tuning, SFT, LoRA/QLoRA/PEFT, and preference/post-training methods; training configs, hyperparameter starting points, pilots, checkpoints, overfitting diagnosis, load-time format/chat-template compatibility, and evaluation handoff; includes orientation on MoE and distillation (with research delegation for depth). Do NOT use for sourcing, cleaning, dedup, splits, or synthetic generation (see skill training-data-engineering), evaluation design (see skill eval-harness), or serving (see skill model-serving)."
---

# Training and PEFT

## Boundaries

- Own method selection through training execution, checkpoints, diagnosis, and evaluation handoff, consuming a curated dataset handoff. Method selection spans continued pretraining, full-parameter fine-tuning, SFT, LoRA/QLoRA/PEFT, and preference/post-training methods.
- Data production — sourcing, rights, cleaning, quality filtering, dedup, splits, synthetic generation — is owned elsewhere; see skill training-data-engineering. This skill consumes its handoff contract and revalidates compatibility at load time (consumer check, not duplication).
- Treat hyperparameters as experiment starting points, never universal truths. Require a baseline, held-out evidence, and stop/rollback gates.
- For metric, evaluation-set, judge, and significance design, see skill eval-harness.
- For deployment engine and scaled endpoint decisions, see skill model-serving.
- For current framework/model compatibility and deep or novel MoE, distillation, synthetic-data, RLHF, RLAIF, or preference-tuning methods, see skill ai-research.

## Decision Workflow

1. Define the adaptation objective, base model/revision, deployment constraints, output contract, baseline, quality target, failure risks, budget, and evaluation handoff.
2. Consume the dataset handoff contract (see skill training-data-engineering): versioned dataset, all-pass gate report, provenance manifest, split files, and format spec. Missing pieces block training; request them from the producer instead of rebuilding them here.
3. Revalidate at load time with the real tokenizer, chat template, roles, labels, loss masking, truncation, and packing, and spot-check split isolation. Report mismatches back to the producer; do not patch data locally.
4. Establish a reproducible no-adaptation or simpler baseline. Select full SFT, LoRA, QLoRA, or another method from constraints and verified compatibility; use [the PEFT recipes](references/peft-recipes.md) as experiment records, not fixed prescriptions.
6. Declare starting values and search bounds for target modules, rank/capacity, scaling, dropout, precision/quantization, optimizer, learning rate/schedule, effective batch, sequence length, epochs/steps, clipping, seed, checkpoint cadence, and early-stop signal. Cite the source or pilot behind each starting point.
7. Run a small end-to-end pilot first. Validate data loading, loss masking, checkpoint save/load, resumption, inference compatibility, and evaluation handoff before scaling spend.
8. Train with versioned data/config/code, raw metrics, staged checkpoints, held-out checks, and resource telemetry. Diagnose train/validation divergence, slice regressions, instability, collapse, and memorization rather than optimizing training loss alone.
9. Stop or roll back on leakage, rights violations, instability, quality-floor regression, overfitting, unsafe behavior, checkpoint corruption, or budget breach.
10. Hand off the selected checkpoints, exact provenance, configurations, logs, known regressions, and blind held-out predictions; see skill eval-harness. Do not inspect or tune on the held-out test set.

## Advanced-technique Orientation

| Technique | Raise the option when | Required research or gate |
|---|---|---|
| MoE | Conditional capacity or specialization is a measured requirement and serving/training complexity is acceptable | Verify architecture/framework support, routing/load balance, communication, stability, and serving consequences. |
| Distillation | A qualified teacher exists and a smaller/cheaper student must preserve specified behavior | Define teacher/data rights, transfer targets, student capacity, failure slices, and workload evaluation. |
| Synthetic data | Real data is scarce, sensitive, imbalanced, or missing targeted cases | Production is owned elsewhere (see skill training-data-engineering): state the requirement (coverage, ratio, quality bar) and consume its curated, gated output. |
| RLHF/RLAIF or preference tuning | Ranking or preference behavior cannot be achieved reliably through supervised examples alone | Verify the current method, preference/reward data quality, annotator or AI-feedback bias, objective gaming, safety, and conservative baseline. |

Treat this table as a routing map. For a novel method or missing reliable recipe, state the knowledge boundary, create a focused research task, and see skill ai-research. Propose only a conservative baseline plus experiment gate.

## Tool Requirements & Degradation

- Require dataset inspection/validation, deterministic split and dedup tooling, versioned training configuration, accelerator/resource telemetry, checkpoint storage, reproducible inference, and a handoff path to evaluation.
- For current library, model, quantization, target-module, and advanced-method compatibility, see skill ai-research.
- If dataset provenance or rights cannot be established, stop training; do not treat technical access as permission.
- If reliable compatibility evidence is absent, label the configuration experimental, run the smallest safe pilot, and keep scaling blocked.
- If compute is unavailable, produce a versioned experiment plan and validation commands; never fabricate learning curves or checkpoint results.
- If held-out evaluation cannot run, do not select a final checkpoint. Preserve candidates and label comparative quality `UNVERIFIED`.

## Failure Modes

- Training on a handoff whose split isolation was never spot-checked, or re-doing sourcing and cleaning inside the training plan.
- Tuning on held-out test examples or copying validation examples into prompts, synthetic data, or judge context.
- Optimizing only training loss while ignoring overfitting, imbalance, memorization, safety, and slice regressions.
- Claiming one LoRA/QLoRA rank, learning rate, target module set, or recipe works universally.
- Scaling before a checkpoint save/load/resume and end-to-end pilot succeeds.
- Fabricating hyperparameters or research certainty for a novel preference method.
- Treating advanced-technique orientation as a complete implementation recipe.
- Designing the evaluation harness or serving stack inside the training plan.
