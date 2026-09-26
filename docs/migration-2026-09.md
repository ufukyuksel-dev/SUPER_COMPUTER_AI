# Migration record — 2026-09 consolidation

Plan: `plan-super-computer-ai-consolidation-v7.md` (kept outside the repo in the pipeline `output/`). Copies were made
**only** from the allowlists below; every allowlisted file is tracked in its source repository (`git ls-files`).
History was not imported (plan §6 Faz 4). Source repositories stay untouched until the Phase 4 archive.

Public source map (machine-readable): `scripts/migration/source_map.json`.

## Phase 1A — skills, roles and tooling

| Source | Allowlisted | Identical copies | Intentionally modified | Excluded |
|---|---|---|---|---|
| AI_Developer | 173 | 159 | 14 | 63 |
| AI_SKILLS | 9 | 7 | 2 | 9 |
| Hand-copied skills | 2 (`jev-browser`, `mobile-ui-review`) | — | 2 | — |
| GoogleAds | 1 derived skill (`google-ads-management`) | — | new file | everything else (Phase 2) |

### Hand-copied skills

- `mobile-ui-review` ← `~/.claude/skills/Mobile_UI_Review/SKILL.md` (26.5 KB, 2026-03-20). The two other copies
  (`~/.codex/skills/Mobile_UI_Review`, 11.4 KB, and `ADB_MCP_SERVER/DOCS/skill-ui-review.md`, 11.2 KB) are older subsets:
  every heading they contain exists in the Claude copy, which adds prerequisites, crash detection/recovery, logcat and a
  fast-interaction loop. Changes: kebab-case name and a descriptive `description` (the Codex copy's wording, extended).
- `jev-browser` ← `~/.claude/skills/jev-browser/SKILL.md`. Changes: the code path and the `.env` path were replaced with
  location-independent wording. Platform stays `claude` only (it was never installed for Codex).

### Derived skill

- `google-ads-management` — the generic workflow from `GoogleAds/docs/ads-instructions.md` (Turkish, Wordfall-specific)
  rewritten in English without any account, manager, Cloud project, app-store or e-mail identifiers. The full original,
  which contains those identifiers, is staged for the private overlay (`private/instructions/projects/wordfall-ads.md`),
  never committed.

### Private overlay staging (not committed)

Installed into `~/.config/super-computer-ai/private/` in Phase 1C:
`skills/mobile-store-release/wordfall.md`, `skills/store-listing-assets/wordfall.md` (workspace paths),
`instructions/projects/wordfall-ads.md` (account identifiers).

### Excluded from AI_Developer and why

| Excluded | Reason |
|---|---|
| `.agents/skills/manifest.json` | replaced by `skills/manifest.json` (schema v2) |
| `.claude/skills/*` (14 symlinks) | in-repo links are no longer used; the installer links directly to `skills/<category>/<name>` |
| `AGENTS.md`, `CLAUDE.md`, `README.md` | content moved to `skills/ai-engineering/README.md` and `instructions/global/30-ai-engineering-routing.md` |
| `.gitignore`, `requirements-dev.txt` | superseded by root files |
| `scripts/install_global.py`, `tests/installer/*` | replaced by `scripts/install.py` (Phase 1B), which adopts its links and managed block and retires its record to `*.migrated-<ts>` |
| `scripts/new_skill.sh` | ported to `scripts/new_skill.py` (Phase 1B) for categories, bundles and both profiles |
| `templates/global-instructions.md` | merged into `instructions/global/30-ai-engineering-routing.md` |
| `tests/validator/*` (fixtures + tests) | legacy layout; replaced by builder-based `tests/skills/test_validate_skills.py` covering the same 8 failure classes plus new manifest/profile/role checks |

### Excluded from AI_SKILLS and why

| Excluded | Reason |
|---|---|
| `.idea/*`, `logs/*` | editor settings / runtime log |
| `README.md`, `scripts/install_skills.py`, `scripts/test_install_skills.py` | replaced by `scripts/install.py` (Phase 1B); its `~/.codex/skills` links are removed in favour of `~/.agents/skills` |

### Vendored third-party code

- `third_party/openai-skill-creator/` — unmodified Apache-2.0 skill-creator scripts from the Codex-bundled system skill,
  used for Layer 0 validation everywhere (local, pre-commit, CI). Provenance and checksums: its README / `SHA256SUMS`.

### Intentionally modified files

| File | Change |
|---|---|
| `skills/ai-engineering/training-data-engineering/SKILL.md` | collector/slot paths → tools/dataset-collector (body only; description and openai.yaml hash unchanged) |
| `skills/ai-engineering/training-data-engineering/references/model-routing-contract.md` | collector/slot paths |
| `skills/ai-engineering/training-data-engineering/references/source-and-provenance.md` | collector adapter path |
| `agents/claude/dataset-curator.md` | collector/slot/output paths |
| `agents/codex/dataset-curator.toml` | collector/slot/output paths |
| `tools/dataset-collector/config/curator-model-selection.md` | role and slot executor paths |
| `tools/dataset-collector/collector/collect.py` | CLI defaults: config/sources.yaml, data/ |
| `tools/dataset-collector/collector/slots.py` | CLI default usage log: state/slot-usage.jsonl |
| `scripts/run_behavior_tests.py` | role files read from agents/codex|claude; `install_preflight()` aborts a paid run unless the installed skills/roles resolve to this checkout |
| `scripts/skills/validate_skills.py` | rewritten repo walker/manifest loader for manifest v2 + categories + strict/basic profiles; strict enforced for `ai-engineering`; skill-local link resolution; Layer 0 default `require` via vendored skill-creator; document/openai.yaml/matrix checks kept |
| `scripts/update_openai_metadata.py` | prefers the vendored skill-creator (after `$SKILL_CREATOR_HOME`) |
| `tests/behavior/results/event-taxonomy.md` | role paths |
| `tests/behavior/results/probe-claude.json` | another machine's user name/home path neutralized to /workspace/... |
| `tests/behavior/test_run_behavior_tests.py` | role paths |
| `tools/dataset-collector/tests/test_collector.py` | import path (collector package) |
| `skills/mobile/mobile-store-release/references/wordfall.md` | machine-specific paths moved to private overlay |
| `skills/mobile/store-listing-assets/references/wordfall.md` | machine-specific paths moved to private overlay |

<details><summary>Full allowlist (source → destination)</summary>

| Source repo | Source path | Destination | Status |
|---|---|---|---|
| AI_Developer | `.agents/skills/ai-automation/SKILL.md` | `skills/ai-engineering/ai-automation/SKILL.md` | identical |
| AI_Developer | `.agents/skills/ai-automation/agents/openai.yaml` | `skills/ai-engineering/ai-automation/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/ai-automation/references/automation-safety-rules.md` | `skills/ai-engineering/ai-automation/references/automation-safety-rules.md` | identical |
| AI_Developer | `.agents/skills/ai-research/SKILL.md` | `skills/ai-engineering/ai-research/SKILL.md` | identical |
| AI_Developer | `.agents/skills/ai-research/agents/openai.yaml` | `skills/ai-engineering/ai-research/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/ai-research/references/recency-checklist.md` | `skills/ai-engineering/ai-research/references/recency-checklist.md` | identical |
| AI_Developer | `.agents/skills/ai-research/references/source-hierarchy.md` | `skills/ai-engineering/ai-research/references/source-hierarchy.md` | identical |
| AI_Developer | `.agents/skills/ai-system-design/SKILL.md` | `skills/ai-engineering/ai-system-design/SKILL.md` | identical |
| AI_Developer | `.agents/skills/ai-system-design/agents/openai.yaml` | `skills/ai-engineering/ai-system-design/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/ai-system-design/references/architecture-decision-template.md` | `skills/ai-engineering/ai-system-design/references/architecture-decision-template.md` | identical |
| AI_Developer | `.agents/skills/ai-system-design/references/capability-matrix.md` | `skills/ai-engineering/ai-system-design/references/capability-matrix.md` | identical |
| AI_Developer | `.agents/skills/ai-system-design/references/intake-checklist.md` | `skills/ai-engineering/ai-system-design/references/intake-checklist.md` | identical |
| AI_Developer | `.agents/skills/context-engineering/SKILL.md` | `skills/ai-engineering/context-engineering/SKILL.md` | identical |
| AI_Developer | `.agents/skills/context-engineering/agents/openai.yaml` | `skills/ai-engineering/context-engineering/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/context-engineering/references/context-budget-guide.md` | `skills/ai-engineering/context-engineering/references/context-budget-guide.md` | identical |
| AI_Developer | `.agents/skills/eval-harness/SKILL.md` | `skills/ai-engineering/eval-harness/SKILL.md` | identical |
| AI_Developer | `.agents/skills/eval-harness/agents/openai.yaml` | `skills/ai-engineering/eval-harness/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/eval-harness/references/eval-pitfalls.md` | `skills/ai-engineering/eval-harness/references/eval-pitfalls.md` | identical |
| AI_Developer | `.agents/skills/implementation-verification/SKILL.md` | `skills/ai-engineering/implementation-verification/SKILL.md` | identical |
| AI_Developer | `.agents/skills/implementation-verification/agents/openai.yaml` | `skills/ai-engineering/implementation-verification/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/implementation-verification/references/verification-checklist.md` | `skills/ai-engineering/implementation-verification/references/verification-checklist.md` | identical |
| AI_Developer | `.agents/skills/inference-optimization/SKILL.md` | `skills/ai-engineering/inference-optimization/SKILL.md` | identical |
| AI_Developer | `.agents/skills/inference-optimization/agents/openai.yaml` | `skills/ai-engineering/inference-optimization/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/inference-optimization/references/quantization-decision-tree.md` | `skills/ai-engineering/inference-optimization/references/quantization-decision-tree.md` | identical |
| AI_Developer | `.agents/skills/model-selection-hf/SKILL.md` | `skills/ai-engineering/model-selection-hf/SKILL.md` | identical |
| AI_Developer | `.agents/skills/model-selection-hf/agents/openai.yaml` | `skills/ai-engineering/model-selection-hf/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/model-selection-hf/references/model-card-checklist.md` | `skills/ai-engineering/model-selection-hf/references/model-card-checklist.md` | identical |
| AI_Developer | `.agents/skills/model-serving/SKILL.md` | `skills/ai-engineering/model-serving/SKILL.md` | identical |
| AI_Developer | `.agents/skills/model-serving/agents/openai.yaml` | `skills/ai-engineering/model-serving/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/model-serving/references/serving-engine-matrix.md` | `skills/ai-engineering/model-serving/references/serving-engine-matrix.md` | identical |
| AI_Developer | `.agents/skills/production-ops/SKILL.md` | `skills/ai-engineering/production-ops/SKILL.md` | identical |
| AI_Developer | `.agents/skills/production-ops/agents/openai.yaml` | `skills/ai-engineering/production-ops/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/production-ops/references/ops-readiness-checklist.md` | `skills/ai-engineering/production-ops/references/ops-readiness-checklist.md` | identical |
| AI_Developer | `.agents/skills/rag-engineering/SKILL.md` | `skills/ai-engineering/rag-engineering/SKILL.md` | identical |
| AI_Developer | `.agents/skills/rag-engineering/agents/openai.yaml` | `skills/ai-engineering/rag-engineering/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/rag-engineering/references/rag-failure-modes.md` | `skills/ai-engineering/rag-engineering/references/rag-failure-modes.md` | identical |
| AI_Developer | `.agents/skills/tool-and-mcp-design/SKILL.md` | `skills/ai-engineering/tool-and-mcp-design/SKILL.md` | identical |
| AI_Developer | `.agents/skills/tool-and-mcp-design/agents/openai.yaml` | `skills/ai-engineering/tool-and-mcp-design/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/tool-and-mcp-design/references/mcp-tool-design.md` | `skills/ai-engineering/tool-and-mcp-design/references/mcp-tool-design.md` | identical |
| AI_Developer | `.agents/skills/training-data-engineering/SKILL.md` | `skills/ai-engineering/training-data-engineering/SKILL.md` | modified |
| AI_Developer | `.agents/skills/training-data-engineering/agents/openai.yaml` | `skills/ai-engineering/training-data-engineering/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/training-data-engineering/references/dataset-card-and-handoff.md` | `skills/ai-engineering/training-data-engineering/references/dataset-card-and-handoff.md` | identical |
| AI_Developer | `.agents/skills/training-data-engineering/references/model-routing-contract.md` | `skills/ai-engineering/training-data-engineering/references/model-routing-contract.md` | modified |
| AI_Developer | `.agents/skills/training-data-engineering/references/source-and-provenance.md` | `skills/ai-engineering/training-data-engineering/references/source-and-provenance.md` | modified |
| AI_Developer | `.agents/skills/training-data-engineering/references/synthetic-data-tiers.md` | `skills/ai-engineering/training-data-engineering/references/synthetic-data-tiers.md` | identical |
| AI_Developer | `.agents/skills/training-peft/SKILL.md` | `skills/ai-engineering/training-peft/SKILL.md` | identical |
| AI_Developer | `.agents/skills/training-peft/agents/openai.yaml` | `skills/ai-engineering/training-peft/agents/openai.yaml` | identical |
| AI_Developer | `.agents/skills/training-peft/references/peft-recipes.md` | `skills/ai-engineering/training-peft/references/peft-recipes.md` | identical |
| AI_Developer | `.claude/agents/architect.md` | `agents/claude/architect.md` | identical |
| AI_Developer | `.claude/agents/dataset-curator.md` | `agents/claude/dataset-curator.md` | modified |
| AI_Developer | `.claude/agents/evaluator.md` | `agents/claude/evaluator.md` | identical |
| AI_Developer | `.claude/agents/implementer.md` | `agents/claude/implementer.md` | identical |
| AI_Developer | `.claude/agents/researcher.md` | `agents/claude/researcher.md` | identical |
| AI_Developer | `.codex/agents/architect.toml` | `agents/codex/architect.toml` | identical |
| AI_Developer | `.codex/agents/dataset-curator.toml` | `agents/codex/dataset-curator.toml` | modified |
| AI_Developer | `.codex/agents/evaluator.toml` | `agents/codex/evaluator.toml` | identical |
| AI_Developer | `.codex/agents/implementer.toml` | `agents/codex/implementer.toml` | identical |
| AI_Developer | `.codex/agents/researcher.toml` | `agents/codex/researcher.toml` | identical |
| AI_Developer | `datasets/config/curator-model-selection.md` | `tools/dataset-collector/config/curator-model-selection.md` | modified |
| AI_Developer | `datasets/config/sources.yaml` | `tools/dataset-collector/config/sources.yaml` | identical |
| AI_Developer | `scripts/collector/__init__.py` | `tools/dataset-collector/collector/__init__.py` | identical |
| AI_Developer | `scripts/collector/adapters.py` | `tools/dataset-collector/collector/adapters.py` | identical |
| AI_Developer | `scripts/collector/collect.py` | `tools/dataset-collector/collector/collect.py` | modified |
| AI_Developer | `scripts/collector/config.py` | `tools/dataset-collector/collector/config.py` | identical |
| AI_Developer | `scripts/collector/dedup.py` | `tools/dataset-collector/collector/dedup.py` | identical |
| AI_Developer | `scripts/collector/ratelimit.py` | `tools/dataset-collector/collector/ratelimit.py` | identical |
| AI_Developer | `scripts/collector/run.py` | `tools/dataset-collector/collector/run.py` | identical |
| AI_Developer | `scripts/collector/slots.py` | `tools/dataset-collector/collector/slots.py` | modified |
| AI_Developer | `scripts/collector/storage.py` | `tools/dataset-collector/collector/storage.py` | identical |
| AI_Developer | `scripts/run_behavior_tests.py` | `scripts/run_behavior_tests.py` | modified |
| AI_Developer | `scripts/update_openai_metadata.py` | `scripts/update_openai_metadata.py` | identical |
| AI_Developer | `scripts/validate_skills.py` | `scripts/skills/validate_skills.py` | modified |
| AI_Developer | `tests/behavior/fixtures/ai-automation-h1.json` | `tests/behavior/fixtures/ai-automation-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-automation-h2.json` | `tests/behavior/fixtures/ai-automation-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-automation-n1.json` | `tests/behavior/fixtures/ai-automation-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-automation-n2.json` | `tests/behavior/fixtures/ai-automation-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-automation-p1.json` | `tests/behavior/fixtures/ai-automation-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-automation-p2.json` | `tests/behavior/fixtures/ai-automation-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-h1.json` | `tests/behavior/fixtures/ai-research-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-h2.json` | `tests/behavior/fixtures/ai-research-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-n1.json` | `tests/behavior/fixtures/ai-research-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-n2.json` | `tests/behavior/fixtures/ai-research-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-p1.json` | `tests/behavior/fixtures/ai-research-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-research-p2.json` | `tests/behavior/fixtures/ai-research-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-h1.json` | `tests/behavior/fixtures/ai-system-design-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-h2.json` | `tests/behavior/fixtures/ai-system-design-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-n1.json` | `tests/behavior/fixtures/ai-system-design-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-n2.json` | `tests/behavior/fixtures/ai-system-design-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-p1.json` | `tests/behavior/fixtures/ai-system-design-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/ai-system-design-p2.json` | `tests/behavior/fixtures/ai-system-design-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/composite-data-curation-training.json` | `tests/behavior/fixtures/composite-data-curation-training.json` | identical |
| AI_Developer | `tests/behavior/fixtures/composite-design-research.json` | `tests/behavior/fixtures/composite-design-research.json` | identical |
| AI_Developer | `tests/behavior/fixtures/composite-model-research.json` | `tests/behavior/fixtures/composite-model-research.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-h1.json` | `tests/behavior/fixtures/context-engineering-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-h2.json` | `tests/behavior/fixtures/context-engineering-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-n1.json` | `tests/behavior/fixtures/context-engineering-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-n2.json` | `tests/behavior/fixtures/context-engineering-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-p1.json` | `tests/behavior/fixtures/context-engineering-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/context-engineering-p2.json` | `tests/behavior/fixtures/context-engineering-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/e2e-confidential-rag.json` | `tests/behavior/fixtures/e2e-confidential-rag.json` | identical |
| AI_Developer | `tests/behavior/fixtures/e2e-oss-serving.json` | `tests/behavior/fixtures/e2e-oss-serving.json` | identical |
| AI_Developer | `tests/behavior/fixtures/e2e-social-media.json` | `tests/behavior/fixtures/e2e-social-media.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-h1.json` | `tests/behavior/fixtures/eval-harness-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-h2.json` | `tests/behavior/fixtures/eval-harness-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-n1.json` | `tests/behavior/fixtures/eval-harness-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-n2.json` | `tests/behavior/fixtures/eval-harness-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-p1.json` | `tests/behavior/fixtures/eval-harness-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/eval-harness-p2.json` | `tests/behavior/fixtures/eval-harness-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-h1.json` | `tests/behavior/fixtures/implementation-verification-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-h2.json` | `tests/behavior/fixtures/implementation-verification-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-n1.json` | `tests/behavior/fixtures/implementation-verification-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-n2.json` | `tests/behavior/fixtures/implementation-verification-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-p1.json` | `tests/behavior/fixtures/implementation-verification-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/implementation-verification-p2.json` | `tests/behavior/fixtures/implementation-verification-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-h1.json` | `tests/behavior/fixtures/inference-optimization-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-h2.json` | `tests/behavior/fixtures/inference-optimization-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-n1.json` | `tests/behavior/fixtures/inference-optimization-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-n2.json` | `tests/behavior/fixtures/inference-optimization-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-p1.json` | `tests/behavior/fixtures/inference-optimization-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/inference-optimization-p2.json` | `tests/behavior/fixtures/inference-optimization-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-h1.json` | `tests/behavior/fixtures/model-selection-hf-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-h2.json` | `tests/behavior/fixtures/model-selection-hf-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-n1.json` | `tests/behavior/fixtures/model-selection-hf-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-n2.json` | `tests/behavior/fixtures/model-selection-hf-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-p1.json` | `tests/behavior/fixtures/model-selection-hf-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-selection-hf-p2.json` | `tests/behavior/fixtures/model-selection-hf-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-h1.json` | `tests/behavior/fixtures/model-serving-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-h2.json` | `tests/behavior/fixtures/model-serving-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-n1.json` | `tests/behavior/fixtures/model-serving-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-n2.json` | `tests/behavior/fixtures/model-serving-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-p1.json` | `tests/behavior/fixtures/model-serving-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/model-serving-p2.json` | `tests/behavior/fixtures/model-serving-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-h1.json` | `tests/behavior/fixtures/production-ops-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-h2.json` | `tests/behavior/fixtures/production-ops-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-n1.json` | `tests/behavior/fixtures/production-ops-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-n2.json` | `tests/behavior/fixtures/production-ops-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-p1.json` | `tests/behavior/fixtures/production-ops-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/production-ops-p2.json` | `tests/behavior/fixtures/production-ops-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-h1.json` | `tests/behavior/fixtures/rag-engineering-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-h2.json` | `tests/behavior/fixtures/rag-engineering-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-n1.json` | `tests/behavior/fixtures/rag-engineering-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-n2.json` | `tests/behavior/fixtures/rag-engineering-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-p1.json` | `tests/behavior/fixtures/rag-engineering-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/rag-engineering-p2.json` | `tests/behavior/fixtures/rag-engineering-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/role-architect.json` | `tests/behavior/fixtures/role-architect.json` | identical |
| AI_Developer | `tests/behavior/fixtures/role-evaluator.json` | `tests/behavior/fixtures/role-evaluator.json` | identical |
| AI_Developer | `tests/behavior/fixtures/role-implementer.json` | `tests/behavior/fixtures/role-implementer.json` | identical |
| AI_Developer | `tests/behavior/fixtures/role-parity-dataset-curator.json` | `tests/behavior/fixtures/role-parity-dataset-curator.json` | identical |
| AI_Developer | `tests/behavior/fixtures/role-researcher.json` | `tests/behavior/fixtures/role-researcher.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-h1.json` | `tests/behavior/fixtures/tool-and-mcp-design-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-h2.json` | `tests/behavior/fixtures/tool-and-mcp-design-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-n1.json` | `tests/behavior/fixtures/tool-and-mcp-design-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-n2.json` | `tests/behavior/fixtures/tool-and-mcp-design-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-p1.json` | `tests/behavior/fixtures/tool-and-mcp-design-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/tool-and-mcp-design-p2.json` | `tests/behavior/fixtures/tool-and-mcp-design-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-h1.json` | `tests/behavior/fixtures/training-data-engineering-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-m1.json` | `tests/behavior/fixtures/training-data-engineering-m1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-n1.json` | `tests/behavior/fixtures/training-data-engineering-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-n2.json` | `tests/behavior/fixtures/training-data-engineering-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-p1.json` | `tests/behavior/fixtures/training-data-engineering-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-p2.json` | `tests/behavior/fixtures/training-data-engineering-p2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-data-engineering-p3.json` | `tests/behavior/fixtures/training-data-engineering-p3.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-h1.json` | `tests/behavior/fixtures/training-peft-h1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-h2.json` | `tests/behavior/fixtures/training-peft-h2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-n1.json` | `tests/behavior/fixtures/training-peft-n1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-n2.json` | `tests/behavior/fixtures/training-peft-n2.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-p1.json` | `tests/behavior/fixtures/training-peft-p1.json` | identical |
| AI_Developer | `tests/behavior/fixtures/training-peft-p2.json` | `tests/behavior/fixtures/training-peft-p2.json` | identical |
| AI_Developer | `tests/behavior/results/event-taxonomy.md` | `tests/behavior/results/event-taxonomy.md` | modified |
| AI_Developer | `tests/behavior/results/probe-claude.json` | `tests/behavior/results/probe-claude.json` | modified |
| AI_Developer | `tests/behavior/results/probe-codex.json` | `tests/behavior/results/probe-codex.json` | identical |
| AI_Developer | `tests/behavior/test_run_behavior_tests.py` | `tests/behavior/test_run_behavior_tests.py` | modified |
| AI_Developer | `tests/collector/test_collector.py` | `tools/dataset-collector/tests/test_collector.py` | modified |
| AI_SKILLS | `meta-ads-management/SKILL.md` | `skills/advertising/meta-ads-management/SKILL.md` | identical |
| AI_SKILLS | `mobile-store-release/SKILL.md` | `skills/mobile/mobile-store-release/SKILL.md` | identical |
| AI_SKILLS | `mobile-store-release/references/wordfall.md` | `skills/mobile/mobile-store-release/references/wordfall.md` | modified |
| AI_SKILLS | `store-listing-assets/SKILL.md` | `skills/mobile/store-listing-assets/SKILL.md` | identical |
| AI_SKILLS | `store-listing-assets/references/wordfall.md` | `skills/mobile/store-listing-assets/references/wordfall.md` | modified |
| AI_SKILLS | `suno-music-generator/SKILL.md` | `skills/media/suno-music-generator/SKILL.md` | identical |
| AI_SKILLS | `suno-music-generator/references/client-access.md` | `skills/media/suno-music-generator/references/client-access.md` | identical |
| AI_SKILLS | `suno-music-generator/references/prompt-examples.md` | `skills/media/suno-music-generator/references/prompt-examples.md` | identical |
| AI_SKILLS | `tiktok-ads-management/SKILL.md` | `skills/advertising/tiktok-ads-management/SKILL.md` | identical |

</details>

## Phase 2 — MCP servers

### premiere-pro (`mcp/servers/premiere-pro/`)

Source: private fork `PremiereProMCP` at `5b6281a` (clean working tree) = upstream
`hetpatel-11/Adobe_Premiere_Pro_MCP@ee31c3d` + local security commits `9685f2f`, `5b6281a` (see `THIRD_PARTY_NOTICES.md`).

| Allowlisted (tracked) | Identical | Intentionally modified | Added | Missing |
|---|---|---|---|---|
| 107 | 103 | 4 (`CONTRIBUTING.md`, `README.md`, `package.json`, `scripts/install-macos.sh`) | `.env.example` | 0 |

Allowlist: `src/`, `cep-plugin/`, `uxp-plugin/`, `scripts/`, `images/`, `package.json`, `package-lock.json`,
`tsconfig.json`, `jest.config.js`, `.gitignore`, `LICENSE.md`, `README.md`, `QUICKSTART.md`, `KNOWN_ISSUES.md`,
`CHANGELOG.md`, `SECURITY.md`, `PRIVACY.md`, `TERMS.md`, `CONTRIBUTING.md`.

| Excluded | Reason |
|---|---|
| `website/`, `translations/`, `marketplace-assets/` | upstream marketing site, translated READMEs and store art; not needed to run or develop the server |
| `telemetry/` | upstream's Cloudflare telemetry backend; telemetry is off by default in this fork |
| `.agents/`, `.claude-plugin/`, `claude-plugins/`, `plugins/`, `.cursor/` | marketplace/plugin packaging that installs the npm package; registration here comes from `mcp/registry.json` |
| `.github/` | upstream release/signing workflows (inactive in a subdirectory anyway) |
| `.idea/`, `dist/`, `node_modules/` | editor settings and build/dependency output |
| `skills/premiere-pro-mcp/` | imported separately as `skills/media/premiere-pro-mcp` (bridge dir and registration updated) |

Modifications: `CONTRIBUTING.md` — machine-specific absolute link made relative; `README.md` — provenance/fork note
prepended; `scripts/install-macos.sh` — `--skip-client-config`; `package.json` — `setup:cep` script. Two reviewed home-path exceptions (test fixtures of the telemetry path sanitizer and a schema placeholder)
are recorded in `.public-safety-allowlist.json`.

Verification: `npm ci && npm run build && npm test` → 33 suites / **676 tests passed**, identical to the source repo
(676/676). CI job `premiere-pro` (Node 20, 22).

### google-ads (`mcp/servers/google-ads/`)

Source: `GoogleAds@b4ba9fa`, `google-ads-mcp/` (clean). Allowlisted: all 8 tracked files of that directory.
Identical: 0; intentionally modified: 8 (`README.md`, `config.example.json`, `mutations.py`, `pyproject.toml`, `server.py`, `test_mutations.py`, `test_server.py`, `uv.lock`).
Added: `conftest.py`, `test_instance_isolation.py`, `.env.example`. Not imported here: `GoogleAds/meta-ads/`
(→ remote step), `docs/ads-instructions.md` (→ skill `google-ads-management` + private overlay), `output/`
(evidence with account data), `.mcp.json` (machine paths; registration comes from `mcp/registry.json`).

Generalisation (plan Faz 2.2):
- Hard-coded production customer and app identifiers removed from code; they are now required config fields
  (`production_customer_id`, `apps`). The test/production invariant uses the configured production ID.
- `GOOGLE_ADS_CONFIG` / `GOOGLE_ADS_CREDENTIAL_DIR` (old `WORDFALL_*` names = deprecated aliases; conflicting values
  rejected). No default config/credential path: missing variables → the server refuses to start (exit 2); a named
  but missing config file → every call `OUT_OF_SCOPE` (never a fallback to another instance).
- Audit default: `audit.jsonl` next to the instance config, override `GOOGLE_ADS_AUDIT_PATH`.
- Unconfigured app/store pairs are rejected before any RPC. Tool descriptions and the MCP server name are generic
  (`google-ads`); `pyproject` name `google-ads-mcp` (lock re-resolved: project entry only, no dependency changes).
- Tests made hermetic (`conftest.py`: fake IDs, temporary config, legacy variables cleared). **Baseline in the source
  repository: 114 passed, 2 failed** — both failures were caused by the old implicit default path reading the real
  local config. After import: **128 passed** (116 original incl. the 2 former failures + 12 new isolation tests).
- README rewritten generically (English); the original README (account IDs, setup history) moved to the private
  overlay (`private/mcp/google-ads/README-wordfall-2026-09.md`). `config.example.json` uses placeholder IDs.

Cutover note: existing real instance configs predate the new required fields (`production_customer_id`, `apps`);
they must be extended when the registration switches to this copy (Phase 2 cutover). Until then the running
registration still uses the old project.

### jev (`mcp/servers/jev/`)

Source: `JevAI` (not a Git repository). Allowlist (102 files): `src/**` and `tests/**` without `__pycache__`/`.DS_Store`,
`pyproject.toml`, `uv.lock`, `.python-version`. Identical: 87; intentionally modified: 15. Added:
`src/jev/paths.py`, `tests/test_paths.py`, `README.md`, `.env.example`.

**Not imported:** `.env` (real API keys), `workspace/` (Chrome profiles with sessions, run/task/takeover logs, spike and
benchmark scripts — human decision Q4), `.playwright-mcp/`, `output/` (design notes and reports), `logs/`,
`artifacts/`, `attachments/`, `.venv/`, `.pytest_cache/`, `.claude/`.

Changes: secrets from `JEV_ENV_FILE` (default `~/.config/super-computer-ai/credentials/jev/.env`, loaded only if
present, exported values win) instead of the checkout's `.env`; runtime state (profiles, logs) in `JEV_STATE_DIR`
(default `~/.local/state/super-computer-ai/jev`, 0700) instead of `workspace/`; the tests set a throwaway state dir and
load no secrets unless opted in; state paths are resolved at call time (so a `JEV_STATE_DIR` set in the
`.env` reaches profiles and every log); references to private design notes (`output/plan-*.md`) in comments neutralised.

Tests (live Jev tests skipped, no key): source **309 passed, 4 failed, 27 skipped, 2 xfailed**; new location
identical (**309 / 4 / 27 / 2**) before fixes. The 4 failures (`test_v4.py`, experimental v4 engine) were
pre-existing and are fixed at the root cause: `v4/prices.py` `listing_key` dropped one-letter words, so
`Option X`/`Option Y` (and `Deal A/B/C`) were merged as duplicate rows of one listing; test assertions unchanged.

Cutover note: the existing registrations use profiles under `JevAI/workspace/` (`chrome-profile-claude`, …); at
cutover either move those profiles into the state directory or set `JEV_STATE_DIR` for the instance.

### adb (`mcp/servers/adb/`)

Source: the author's `ADB_MCP_SERVER` Kotlin/Spring Boot project (the IdeaProjects copy; the `Projects/ADB_MCP_SERVER`
directory holds only runtime output). Not a Git repository. Allowlist (92 files): `src/**`, Gradle build files and
wrapper (wrapper jar SHA-256 matches Gradle's published 9.3.1 checksum), `.gitattributes`, `.gitignore`, and the
spec `DOCS/ADB_MCP_Server_MVP_Spec_v3_6.docx` → `docs/` (public per Q5; text, headers, comments and document
properties scanned — no paths, names, e-mails, secrets or device serials). Identical: 87 (incl. the spec);
intentionally modified: 5 (incl. `ScrcpyService.kt`: an agent-supplied `outputPath` must resolve inside the
artifact directory). Added: `infrastructure/StateDir.kt`, `infrastructure/StateDirEnvironmentPostProcessor.kt`,
`META-INF/spring.factories`, `StateDirTest.kt`, `StatePathsTest.kt`, `StateDirStartupTest.kt`, `ScrcpyServiceOutputPathTest.kt`, `README.md`,
`.env.example`.

**Not imported:** `.claude/` (local permissions), `.idea/`, `*.iml`, `.gradle/`, `.kotlin/`, `build/`, `artifacts/`,
`logs/`, `output/` (design note), `attachments/`, `workspace/`, `HELP.md` (Spring Initializr boilerplate, ignored by
the source's own `.gitignore`), `DOCS/skill-ui-review.md` (older subset of `skills/mobile/mobile-ui-review`).

Changes: runtime state (artifacts, recordings, log, host transfer directory) moved from paths relative to the
working directory (`./artifacts`, `./logs`, `./transfers`) to `ADB_MCP_STATE_DIR` (default
`~/.local/state/super-computer-ai/adb`, 0700; an `EnvironmentPostProcessor` applies the effective value from any
source before logging starts, refuses relative values and write locations whose real, symlink-resolved path lies
outside it). The old registrations set no `cwd`, so every project an agent
worked in collected `artifacts/` and `logs/` (found in 14 directories). Tests run with a state dir under `build/`.
`gradle-wrapper.properties` pins `distributionSha256Sum`.

Tests: source **65 passed, 0 failed**; new location **77 passed** (65 + 12 new, incl. a real start-up test in a separate JVM), no device needed.

Cutover note: registrations point at `~/MCP_SERVER/Project/adb-mcp-server.jar` under the name `adb-mcp-server`; at
cutover they switch to the jar built here under the name `adb`, and `mobile-ui-review` drops the old name. Old
`artifacts/`/`logs/` directories in project folders are left for the human to review and delete.

### Remote MCPs and the registry (`mcp/remote/`, `mcp/registry.json`)

- `meta-ads` ← `GoogleAds@b4ba9fa:meta-ads/auth_headers.py` (the only file in that directory). Changes: the token
  file path defaults to `~/.config/super-computer-ai/credentials/meta-ads/system-user-token.txt` (argument still
  accepted; deliberately not an environment variable, because Claude Code strips credential-like variables from
  helpers of project/local-scope servers); a token file readable or writable by group/others, or not a regular file,
  is refused. Unchanged: stdout carries only `{"Authorization": "Bearer …"}`, the token shape check and the generic
  error message. Added `README.md` and `tests/mcp/test_meta_ads_auth_headers.py`.
- `tiktok-ads`: `README.md` only. Authentication verified 2026-09-25 as standard MCP OAuth (401 +
  protected-resource metadata, scope `mcp:tt4b`); the client stores the token, this repository stores nothing.
- `mcp/registry.json` (new; first written as YAML and converted to JSON so the stdlib-only installer and launch
  wrapper can read it, like every other catalog in the repository): generic definitions of all six servers, launch commands with `{path}`/`{client}`
  placeholders, env schemas matching each `.env.example`, auth methods, skills and bundles; `tests/mcp/test_registry.py`
  checks it against the disk and `skills/manifest.json`. Every local launch command was started from the registry
  (`initialize` + `tools/list`): premiere-pro, google-ads (with a placeholder config), jev, jev-chrome, adb.
