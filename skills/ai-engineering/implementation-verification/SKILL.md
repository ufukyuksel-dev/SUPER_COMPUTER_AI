---
name: implementation-verification
description: "Use when a task is claimed complete — before reporting success. Exercises the deliverable end-to-end against its acceptance criteria: run it, probe edge cases, check claims against actual output, list what was NOT verified. Do NOT use for designing metrics (see skill eval-harness)."
---

# Implementation Verification

## Boundaries

- Verify an existing deliverable against authoritative acceptance criteria with direct execution and observed evidence.
- Do not design a future architecture or implementation plan; for that work, see skill ai-system-design.
- Do not invent metrics, evaluation sets, or judges; for evaluation design, see skill eval-harness and consume its declared gates.
- Treat code inspection, diffs, unit tests, manifests, and green checks as supporting evidence only for the scope they actually exercise.
- Never redefine, narrow, waive, or convert an acceptance criterion into a weaker pass without explicit human approval.

## Decision Workflow

1. Establish the exact deliverable, environment, claimed completion scope, authoritative criteria, required side effects, prohibited side effects, and risk boundaries. Reject vague success criteria before sign-off.
2. Build an evidence matrix with one row per criterion: criterion, scope, direct command/probe, expected observable result, actual output/side effect, artifact locator, and `PASS/FAIL/UNVERIFIED` status.
3. Inspect the current implementation and environment narrowly enough to choose valid execution paths. Record versions, configuration, fixtures, credentials/permissions availability, and preconditions; redact secrets from evidence.
4. Execute the real entry point end to end in the safest representative environment. Capture the exact command or request, exit/status, relevant output, logs, generated artifacts, state changes, and cleanup/rollback result.
5. Exercise relevant edge and failure behavior: malformed and boundary inputs, empty/large cases, authorization and tenant isolation, retries/timeouts, idempotency, concurrency, partial dependency failure, cancellation, rollback, and recovery.
6. Run unit, integration, regression, static, security, and evaluation checks that map to criteria. Preserve their scope; unit success does not prove integration or end-to-end acceptance.
7. Reconcile claims against observed behavior. Distinguish product failures, test defects, and infrastructure limitations without turning any of them into a pass.
8. Exhaust safe local evidence when an external dependency is unavailable. Test adapters, request construction, validation, deterministic failure handling, and recorded fixtures where valid, but mark the live provider-dependent path `UNVERIFIED`.
9. Sign off only when every required criterion has direct, scope-matched passing evidence and no required path remains unverified. Otherwise report incomplete status, exact failures/gaps, residual risk, and next verification command.

Read [the verification checklist](references/verification-checklist.md) before sign-off.

## Evidence Status Rules

- `PASS`: the required path ran, the expected observable result and side effects occurred, and evidence covers the criterion's full scope.
- `FAIL`: observed product behavior contradicts the criterion, including unsafe or prohibited side effects.
- `UNVERIFIED`: evidence is inaccessible, skipped, simulated, stale, indirect, or narrower than the criterion. `UNVERIFIED` is not a weak pass.

Report exact commands/probes, observed outputs, failures, skipped checks, inaccessible dependencies, unverified claims, and residual risk. Keep raw artifacts available or identify their path.

## Tool Requirements & Degradation

- Require repository/artifact inspection plus permission to run the build, tests, actual entry point, relevant service/dependency probes, log/state inspection, and safe cleanup.
- Use the least-privileged representative environment. Ask before irreversible actions, production writes, requirement-weakening workarounds, or a paid full behavior suite.
- If execution permission is unavailable, provide inspection findings and exact commands but label the execution-dependent criteria `UNVERIFIED`.
- If an external provider is down or credentials are unavailable, never simulate success or fake output. Exhaust safe local evidence, separate the infrastructure limitation, and mark the live path `UNVERIFIED`.
- If required observability or side-effect inspection is unavailable, do not pass a criterion solely from an exit code or response body.
- If a check would expose secrets or confidential payloads, redact evidence or use an approved safe fixture without weakening the behavior being tested.

## Failure Modes

- Approving from a code diff, review, manifest, typecheck, or unit suite without running the deliverable.
- Testing only the happy path and omitting malformed input, authorization, retries, partial failure, or side effects.
- Using a mock, fixture, or simulated provider result as proof of the live integration.
- Hiding skipped checks, truncated output, flaky results, environment drift, or inaccessible evidence.
- Treating infrastructure failure as product success or product failure without distinguishing the evidence.
- Claiming a broad criterion from a narrow test or assuming a green command covers undocumented scope.
- Moving the acceptance threshold after observing results or redefining completion around what already passes.
