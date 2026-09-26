# skills

Canonical skill sources, grouped by category. Each skill is `skills/<category>/<name>/SKILL.md` plus optional
`references/` and `agents/openai.yaml`. Skill names are unique across all categories.

| Category | Skills | Bundle |
|---|---|---|
| `ai-engineering` | 14 skills for designing, building, evaluating and operating AI systems (see its README) | `ai-engineering` |
| `advertising` | `google-ads-management`, `meta-ads-management`, `tiktok-ads-management` | `ads` |
| `mobile` | `mobile-store-release`, `store-listing-assets`, `mobile-ui-review` | `mobile` |
| `media` | `suno-music-generator` | `media` |
| `browser` | `jev-browser` | `browser` |

## manifest.json (schema 2)

Every skill has one entry; its directory is derived as `skills/<category>/<name>`:

```json
"skill-name": {"category": "media", "status": "active", "profile": "basic",
               "platforms": ["claude", "codex"], "bundles": ["media"]}
```

- `status`: `active` (exists on disk, installed) or `planned` (reserved name, must not exist on disk).
- `profile`: `strict` (full AI-engineering contract) or `basic` (see `scripts/skills/validate_skills.py`).
- `platforms`: where the installer links it. `bundles`: which install bundles include it.

## Adding a skill

1. Create `skills/<category>/<name>/SKILL.md` with `name` and `description` frontmatter (no secrets, no machine paths).
2. Add the manifest entry. Strict skills also need `agents/openai.yaml`
   (`python3 scripts/update_openai_metadata.py ...`) and a routing row in
   `instructions/global/30-ai-engineering-routing.md`.
3. Run `python3 scripts/skills/validate_skills.py` and `python3 scripts/validate.py`.

Project-specific private values (paths, account IDs) go to `~/.config/super-computer-ai/private/skills/<name>/`, never here.
