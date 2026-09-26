# Model Card Checklist

Record the exact model ID, organization, revision or commit, and access date before evaluating any field.

## Identity and artifact

- Verify architecture, parameter count, base or parent model, revision, file formats, and declared context limits from primary artifacts.
- Verify input/output modalities, supported languages, task framing, and required preprocessing or chat template.
- Distinguish base, instruct, fine-tuned, quantized, adapter, and merged variants; do not transfer facts between variants without evidence.

## License and access

- Inspect model-card metadata, repository license file, linked terms, acceptable-use policy, and upstream/base-model obligations.
- Record commercial-use, redistribution, derivative, attribution, field-of-use, and geographic restrictions relevant to the request.
- Record gated access, approval requirements, authentication, click-through terms, and artifact availability.
- Mark contradictions `conflicted`; identify the governing document that must resolve them.

## Workload fit

- Match task, modality, language, context distribution, output structure, and safety requirements to directly relevant evidence.
- Record evaluation dataset, metric, baseline, sample size, hardware, precision, and method before using a benchmark claim.
- Identify contamination, self-reporting, missing variance, or workload mismatch.
- Record privacy, data-egress, remote-code, tokenizer, and custom-code implications.

## Operational handoff

- Pass exact parameter, architecture, precision, context, concurrency, and artifact-format inputs to `inference-optimization` for memory analysis.
- Pass model/runtime/API requirements to `model-serving` for engine compatibility and topology decisions.
- Pass candidate-specific behavior risks and claimed strengths to `eval-harness` for workload validation.

## Evidence table

| Field | Value | Status | Primary citation | Scope/revision | Conflict or follow-up |
|---|---|---|---|---|---|
| `<field>` | `<value>` | `verified / conflicted / unverified` | `[Title](URL) — accessed YYYY-MM-DD` | `<revision>` | `<note>` |

Do not recommend a candidate that fails a hard constraint or has unresolved commercial-license uncertainty. Label provisional candidates and every unverified field explicitly.
