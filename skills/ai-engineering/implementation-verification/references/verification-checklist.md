# Verification Checklist

## Preflight

- Identify the authoritative acceptance criteria and preserve their original scope and thresholds.
- Pin the deliverable revision/artifact, environment, versions, configuration, data fixtures, dependencies, and permissions.
- Identify destructive, paid, external, confidential, or production-affecting probes and obtain required approval.
- Define expected outputs, side effects, prohibited effects, cleanup, and rollback before execution.

## Evidence matrix

| Criterion | Full scope | Command/probe | Expected | Observed output and side effects | Artifact/log | Status |
|---|---|---|---|---|---|---|
| `<criterion>` | `<scope>` | `<exact command/request>` | `<observable threshold>` | `<actual evidence>` | `<path or locator>` | `PASS / FAIL / UNVERIFIED` |

Do not combine criteria whose scopes require different evidence.

## Execution

- Build or install through the supported path in a clean or controlled environment.
- Run the real entry point end to end, not only a helper or mocked layer.
- Capture command/request, working directory or endpoint, exit/status, relevant stdout/stderr/body, logs, artifacts, state changes, and timing.
- Confirm expected side effects and absence of prohibited side effects.
- Run the documented setup, restart/resume, upgrade/migration, and cleanup paths when they are in scope.

## Edge and failure probes

- Exercise malformed, missing, boundary, empty, large, Unicode, and adversarial inputs as relevant.
- Exercise authentication, authorization, tenant separation, sensitive-data handling, and audit behavior.
- Exercise timeout, retry budget, idempotency, concurrency, cancellation, partial failure, fallback, restart, and rollback as relevant.
- Verify fail-closed behavior and recovery state, not only the returned message.

## Supporting checks

- Map unit, integration, regression, evaluation, static, dependency, and security checks to the criteria they actually cover.
- Repeat flaky or stochastic checks according to the predeclared policy; retain every run.
- Compare runtime behavior with documentation and configuration claims.
- Inspect raw evidence when a wrapper reports only a summary.

## Degraded dependencies

- Exhaust safe local checks of validation, serialization, requests, adapters, deterministic errors, and approved recorded fixtures.
- Separate `infrastructure limitation` from `observed product failure`.
- Mark the inaccessible live path `UNVERIFIED`; never substitute a simulated success.
- Name the exact credential, provider state, permission, environment, or command required to close the gap.

## Sign-off gate

- Require every mandatory criterion to be `PASS` with direct scope-matched evidence.
- Report all failures, unverified paths, skipped checks, residual risks, and evidence locations.
- Refuse completion when any required criterion is `FAIL` or `UNVERIFIED`.
