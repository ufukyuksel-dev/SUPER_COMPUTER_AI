# Evaluation Pitfalls

Use this catalog as a pre-run and interpretation gate.

| Failure mode | Detect | Correct |
|---|---|---|
| Goal/metric mismatch | High score does not imply the intended user or risk outcome | State the decision and observable behavior first; justify every metric. |
| Aggregate masking | Aggregate improves while a critical language, tenant, safety, or difficulty slice regresses | Predeclare slices and per-slice gates; report all slices. |
| Data leakage | Examples or near-duplicates appear in training, prompts, tuning, synthetic parents, or judge calibration | Track provenance, group/deduplicate before splitting, protect holdouts. |
| Benchmark contamination | Memorized benchmark performance is mistaken for workload ability | Add fresh/private slices and contamination checks; qualify public scores. |
| Weak or shifting baseline | Candidate gains depend on an outdated or differently configured baseline | Pin and rerun a strong baseline under identical conditions. |
| Single stochastic run | Verdict changes with seed/order/run | Repeat, randomize or pair appropriately, and report uncertainty. |
| Statistical without practical value | Difference is detectable but too small to matter | Predeclare a practical-effect floor and cost/risk trade-off. |
| Underpowered comparison | Wide uncertainty cannot distinguish candidates | Increase representative samples/repeats or report `inconclusive`. |
| Slice cherry-picking | Only favorable subsets or runs are reported | Freeze the analysis plan and retain raw item-level results. |
| Uncalibrated LLM judge | Judge disagrees with adjudicated humans or favors style/position/model identity | Blind/order-randomize, calibrate, measure agreement/bias, and adjudicate. |
| Judge context leakage | Expected answer, repository skill, hidden reasoning, or candidate internals reach the judge | Run in an empty isolated context with only rubric, allowed reference, and observable output. |
| Malformed judge result | Free-form or invalid verdict is silently coerced | Enforce a strict schema and fail closed; store raw output. |
| Workload mismatch | Paper/leaderboard setup differs in data, hardware, prompts, tools, or constraints | Reproduce a decision-relevant slice and label external validity. |
| Missing failure accounting | Timeouts, refusals, parse errors, or tool failures disappear from scores | Define denominators and error policy before execution. |
| Irreproducible record | Result lacks versions, config, dataset hash, seed, or raw artifacts | Store a run manifest and exact command for every result. |

Before a release decision, confirm that thresholds were fixed before candidate results, raw outputs remain auditable, critical regressions are visible, and inconclusive evidence has not been converted into a pass.
