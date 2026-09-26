# Quantization Decision Tree

## 1. Pin inputs

Record the exact model/revision, architecture, source precision, artifact format, hardware, accelerator capabilities, runtime and version, context/concurrency distribution, quality floor, and memory target.

## 2. Gate compatibility before quality or speed

For every candidate, verify current support from official runtime, hardware, and model documentation.

| Candidate family | Compatibility questions to verify | Decision risk |
|---|---|---|
| GGUF | Does the selected runtime support the model architecture, chosen quantization type, accelerator offload, and required context/features? | Do not infer GPU behavior or quality from the container name alone. |
| AWQ | Does the runtime provide kernels for the exact architecture, bit/group configuration, dtype, and accelerator? | Conversion success does not prove efficient execution. |
| GPTQ | Does the runtime support the artifact dialect, architecture, kernel path, and requested batching/context behavior? | Similar labels can hide incompatible layouts or kernels. |
| FP8 | Does the accelerator and runtime support the required FP8 path for the exact operations and model? | Storage format, weight-only use, and accelerated compute are different claims. |

Mark each combination `supported`, `unsupported`, or `UNVERIFIED` with a citation and local probe. Remove unsupported combinations; keep unverified ones out of the recommendation.

## 3. Build the full memory envelope

- Derive weight memory from the actual artifact when possible; otherwise show `parameters × effective bytes` plus scales, zero-points, grouping, and metadata.
- Derive KV-cache memory from the exact layer count, KV-head structure, head dimension, cache dtype, tokens, and concurrent sequences used by the runtime.
- Add activations, temporary buffers, attention workspaces, graphs, runtime/process overhead, allocator fragmentation, and safety margin.
- Report low/expected/high cases and the assumption that drives each range.

## 4. Select candidates for measurement

- Reject any candidate that misses the hard memory limit with margin.
- Reject any candidate that cannot satisfy required features or portability.
- Keep multiple bit/format candidates when their quality effect is unknown.
- Establish an unquantized or less-quantized baseline when the hardware permits; otherwise document the best reproducible reference.

## 5. Measure under the target workload

Use identical prompts, output limits, sampling, concurrency, warmup, repeats, versions, and quality data. Measure memory, time to first token, decode rate, end-to-end and tail latency, throughput, failures, and task quality. Store raw results.

## 6. Decide

Choose the least risky configuration that passes all declared gates. Record conversion provenance, artifact hash, runtime flags, measured deltas, confidence, and rollback trigger. Report `inconclusive` when differences are within noise or quality evidence is insufficient.
