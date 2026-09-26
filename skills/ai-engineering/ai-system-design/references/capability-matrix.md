# Capability Matrix

Copy every row into the project design. Set exactly one status:

- `required` — include an owning DAG node and deliverable;
- `unnecessary — <rationale>` — explain why omission is safe for this project; or
- `unresolved — <question>` — ask the decision-changing question and block dependent decisions.

| Area | Sub-capability to assess | Status | Evidence, rationale, or question | Responsible skill |
|---|---|---|---|---|
| 1. Discovery and framing | Current facts, primary-source verification, unfamiliar-domain actors, data sources, constraints, ToS, licenses, and risks |  |  | `ai-research` |
| 1. Discovery and framing | Requirements, system boundary, option comparison, architecture, ordered plan, and acceptance criteria |  |  | `ai-system-design` |
| 2. Models and adaptation | Concrete model/Hugging Face candidate, model card, parameters, context, license, gated access, hardware, and budget fit |  |  | `model-selection-hf` |
| 2. Models and adaptation | Multimodal and language capability selection |  |  | `model-selection-hf`, `ai-research` |
| 2. Models and adaptation | Training-data sourcing, rights/provenance, cleaning, quality filtering, dedup, leakage-safe splits, and tiered synthetic generation |  |  | `training-data-engineering` |
| 2. Models and adaptation | Training execution on a curated handoff: method selection, configs, pilots, checkpoints, diagnosis, and evaluation handoff |  |  | `training-peft` |
| 2. Models and adaptation | SFT, PEFT, LoRA, and QLoRA configuration |  |  | `training-peft` |
| 2. Models and adaptation | MoE, distillation, and RLHF/RLAIF orientation or research |  |  | `training-peft`, `ai-research` |
| 2. Models and adaptation | Synthetic-data production, audit gates, and generation model routing |  |  | `training-data-engineering`, `ai-research` |
| 3. Inference and serving | GPU/VRAM sizing, weights, KV cache, runtime overhead, batching, and quantization |  |  | `inference-optimization` |
| 3. Inference and serving | Speculative decoding, attention optimization, latency, throughput, memory, and quality trade-offs |  |  | `inference-optimization` |
| 3. Inference and serving | vLLM or alternative engine, endpoint topology, scale, backpressure, and serving SLO |  |  | `model-serving` |
| 3. Inference and serving | Multi-model/provider routing, serving cache, retry, fallback, and operational resilience |  |  | `model-serving`, `production-ops` |
| 4. Knowledge and context | Ingestion, chunking, embeddings, vector store, hybrid retrieval, reranking, access filtering, and RAG evaluation |  |  | `rag-engineering` |
| 4. Knowledge and context | Prompt/context structure, context budget, memory, progressive disclosure, and compaction |  |  | `context-engineering` |
| 5. Evaluation and verification | Metrics, evaluation data and slices, LLM judging, output regression, and comparison significance |  |  | `eval-harness` |
| 5. Evaluation and verification | Current paper or model claim verification and workload-relevant interpretation |  |  | `ai-research`, `eval-harness` |
| 5. Evaluation and verification | End-to-end execution, acceptance evidence, edge cases, and unverified paths |  |  | `implementation-verification` |
| 6. Agent capabilities | Agent design, tool calling, MCP, skills, plugins, subagents, hooks, harness integration, and tool security |  |  | `tool-and-mcp-design` |
| 7. Production readiness | Monitoring, drift, observability, incidents, cost, security, resilience, rollout, and rollback |  |  | `production-ops` |
| 8. Automation and data movement | Schedules, triggers, data-source ingestion pipelines, approvals, retries, idempotency, and unattended guardrails |  |  | `ai-automation` |

After assigning statuses, verify that every `required` row has an owner, input contract, output artifact, acceptance criterion, and evaluation or verification path in the DAG.
