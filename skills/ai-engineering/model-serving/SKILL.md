---
name: model-serving
description: "Use when selecting or configuring a serving stack — vLLM, TGI, llama.cpp server, SGLang, managed endpoints — including topology, scaling, multi-model/provider routing, cache/retry/fallback at serving time, and serving-level SLOs. Do NOT use for on-device quantization/VRAM math (see skill inference-optimization) or post-deploy operations (see skill production-ops)."
---

# Model Serving

## Boundaries

- Own serving engine, API/runtime compatibility, endpoint topology, scaling, admission control, serving-time routing, cache, retry, fallback, and serving SLO decisions.
- For concrete model choice, see skill model-selection-hf; for memory and quantization calculations, see skill inference-optimization.
- For deployed monitoring, incident response, drift, cost governance, rollout, and rollback operations, see skill production-ops; provide serving signals and safe controls as inputs.
- Treat engine features and version compatibility as current facts. For source verification, see skill ai-research; also run a local rollback-safe probe.

## Decision Workflow

1. Bound the workload: model/artifact and modality, hardware and region, arrival rate, concurrency, burst shape, prompt/output distribution, streaming, payload, tenant isolation, availability, security, and budget.
2. Define serving objectives before choosing an engine: time to first token, inter-token latency, end-to-end p50/p95/p99, throughput, availability, error rate, freshness, and recovery behavior.
3. Read [the serving engine matrix](references/serving-engine-matrix.md). For current support of the exact model, artifact, hardware, protocol, features, and deployed version, see skill ai-research; separate documented support from a successful local probe.
4. Compare engine and managed-endpoint candidates against hard constraints, operational complexity, scaling behavior, observability, portability, and cost. Record rejected candidates and evidence gaps.
5. Compare topology options conditionally: single instance, replicated service, tensor/pipeline parallel placement, multi-model pools, or regional endpoints. Do not select capacity before workload-matched load tests.
6. Define overload behavior: bounded queues, concurrency/admission limits, backpressure, timeouts, shedding priority, cancellation, and safe degraded responses.
7. Design serving-time policy explicitly:
   - **routing:** filter providers/models by capability, tenant, region, privacy, health, and budget before scoring;
   - **cache:** define semantic versus exact behavior, freshness, eviction, tenant/auth isolation, and a key containing every response-affecting input;
   - **retry:** classify transient failures, require idempotency, use a bounded retry budget within the request deadline, add jitter, and prevent retry amplification;
   - **fallback:** require compatible output, security, data-handling, and quality contracts; bound hops and make material degradation visible.
8. Validate with conformance and load probes, failure injection, version-pinned configuration, and rollback criteria. Recommend only what the evidence supports.

## Serving SLO Template

Record:

- workload and measurement window;
- time-to-first-token, inter-token, and end-to-end percentile targets;
- sustained and burst throughput/concurrency envelopes;
- availability and error-budget target with excluded versus included failures;
- queue, timeout, retry, fallback, and shedding budgets;
- response correctness/quality guardrail and cache-freshness target;
- measurement location, telemetry source, alert boundary, and rollback trigger.

Express every SLO as conditional on a named workload and validated capacity envelope. Never promise an SLO from an assumed traffic profile.

## Tool Requirements & Degradation

- Require official engine/provider documentation, deployment/version inventory, a conformance probe, load generator, request/queue/accelerator telemetry, and failure-injection or controlled fault tools.
- For recent features and compatibility, see skill ai-research. Verify the deployed version locally before relying on documented support.
- If traffic is unknown, ask for or bound arrival rate, concurrency, payload, and latency objectives; provide conditional topology options and a load-test plan, not invented capacity.
- If deployment access is unavailable, label local compatibility, capacity, SLO, and failure behavior `UNVERIFIED`; provide rollback-safe probe commands or procedures.
- If a provider is unavailable, do not simulate its success. Test the remaining deterministic policy and mark the provider-dependent path `UNVERIFIED`.

## Failure Modes

- Choosing an engine from remembered release notes, popularity, or a feature absent from the deployed version.
- Conflating documented compatibility with successful local model loading and API behavior.
- Inventing traffic, capacity, or latency and then promising an SLO.
- Omitting admission control, cancellation, overload, backpressure, or bounded failure behavior.
- Retrying non-idempotent requests, exceeding the request deadline, or creating retry storms.
- Using cache keys that omit model/version, prompt/system/tool state, generation settings, tenant, authorization, or freshness boundaries.
- Silently falling back to a weaker, noncompliant, differently licensed, or differently shaped response.
- Turning serving configuration into post-deploy incident or cost-management design.
