# Recency Checklist

## Before retrieval

- Define the exact claim and the decision it affects.
- Set the acceptable as-of date or freshness window.
- Identify version, revision, region, plan, hardware, runtime, and license scope that could change the answer.
- Set a bounded time or cost ceiling when one exists.

## For each source

- Confirm that the source is primary for the claim.
- Capture title, direct URL, access date, and any effective, release, commit, or publication date.
- Match the source scope to the requested artifact and environment.
- Check for superseding notices, archived versions, conflicting branches, or version selectors.
- Separate quoted or directly stated facts from calculations and inference.
- Capture enough method detail to judge whether a benchmark or experiment is reproducible.

## Claim record

| Claim | Status | Evidence | Source date/version | Accessed | Scope match | Notes |
|---|---|---|---|---|---|---|
| `<atomic claim>` | `verified / conflicted / unverified` | `[Title](URL)` | `<date or revision>` | `YYYY-MM-DD` | `yes / partial / no` | `<inference or gap>` |

## Before stopping

- Ensure every critical fact has direct primary evidence or an explicit unresolved label.
- Reconcile source conflicts by authority, recency, scope, and reproducibility, or report them.
- Stop when additional retrieval yields no decision-relevant facts; record saturation rather than claiming exhaustive search.
- If the budget ceiling stops the work, list uncovered claims and the next highest-value source to inspect.
- Use the citation form `[Title](URL) — accessed YYYY-MM-DD` for every decision-bearing source.
