---
name: model-selection-hf
description: "Use when choosing or comparing concrete models, evaluating a Hugging Face model card, checking licenses or gated access, or mapping task+hardware+budget to candidates — including multimodal model selection. Verifies params/license/context via skill ai-research, never from memory. Do NOT use for serving-stack choice or GPU tuning (planned skills model-serving and inference-optimization; when unavailable, state the boundary and hand findings to ai-system-design)."
---

# Model Selection for Hugging Face

## Boundaries

- Own concrete model discovery, model-card evaluation, constraint filtering, shortlisting, and conditional recommendation, including multimodal candidates.
- For changing metadata, see skill ai-research. Never state parameters, context, license, access, release, benchmark, or runtime support from memory.
- For VRAM calculation, quantization, and kernel tuning, see skill inference-optimization.
- For serving engine and topology selection, see skill model-serving.
- Return model requirements and verified candidate facts to the orchestrator; see skill ai-system-design. Do not broaden selection into system architecture.
- Treat license interpretation as evidence collection and risk identification, not legal advice.

## Decision Workflow

1. Capture hard and soft constraints: task, output contract, modality, languages, quality floor, context, latency, throughput, hardware, deployment boundary, privacy, budget, license/commercial-use needs, and gated-access tolerance.
2. Convert hard constraints into explicit exclusion tests before naming a preferred candidate. Ask one narrow question when a missing constraint could reverse the recommendation.
3. To build a candidate set from current primary sources, see skill ai-research. Do not rely on remembered leaderboards or model metadata.
4. For each candidate, complete [the model-card checklist](references/model-card-checklist.md). Pin the exact model ID and revision; verify parameters, modality, context, license artifacts, access gate, usage restrictions, and evidence relevant to the requested workload.
5. Record every field as `verified`, `conflicted`, or `unverified` with a citation. When model-card metadata, repository files, and terms disagree, report the conflict and do not recommend commercial use until the governing license uncertainty is resolved.
6. Exclude candidates that fail a hard constraint. Record the exact reason; do not hide rejected candidates that appeared otherwise strong.
7. Compare the surviving shortlist on task evidence, language/modality fit, operational feasibility, cost envelope, risks, and evidence quality. For precise hardware-fit questions, see skill inference-optimization instead of guessing fit.
8. Recommend conditionally: name the preferred candidate, evidence-backed reasons, trade-offs, confidence, validation tasks, and conditions that would change the decision.

## Required Output

Return:

- a constraint table with hard versus soft requirements;
- a candidate evidence table with exact model/revision, citations, and verification status;
- a shortlist and rejected-candidate ledger;
- license and gated-access status, including conflicts and required approvals;
- a conditional recommendation and a workload-matched validation plan;
- explicit handoffs for VRAM tuning, serving, evaluation, or architecture concerns.

## Tool Requirements & Degradation

- Require current access to official Hugging Face model cards and repository artifacts, or equivalent official upstream sources, via browsing/model-hub tools; for current-fact verification, see skill ai-research.
- Require local hardware/runtime inspection only to record constraints; do not convert unmeasured compatibility into verified fit.
- If Hugging Face or primary artifacts are unavailable, label **every** candidate and metadata field `UNVERIFIED`, keep the recommendation conditional, state the access limitation, and create a concrete follow-up task naming the exact model IDs, revisions, files, and claims to verify.
- If only cached or secondary metadata is available, use it for provisional discovery only. Never present it as verified license, parameter, context, access, or modality evidence.
- If a license or access conflict cannot be resolved, stop that candidate's recommendation rather than inventing legal certainty.

## Failure Modes

- Selecting before task, hardware, license, budget, modality, or language constraints are known.
- Fabricating parameters, context length, license, gated status, benchmark position, or commercial suitability.
- Treating a model-card tag as sufficient when license files or governing terms conflict.
- Ignoring rejected candidates, access approval, data egress, or workload mismatch.
- Turning parameter count into a VRAM-fit claim without weights, KV cache, runtime overhead, and concurrency analysis.
- Choosing a serving engine or topology inside the model recommendation.
- Producing an unconditional winner when sources are inaccessible or evidence is conflicted.
