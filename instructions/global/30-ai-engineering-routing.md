<!-- bundles: ai-engineering -->
## AI engineering skills

- The AI-engineering skills live in `skills/ai-engineering/` of SUPER_COMPUTER_AI and are installed globally by `scripts/install.py`.
- For project-scale AI requests, start with `ai-system-design`; compose every relevant specialist skill as a DAG instead of forcing one skill to own the whole project.
- Use `ai-research` for current facts or unfamiliar domains, and use `implementation-verification` before reporting an implementation complete.
- Business examples such as social-media analysis or finance are scenarios, not fixed domain agents. Map the requested domain and determine the necessary AI capabilities for that specific job.
- Skills supply reusable knowledge and workflows; MCP/tools, credentials, schedulers, and runtime services still require actual platform configuration and executable verification.

### Skill routing

One skill per concern; if two match, the more specific first.

| Skill | Route when the concern is |
|---|---|
| `ai-system-design` | project scoping, architecture, capability gap-scan, planning, or acceptance criteria |
| `ai-research` | current facts, primary-source verification, or unfamiliar-domain mapping |
| `model-selection-hf` | concrete model or Hugging Face card, license, access, modality, hardware, or budget fit |
| `inference-optimization` | VRAM sizing, quantization, KV cache, batching, decoding, attention, or latency/throughput tuning |
| `model-serving` | serving engine, topology, scale, serving-time routing/cache/retry/fallback, or serving SLO |
| `training-data-engineering` | training-data sourcing, provenance, cleaning, dedup, leakage-safe splits, or tiered synthetic data |
| `training-peft` | training on a curated dataset: method selection, SFT, LoRA/QLoRA, PEFT, configs, checkpoints, or preference tuning |
| `eval-harness` | metrics, evaluation data, LLM judging, output regression, or comparison significance |
| `rag-engineering` | chunking, embeddings, retrieval, vector stores, reranking, or RAG-specific evaluation |
| `implementation-verification` | an implementation is claimed complete and must be exercised end to end |
| `context-engineering` | prompt/context structure, budgets, memory, disclosure, or compaction |
| `tool-and-mcp-design` | tool schemas, MCP, skills/plugins/subagents/hooks, harness integration, or tool security |
| `production-ops` | deployed monitoring, drift, incidents, cost, security, resilience, rollout, or rollback |
| `ai-automation` | schedules, autonomous jobs, ingestion pipelines, triggers, approvals, or unattended guardrails |

