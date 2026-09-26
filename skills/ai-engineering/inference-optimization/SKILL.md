---
name: inference-optimization
description: "Use when tuning inference efficiency on given hardware — GPU/VRAM sizing, quantization (GGUF/AWQ/GPTQ/FP8), KV-cache, batching, speculative decoding, attention optimizations (e.g. FlashAttention), latency/throughput trade-offs. Do NOT use for choosing a serving stack or topology (see skill model-serving) or the model itself (see skill model-selection-hf)."
---

# Inference Optimization

## Boundaries

- Optimize an already identified model and workload on specified hardware and runtime constraints.
- For concrete model selection and license verification, see skill model-selection-hf.
- For serving engine, endpoint topology, scaling, and multi-region design, see skill model-serving; return measured runtime requirements as inputs.
- Treat estimates as capacity hypotheses and measurements as evidence. Never claim that a model fits or an optimization helps until the complete envelope is accounted for and tested.

## Decision Workflow

1. Pin the model revision and architecture, parameter count, precision/artifact, runtime version, accelerator and memory, prompt/output length distributions, context ceiling, concurrency, quality floor, and latency/throughput objectives.
2. For current hardware, kernel, runtime, format, speculative-decoding, and attention-feature compatibility, see skill ai-research. Mark unsupported or unverified combinations before ranking them.
3. Build a memory envelope:
   - estimate weights from the exact artifact or `parameters × effective bytes`, including quantization metadata;
   - calculate KV cache from the model architecture, cache dtype, sequence length, batch/concurrency, and runtime layout;
   - include activations, temporary workspaces, graph/kernel buffers, allocator fragmentation, runtime/process overhead, and a safety margin;
   - show every assumption, unit, and range. Never use weights alone as a fit test.
4. Read [the quantization decision tree](references/quantization-decision-tree.md). Eliminate formats without verified hardware/runtime/model support, then compare memory, quality, conversion, portability, and kernel implications.
5. Locate the bottleneck with separate prefill and decode measurements. Treat batching, cache policy, speculative decoding, prefix reuse, attention kernels, and compilation as independent hypotheses with interactions to test.
6. Define a reproducible benchmark gate: pin versions and settings; use representative prompt/output buckets and concurrency; warm up; repeat runs; capture raw results; and compare against the same quality set.
7. Measure time to first token, inter-token/decode latency, end-to-end p50/p95/p99 latency, tokens per second, request throughput, peak and steady memory, queueing, error rate, and task quality.
8. Select only a configuration that meets the predeclared memory, quality, latency, and throughput gates. Report uncertainty, conflicting benchmarks, and rollback conditions.

### Speculative and attention decision notes

- Test speculative decoding only after verifying draft/target/runtime compatibility. Measure acceptance rate, draft cost, tail latency, memory, and quality; do not assume a universal speedup.
- Test attention optimizations only after verifying model shape, dtype, accelerator, runtime, and kernel support. Compare full workload behavior, not a microbenchmark alone.
- Separate improvements to prefill from improvements to decode. Do not attribute queueing or batching changes to a kernel without controlled evidence.
- When two benchmarks conflict, compare workload, hardware, precision, versions, concurrency, warmup, quality gate, and measurement method. Run a workload-matched reproduction instead of choosing the more favorable result.

## Required Output

Return the pinned input contract, transparent memory worksheet, supported candidate configurations, benchmark protocol, raw-result locations, comparison table, selected configuration, confidence, and remaining `UNVERIFIED` claims.

## Tool Requirements & Degradation

- Require artifact/config inspection, hardware and runtime inventory, memory telemetry, a repeatable load/benchmark runner, and a workload quality check.
- For current format, kernel, runtime, hardware, and feature support, see skill ai-research. Do not infer compatibility from a format name.
- If runtime or hardware inspection is unavailable, provide ranges and formulas labeled `ESTIMATE`; do not state that the model fits.
- If benchmarking is unavailable, return an experiment plan and conditional ranking only. Do not convert published benchmarks into local measurements.
- If quality evaluation is unavailable, do not approve quantization or decoding changes for production; label the quality effect `UNVERIFIED`.

## Failure Modes

- Calculating only weight memory and omitting KV cache, concurrency, workspaces, overhead, fragmentation, or margin.
- Assuming GGUF, AWQ, GPTQ, and FP8 are interchangeable or supported by every runtime and accelerator.
- Reporting estimates as observed measurements or promising universal latency gains.
- Comparing benchmarks with mismatched workload, version, hardware, precision, or quality gates.
- Optimizing average latency while ignoring time to first token, tail latency, queueing, memory, or output quality.
- Choosing a different model, serving engine, or deployment topology to make the tuning result look successful.
