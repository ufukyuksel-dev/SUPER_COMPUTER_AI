# RAG Failure Modes

Classify the failing stage before changing the system. Use a fixed query/corpus slice and alter one hypothesis at a time.

| Stage | Symptom | Probe | Corrective decision |
|---|---|---|---|
| Ingestion | Missing or malformed content | Compare source inventory, parse output, quarantine, and index manifest | Fix parser/coverage and reindex with versioned lineage. |
| Versioning | Stale or duplicate evidence wins | Trace source IDs, hashes, effective dates, supersession, delete propagation | Define canonical version and freshness filters; remove stale copies. |
| Authorization | Unauthorized chunks appear | Test cross-role/tenant canaries before generation and inspect filter plan | Enforce scope in retrieval and fetch; fail closed. |
| Chunking | Relevant document found but answer span is split or buried | Measure answer-bearing chunk rate across structural chunk variants | Adjust structural boundaries, overlap, parent-child retrieval, or table/code handling. |
| Embedding/query | Semantically related but answer-irrelevant chunks rank high | Compare lexical, dense, hybrid, query variants, and per-slice retrieval metrics | Change representation/query only when slice evidence improves. |
| Metadata filter | Relevant chunks disappear or wrong versions pass | Inspect normalized metadata, filter construction, null/default behavior | Fix schema and pre-retrieval filter semantics. |
| Retrieval depth | Answer exists just below cutoff or noise dominates | Plot recall/precision and latency over k by slice | Set k from the quality/latency gate, not a default. |
| Reranking | Good candidates are demoted or latency grows without lift | Compare pre/post ranks, answer-bearing rate, and latency/cost | Recalibrate, change reranker, or remove it when lift is absent. |
| Context assembly | Retrieved evidence is dropped, reordered, or loses provenance | Inspect final context against authorized retrieved IDs | Preserve source/version anchors, budget deterministically, and detect truncation. |
| Generation | Evidence is present but answer is unsupported | Score grounding, citation entailment, abstention, and instruction injection cases | Tighten evidence contract or generation behavior after retrieval is proven. |
| Egress/logging | Confidential content crosses an unapproved boundary | Trace embedding/rerank/generation/log destinations and retention | Contain locally, redact, or obtain explicit approval; do not mask the violation. |

## Minimum diagnostic evidence

- query ID and slice;
- caller authorization scope;
- corpus/index version;
- retrieved source IDs, ranks, scores, filters, and versions;
- reranked order and timing;
- context source IDs actually sent to generation;
- answer citations, abstention result, and stage metrics;
- exact configuration and command or trace locator.

When the production store is unavailable, use redacted historical traces or a small controlled local corpus. State which stages remain `UNVERIFIED`; never infer production index size, distribution, filtering, or performance.
