import time
from datetime import datetime, timezone

from .adapters import build_adapter
from .config import COLLECTOR_VERSION, load_sources
from .ratelimit import RateLimiter, retry_backoff
from .storage import (
    append_error,
    append_provenance,
    load_state,
    save_raw,
    save_state,
    seen_hashes,
    sha256_hex,
)


def collect(
    source_id: str,
    sources_path: str,
    data_dir: str,
    adapter=None,
    sleep_fn=time.sleep,
    max_pages: int = None,
    retries: int = 3,
):
    """Collect records from one source with resume, rate limiting, and retries.

    Resumes from the stored cursor. Records whose content hash already appears
    in provenance are skipped, so a resumed run never duplicates examples.
    Returns counts: {"fetched": n, "skipped": n, "errors": n}.
    """
    sources = load_sources(sources_path)
    source = sources[source_id]
    if adapter is None:
        adapter = build_adapter(source)

    limiter = RateLimiter(source.rate_limit_per_min, sleep_fn=sleep_fn)
    state = load_state(data_dir, source_id)
    cursor = state.get("cursor")
    seen = seen_hashes(data_dir)
    counts = {"fetched": 0, "skipped": 0, "errors": 0}
    pages = 0

    while True:
        limiter.wait()
        records, next_cursor = retry_backoff(
            lambda: adapter.fetch(cursor), retries=retries, sleep_fn=sleep_fn
        )
        for record in records:
            try:
                content = record["content"]
                digest = sha256_hex(content)
                if digest in seen:
                    counts["skipped"] += 1
                    continue
                save_raw(data_dir, content)
                append_provenance(
                    data_dir,
                    {
                        "url": record["url"],
                        "accessed_at": datetime.now(timezone.utc).isoformat(),
                        "license": record.get("license", ""),
                        "content_sha256": digest,
                        "collector_version": COLLECTOR_VERSION,
                        "source_id": source_id,
                    },
                )
                seen.add(digest)
                counts["fetched"] += 1
            except Exception as exc:  # incomplete records are logged, not stored
                counts["errors"] += 1
                url = record.get("url", "") if isinstance(record, dict) else ""
                append_error(
                    data_dir,
                    {"source_id": source_id, "url": url, "error": str(exc)},
                )
        # checkpoint after each fully-processed page
        save_state(data_dir, source_id, {"cursor": next_cursor})
        cursor = next_cursor
        pages += 1
        if next_cursor is None or (max_pages is not None and pages >= max_pages):
            break

    return counts
