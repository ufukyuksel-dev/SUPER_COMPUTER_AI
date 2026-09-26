# Security

## Secrets policy

- This repository must never contain secrets, tokens, API keys, `.env` files, account or customer IDs,
  e-mail addresses, browser profiles or machine-specific absolute paths.
- Credentials: `~/.config/super-computer-ai/credentials/<server>/` (directory `0700`, files `0600`).
- Sensitive project values: `~/.config/super-computer-ai/private/`.
- Only variable names and `.env.example` files are committed.

## Enforcement

- `scripts/validate.py` rejects `.env` files (except `.env.example`), **all** key and certificate container files
  (`.pem`, `.p12`, `.pfx`, `.key`, `id_rsa`, … — public certificates included, by policy), symlinks with absolute or
  repository-escaping targets, absolute home paths and common secret patterns. `--staged` checks exactly what the
  next commit contains (the pre-commit hook uses it).
- `.env.example` files get no scanner exemption; they must contain variable names with empty or dummy values.
- CI runs `validate.py` and a gitleaks scan on every push and pull request.
- A local pre-commit hook runs the same checks (`pre-commit install`).

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on this repository.

If you accidentally committed a secret: rotate it immediately at the provider, then remove it from history.
Deleting the file in a new commit is not enough.
