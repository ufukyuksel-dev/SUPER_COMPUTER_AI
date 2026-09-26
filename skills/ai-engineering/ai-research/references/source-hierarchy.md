# Source Hierarchy

Use the highest-authority source that directly governs or demonstrates the claim.

| Priority | Source | Use |
|---|---|---|
| 1 | Official product, provider, regulator, standards body, policy, pricing, or API documentation | Verify the provider's current behavior, obligations, interfaces, limits, and commercial terms. |
| 2 | Official model card, dataset card, license file, release tag, changelog, or source repository | Verify the exact artifact, revision, declared license, compatibility, provenance, and implementation state. |
| 3 | Original paper, technical report, benchmark artifact, or authors' reproducible code | Verify research methods, measured results, assumptions, and limitations. |
| 4 | Reputable independent secondary source | Discover primary sources, provide context, or corroborate; do not use as sole proof when a primary source should exist. |

## Selection checks

- Open the source itself and match the exact product, artifact, version, region, plan, modality, and date.
- Prefer a governing terms or license document over summaries of that document.
- Prefer a versioned artifact over an undated landing page.
- Prefer measured, reproducible evidence over vendor or author interpretation for performance claims.
- Record effective, publication, release, or commit dates separately from the access date.
- Preserve a stable deep link, revision, commit, section, or table locator when available.
- Use multiple sources when one source cannot establish both identity and the claimed property.

## Conflict ledger

For every material disagreement, record:

| Claim | Source A | Source B | Authority | Recency | Scope | Reproducibility | Resolution |
|---|---|---|---|---|---|---|---|
| `<exact claim>` | `<citation>` | `<citation>` | `<comparison>` | `<comparison>` | `<comparison>` | `<comparison>` | `resolved / unresolved` |

Do not use recency as an automatic tiebreaker. A newer source may describe a different version or scope. Report the conflict when the governing source or reproducible behavior remains unclear.
