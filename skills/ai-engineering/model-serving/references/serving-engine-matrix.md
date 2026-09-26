# Serving Engine Matrix

Do not prefill current feature claims from memory. Complete the matrix with official, version-matched citations and local probes for the target model and environment.

## Candidate evidence

| Candidate | Exact version/service tier | Model, modality, artifact | Hardware/runtime | Protocol and streaming | Batching/parallelism/scale | Tools/structured output/features | Isolation/security/egress | Observability | License/cost | Local probe | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vLLM |  |  |  |  |  |  |  |  |  |  | `verified / unsupported / UNVERIFIED` |
| TGI |  |  |  |  |  |  |  |  |  |  | `verified / unsupported / UNVERIFIED` |
| llama.cpp server |  |  |  |  |  |  |  |  |  |  | `verified / unsupported / UNVERIFIED` |
| SGLang |  |  |  |  |  |  |  |  |  |  | `verified / unsupported / UNVERIFIED` |
| Managed endpoint `<name>` |  |  |  |  |  |  |  |  |  |  | `verified / unsupported / UNVERIFIED` |

For each non-empty fact, cite `[Title](URL) — accessed YYYY-MM-DD`, capture the exact deployed version, and distinguish documentation from observed behavior.

## Topology comparison

| Pattern | Use only when | Validate | Main failure boundary |
|---|---|---|---|
| Single instance | One measured instance satisfies the load and availability envelope | Sustained/burst load, restart, memory headroom | Instance or accelerator loss |
| Replicated service | Requests can be independently scheduled and replicas meet model-loading constraints | Load balancing, cold start, cancellation, autoscale lag | Shared queue/control plane |
| Intra-model parallel placement | The model/runtime requires or benefits from multiple devices under measured communication cost | Placement, interconnect, collective failure, tail latency | Any participating device/link |
| Multi-model pool | Isolation, loading, eviction, and routing policies are explicit | Noisy neighbor, cold load, memory pressure, model identity | Pool or routing policy |
| Regional/provider endpoints | Residency, latency, resilience, or capacity justify distribution | Data policy, health signals, failover, consistency | Region/provider and control plane |

## Decision record

Record hard exclusions, selected candidate and topology, evidence, configuration, capacity envelope, SLO, overload policy, cache/retry/fallback policy, security boundary, conformance/load results, cost assumptions, residual risks, and rollback trigger.
