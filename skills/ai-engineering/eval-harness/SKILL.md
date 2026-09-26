---
name: eval-harness
description: "Use when designing or running evaluations — metric selection, eval set construction, LLM-as-judge setup, regression tests for model outputs, significance of comparisons, and assessing claims from new papers/models. Do NOT use for end-to-end delivery verification (see skill implementation-verification)."
---

# Evaluation Harness

## Boundaries

- Own behavior definitions, evaluation data and slices, metrics, thresholds, human rubrics, LLM judging, model-output regression, and comparison significance.
- To verify current paper, model, benchmark, API, or judge facts, see skill ai-research; interpret only source-backed claims against the target workload.
- For training configuration, see skill training-peft.
- For execution of a completed deliverable against acceptance criteria, see skill implementation-verification. Evaluation evidence may feed verification but does not prove end-to-end delivery.
- Never expose hidden chain-of-thought. Evaluate observable outputs and concise evidence fields only.

## Decision Workflow

1. State the decision the evaluation will support, target behavior, unacceptable behavior, baseline, population, workload, risk, and practical improvement required.
2. Build a provenance-tracked evaluation set with representative and adversarial slices, protected holdouts, deduplication, leakage checks, sample policy, and sufficient coverage for the decision.
3. Predeclare per-slice and aggregate metrics, thresholds, weighting, repeats, uncertainty method, practical-significance floor, and regression policy before viewing candidate results.
4. Select direct task metrics where possible. Use human rubrics or LLM-as-judge only for behavior that cannot be measured adequately with deterministic checks.
5. For an LLM judge:
   - run it in an isolated empty context that cannot load repository skills, candidate internals, or expected answers;
   - provide only the rubric, allowed reference material, and observable candidate output;
   - require a strict structured verdict schema with bounded evidence, validate it, and treat malformed output as failure;
   - blind candidate identity/order, calibrate against adjudicated human examples, repeat stochastic calls, and measure agreement and bias;
   - store raw judge input/output, model/version, parameters, rubric version, parse result, and calibration evidence.
6. Run the same versioned harness against baseline and candidates. Capture raw item-level results, errors, latency/cost when relevant, environment, seeds, versions, and timestamps.
7. Compare with repeats, uncertainty intervals or an appropriate paired analysis, sample-size adequacy, and slice-level regressions. Separate statistical evidence from practical impact.
8. Return `pass`, `fail`, or `inconclusive` against predeclared gates. Preserve failures and uncertainty; never cherry-pick a favorable slice or single run.

### Assessing a new paper or model claim

1. To verify the original claim and artifacts, see skill ai-research.
2. Record baseline, dataset, metric, sample size, repeats/variance, hardware, software, and evaluation method.
3. Test comparability to the target workload and identify contamination, missing variance, weak baselines, or irreproducible settings.
4. Reproduce the smallest decision-relevant comparison when feasible. Label unreproduced or workload-mismatched claims accordingly.

## Required Output

Return the decision and behavior contract, dataset/slice manifest, metric and threshold registry, judge specification and calibration evidence when used, reproducible command/config, raw artifact locations, aggregate and slice results, uncertainty/practical-impact interpretation, regressions, and final `pass/fail/inconclusive` result.

Read [evaluation pitfalls](references/eval-pitfalls.md) before finalizing the design or interpreting a close comparison.

## Tool Requirements & Degradation

- Require dataset/version inspection, a repeatable candidate runner, deterministic scoring where possible, raw artifact storage, and analysis capable of repeats and uncertainty.
- Require an isolated empty working context and strict schema validation for LLM judging. Do not run a judge in the repository context.
- If automated judging is unavailable, use a blinded human rubric or deterministic subset and mark uncovered subjective behavior `UNVERIFIED`.
- If sample size, repeats, baseline, or slice coverage is inadequate, report `inconclusive`; do not weaken the threshold after seeing results.
- If a paper/model source is unreachable, do not repeat its abstract as proof. Create a bounded research task and see skill ai-research; keep the claim unverified.
- If the candidate cannot run, separate infrastructure failure from measured product behavior and do not manufacture scores.

## Failure Modes

- Using one aggregate score while hiding critical slice regressions.
- Evaluating on training, prompt-development, synthetic-parent, or otherwise leaked examples.
- Calling one stochastic run significant or treating a tiny numerical gain as practically meaningful.
- Letting the judge see repository skills, hidden expected reasoning, candidate identity, or privileged metadata.
- Accepting malformed judge output, failing to calibrate the judge, or discarding raw judge evidence.
- Comparing candidates with changed prompts, tools, versions, sampling, datasets, or failure handling.
- Repeating a paper abstract or leaderboard result without checking baseline, variance, sample size, and workload match.
- Claiming a completed implementation passed because an offline metric suite passed.
