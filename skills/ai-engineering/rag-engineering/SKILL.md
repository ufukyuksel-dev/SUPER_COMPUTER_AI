---
name: rag-engineering
description: "Use when building or debugging retrieval-augmented generation — chunking, embedding choice, vector store, hybrid search, reranking, RAG-specific evaluation and failure modes. Do NOT use for general context budgeting/prompt structure (planned skill context-engineering; when unavailable, state the boundary)."
---

# RAG Engineering

## Boundaries

- Own corpus ingestion, chunking, embedding choice, index/store design, lexical/dense/hybrid retrieval, metadata filters, reranking, provenance, and RAG-specific evaluation and diagnosis.
- Enforce authorization and tenant/document visibility before retrieval and again before content fetch. Never use prompt instructions or post-generation filtering as access control.
- For general prompt layout, conversation memory, context budgeting, and compaction, see skill context-engineering.
- For current embedding, vector-store, reranker, license, API, and data-egress facts, see skill ai-research. Never select a changing external capability from memory.
- Keep base-model selection separate; RAG need does not determine the concrete generation model.

## Decision Workflow

1. Define the question types, corpus, source authority, languages/modalities, confidentiality, tenant/role model, freshness/versioning, citation requirement, latency/cost envelope, and allowed data egress.
2. Build ingestion with source identity, parser/version, content hash, permissions, timestamps, document version, lineage, deletion propagation, deduplication, and failure quarantine.
3. Define chunking hypotheses from document structure and question granularity. Preserve headings, page/section anchors, parent-child relationships, tables/code where relevant, and stable provenance.
4. Select embeddings from workload evidence: language/modality, domain, length, retrieval metric, privacy/egress, license, runtime, and cost. For current metadata, see skill ai-research.
5. Select the store/index by required filters, authorization isolation, update/delete consistency, hybrid support, scale, backup, audit, and egress constraints. Do not treat a vector-store brand as an architecture answer.
6. Apply query normalization or transformation only with measurable benefit. Retrieve through authorization-scoped dense, lexical, or hybrid paths; apply metadata/version filters before candidates can cross the trust boundary.
7. Rerank only authorized candidates. Define top-k, score/abstention thresholds, diversity, freshness, and no-answer behavior from evaluation rather than intuition.
8. Assemble generation context with stable source IDs and versioned citations. Require the answer to distinguish supported statements, uncertainty, and no-evidence cases.
9. Evaluate separate stages and slices:
   - ingestion coverage, freshness, deletion, version, and ACL correctness;
   - retrieval recall@k, precision@k, MRR/nDCG where appropriate, answer-bearing chunk rate, and filter leakage;
   - reranking lift versus latency/cost;
   - grounded answer quality, citation correctness/completeness, hallucination/abstention, and unauthorized disclosure.
10. Diagnose by classifying the failure as ingestion, chunking, embedding/query, filter, retrieval, reranking, context assembly, or generation. Change one hypothesis at a time and retain slice-level evidence.

Read [the RAG failure-mode catalog](references/rag-failure-modes.md) before diagnosing or approving the design.

## Required Output

Return the data/egress and authorization boundary, ingestion and versioning contract, chunk/embedding/store decision records, retrieval/reranking pipeline, provenance/citation contract, RAG evaluation dataset and gates, diagnostic evidence, rejected alternatives, and all `UNVERIFIED` production-path claims.

## Tool Requirements & Degradation

- Require corpus/parser inspection, permission metadata, index/store access, retrieval traces, query/result logging with redaction, a controlled evaluation corpus, and an end-to-end runner.
- For current service/model/store facts and licenses, see skill ai-research. Keep confidential text out of external tools unless egress is explicitly allowed.
- If vector-store access is unavailable, state the boundary; use existing retrieval logs or a small local controlled corpus to test deterministic hypotheses. Label index statistics, production filtering, scale, and retrieval behavior `UNVERIFIED`.
- If authorization metadata is unavailable, stop the confidential retrieval path. Do not substitute prompt instructions or test with cross-tenant data.
- If corpus content cannot leave its boundary, select local tools or work on redacted/synthetic structure; do not weaken the egress requirement without human approval.
- If no labeled evaluation queries exist, create a bounded annotation task and run only smoke diagnostics; do not claim RAG quality.

## Failure Modes

- Filtering authorization after retrieval or generation, or omitting tenant/role scope from cache and index operations.
- Treating duplicate or stale document versions as harmless and citing an obsolete copy.
- Choosing chunk size, top-k, embedding, or reranker by convention without workload evidence.
- Optimizing semantic similarity while retrieved chunks remain answer-irrelevant.
- Debugging every failure by rewriting the prompt or changing the base model first.
- Evaluating only final answer fluency while ignoring retrieval, citation, abstention, freshness, and leakage.
- Inventing production index statistics or claiming the store path was tested while access was unavailable.
- Sending confidential chunks to an external embedding, reranking, generation, or logging service outside the allowed egress boundary.
