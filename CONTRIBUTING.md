# Contributing

1. Read `AGENTS.md` for where each kind of artifact goes and the public-repo rules.
2. Keep each MCP server self-contained: its own README, `.env.example`, tests and lockfile.
3. Use kebab-case names; skill names must be unique across all categories.
4. Before committing:
   ```sh
   python3 scripts/validate.py            # working tree
   python3 scripts/validate.py --staged   # exactly what you are about to commit
   python3 -m unittest discover -s tests -q
   ```
5. Enable the local hooks once: `pre-commit install`.
6. Third-party code: keep its `LICENSE` file and add an entry to `THIRD_PARTY_NOTICES.md`.
