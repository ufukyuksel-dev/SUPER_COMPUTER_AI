---
name: ai-system-design
description: "Use when scoping, architecting, or planning an AI system or feature — requirements intake, capability gap-scan, option comparison, architecture decisions, plan and acceptance-criteria production. Top-level orchestrator for project-scale requests: composes multiple specialist skills as needed. Runs the core loop: analyze, resolve unknowns via skill ai-research, gap-scan the capability matrix, compare options, design, define eval, then verify via skill implementation-verification when available, else an inline verification checklist. Do NOT use for executing research itself or for picking a specific model (see skill model-selection-hf)."
---

# AI System Design

## Boundaries

- Orchestrate project-level scoping and design; assign one specialist skill to each concern and use as many concerns as the project requires.
- Do not perform current-fact research. For bounded fact questions, see skill ai-research and integrate its cited findings.
- Do not choose a concrete model. After recording task, modality, license, hardware, and budget constraints, see skill model-selection-hf.
- Produce decisions, architecture, an ordered implementation plan, acceptance criteria, and an evaluation plan. Do not implement unless the human separately asks for implementation.
- Ask narrowly about decision-changing ambiguity. After at most two focused ambiguity passes, stop and ask the human rather than inventing business meaning, capacity, or trust boundaries.

## Decision Workflow

1. **Analyze.** Complete [the intake checklist](references/intake-checklist.md). Emit an intake brief containing intended outcome, knowns, constraints, assumptions, unknowns, and narrow questions.
2. **Resolve unknowns.** Separate requirements ambiguity from current-fact gaps. Ask the human about the former; for the latter, see skill ai-research and send bounded tasks. Record sources and mark unresolved facts `UNVERIFIED`.
3. **Gap-scan.** Copy [the capability matrix](references/capability-matrix.md). Mark every row `required`, `unnecessary — <rationale>`, or `unresolved — <question>`. Do not omit a row because it looks unrelated.
4. **Compare.** For each decision, enumerate viable options and evaluate evidence, constraints, trade-offs, risks, cost, reversibility, and rejected alternatives. Use [the architecture decision template](references/architecture-decision-template.md).
5. **Design.** Define components, interfaces, data flow, trust and egress boundaries, failure behavior, ownership, and specialist decisions. Distinguish verified facts, estimates, assumptions, and decisions.
6. **Plan and evaluate.** Produce dependency-ordered implementation slices, measurable acceptance criteria, and an evaluation plan. For metric and dataset design, see skill eval-harness. Include rollback or stop gates for risky changes.
7. **Verify.** After implementation exists, see skill implementation-verification and invoke it with the acceptance criteria, evaluation gates, deliverable, environment, and known risks. Integrate its direct evidence and preserve every `FAIL` or `UNVERIFIED` result.

## Composition DAG

1. Create one node per concern, not one node per project. Assign the most specific owning skill from the capability matrix.
2. Add edges for real information dependencies. Typical prerequisites include research before evidence-dependent choices, model selection before hardware tuning, architecture before implementation, and implementation before verification.
3. Run independent nodes in parallel, such as data/privacy analysis, model research, RAG design, serving analysis, and evaluation design when their inputs are already known.
4. Keep specialist content in its owner. Pass compact contracts between nodes: inputs, assumptions, decisions, evidence, outputs, and unresolved items.
5. Reconcile conflicts explicitly and integrate accepted outputs into one architecture and ordered plan. Do not paste disconnected specialist reports.

Use the following ownership boundaries:

- For current facts and unfamiliar-domain mapping, see skill ai-research.
- For concrete model and Hugging Face decisions, see skill model-selection-hf.
- For VRAM, quantization, KV-cache, batching, and decode tuning, see skill inference-optimization.
- For engine, serving topology, scaling, and serving-time routing, see skill model-serving.
- For dataset and adaptation lifecycle, see skill training-peft.
- For metrics, eval data, judging, and comparison significance, see skill eval-harness.
- For retrieval, chunking, embeddings, stores, reranking, and RAG evaluation, see skill rag-engineering.
- For prompts, context budgets, memory, and compaction, see skill context-engineering.
- For tools, MCP, plugins, skills, subagents, hooks, and harness integration, see skill tool-and-mcp-design.
- For deployed monitoring, drift, incidents, security posture, cost controls, and rollback, see skill production-ops.
- For schedules, triggers, ingestion pipelines, approvals, and unattended guardrails, see skill ai-automation.
- For end-to-end completion evidence, see skill implementation-verification.

## Required Output

Return one integrated package:

1. intake brief and unresolved questions;
2. completed capability matrix;
3. concern-to-skill DAG with parallel and sequential edges;
4. option and architecture decision records with cited evidence;
5. target architecture, interfaces, data/trust boundaries, and failure behavior;
6. dependency-ordered implementation plan with owners and gates;
7. measurable acceptance criteria and evaluation plan;
8. verification mapping or `UNVERIFIED` labels for anything not exercised.

Put evidence before claims. Never turn an unsupported routing signal, remembered current fact, estimate, or unrun test into a pass.

## Tool Requirements & Degradation

- Require repository inspection tools for existing-system constraints and a planning surface for maintaining the DAG and evidence matrix.
- For current facts, see skill ai-research and use its browsing protocol only; redact confidential inputs before any external call.
- If a specialist skill or tool is unavailable, keep its concern as an explicit DAG node, record required inputs and outputs, and mark its decision or verification `UNVERIFIED`. Do not silently absorb specialist work or weaken its acceptance gate.
- If authoritative requirements or evidence remain unavailable after the ambiguity limit, pause that decision and ask the human one narrow question. Continue only independent, reversible planning work.
- If implementation cannot be executed, do not claim verification; provide the exact commands or probes still required.

## Failure Modes

- Treating one skill as sufficient for a multi-concern project.
- Serializing every concern without a dependency reason or parallelizing nodes before their inputs exist.
- Skipping matrix rows, especially security, cost, evaluation, operations, and automation.
- Presenting traffic, data sensitivity, budget, provider behavior, or trust boundaries as known without evidence.
- Recommending an option without alternatives, trade-offs, rejected choices, and measurable criteria.
- Duplicating specialist guidance instead of defining and integrating its decision contract.
- Implementing during a planning request or declaring completion from a plan, diff, or narrow test.
