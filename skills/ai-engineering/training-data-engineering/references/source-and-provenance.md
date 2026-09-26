# Sources and Provenance

## sources.yaml shape

```yaml
sources:
  - id: support-forum
    type: api            # MVP supports `api` only; other source types need a new
                         # adapter in tools/dataset-collector/collector/adapters.py first
    endpoint: https://example.com/api/threads
    rate_limit_per_min: 30
    license_note: "verified 2026-08-24 via ai-research task <ref>"
```

Credentials are never stored here or in any file; the collector reads them from environment variables named in `auth_env` (e.g. `auth_env: SUPPORT_FORUM_TOKEN`).

## Per-example provenance record (JSONL)

| Field | Meaning |
|---|---|
| `url` | Exact source locator |
| `accessed_at` | ISO 8601 fetch time |
| `license` | License/right under which the example is used |
| `content_sha256` | Hash of the raw payload (also the raw filename) |
| `collector_version` | Version of the collector that fetched it |
| `source_id` | Entry in sources.yaml |

Every example in every split must resolve to a provenance record. Provenance completeness is a quality gate; examples without provenance are rejected with reason `missing-provenance`.

## Rights rules

- Verify ToS/license per source through skill ai-research before bulk collection; record the verification reference in `license_note`.
- Crawl permission (robots) and training-use license are different questions; check the license even when crawling is allowed.
- Do not bypass authentication or paywalls.
- If rights cannot be established, hold the data as `unverified-rights`; it never enters a `training-ready` dataset.
