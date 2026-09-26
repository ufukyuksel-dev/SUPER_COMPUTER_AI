# openai-skill-creator (vendored scripts)

Layer 0 of `scripts/skills/validate_skills.py` runs the official `quick_validate.py`; `update_openai_metadata.py`
and `new_skill.py` use `generate_openai_yaml.py` and `init_skill.py`. Vendoring them makes CI and every clone
run the same Layer 0 as a local Codex installation.

- License: Apache License 2.0 — `LICENSE.txt` (unmodified).
- Source: the Codex-bundled system skill `skill-creator` (`$CODEX_HOME/skills/.system/skill-creator`,
  system-skills marker `8bcfb84cfbe4722a`), copied 2026-09-25 without modification.
- Relation to the public repository: `openai/skills@49f948faa9258a0c61caceaf225e179651397431`
  (`skills/.system/skill-creator/scripts/`) has an older `quick_validate.py`; the vendored copy is a strict superset
  (adds the unfinished-`[TODO:` description/body checks).
- Integrity: `SHA256SUMS`; the validator refuses to run Layer 0 if a vendored file does not match.

To update: copy the newer files, update `SHA256SUMS` and this README, run the full test suite.
