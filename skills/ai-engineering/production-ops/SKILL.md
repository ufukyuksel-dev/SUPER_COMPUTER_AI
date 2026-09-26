---
name: production-ops
description: "Use when operating deployed AI systems — monitoring, drift, observability, incident response, cost controls, security posture, provider-fallback resilience, rollout/rollback. Do NOT use for scheduled/autonomous job design (see skill ai-automation)."
---

# Production Operations

## Operating Boundary

- Own production readiness, service health, quality and drift signals, incidents, cost controls, security posture, operational resilience, and rollout/rollback.
- For serving-engine and topology selection, see skill model-serving.
- For evaluation design, see skill eval-harness.
- For scheduled or autonomous workflows, see skill ai-automation.
- For current provider, platform, pricing, and security claims, see skill ai-research.

## Decision Workflow

1. **Define the service contract.** Record owners, users, critical journeys, data classes, dependencies, SLOs, error budget, recovery objectives, and unacceptable outcomes.
2. **Map production risks.** Rank availability, latency, output-quality, drift, safety, privacy, security, dependency, quota, and cost risks by impact and detectability.
3. **Design signals and actions together.** For each risk, define a measurable signal, threshold, window, owner, runbook, and escalation. Use [ops-readiness-checklist.md](references/ops-readiness-checklist.md).
4. **Bound resilience.** Define timeouts, retries, circuit breaking, load shedding, provider fallback, state reconciliation, and degraded modes. Gate every fallback with compatibility and quality evidence.
5. **Prepare incidents.** Establish severity, command ownership, containment, communication, evidence preservation, recovery, and post-incident review.
6. **Control change.** Use versioned artifacts, staged rollout, canaries, automated stop conditions, rollback criteria, and independently verified rollback steps.
7. **Control cost and capacity.** Set budgets, quotas, unit-cost signals, saturation forecasts, anomaly alerts, and an explicit response to budget exhaustion.
8. **Exercise readiness.** Run health, load, dependency-failure, fallback, security, drift, incident, and rollback probes against the target environment before declaring readiness.

## Required Deliverable

Return:

- the service and ownership contract;
- an SLO/error-budget table tied to user journeys;
- a risk-to-signal-to-runbook map;
- resilience and provider-fallback gates;
- incident, rollout, rollback, and cost-control procedures;
- drill output and observed telemetry;
- a readiness verdict with every unexercised item labeled `UNVERIFIED`.

## Decision Rules

- Derive alerts from user impact and actionable runbooks, not from available dashboard widgets.
- Separate system health, model/output quality, safety, drift, and business-impact signals.
- Treat provider fallback as a behavior change; validate schema, semantics, safety, latency, capacity, and cost before enabling it.
- Fail closed for authorization, privacy, or data-residency uncertainty; degrade explicitly for availability or quality pressure.
- Require a rollback path before rollout and verify it using the same artifact and environment boundaries as production.
- Preserve audit and incident evidence while redacting credentials and unnecessary sensitive content.

## Failure Modes

- Do not declare readiness from configuration review alone.
- Do not use averages alone for tail latency, failure bursts, cost spikes, or quality regressions.
- Do not retry every failure or route blindly to a fallback provider.
- Do not page on signals without an owner and executable response.
- Do not perform an emergency change without scope, audit, verification, and rollback criteria.
- Do not label missing telemetry, drills, or rollback evidence as a pass.

## Tool Requirements & Degradation

- Require production-like telemetry, deployment state, dependency health, cost/usage data, security findings, and runbook access for readiness claims.
- Require a controlled environment and authorized deployment controls for fallback, incident, and rollback drills.
- For current provider limits, terms, pricing, vulnerabilities, or platform behavior, see skill ai-research.
- If telemetry or cost data is unavailable, produce the instrumentation contract and mark affected SLO, drift, and budget controls `UNVERIFIED`; do not infer health from absence of alerts.
- If a safe drill environment or deployment access is unavailable, review procedures and provide exact probes, but do not claim fallback or rollback readiness.
- If security authority or incident ownership is unresolved, block production-readiness approval and ask for the named owner or decision.
