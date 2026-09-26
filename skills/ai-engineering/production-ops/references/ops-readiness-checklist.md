# Operations Readiness Checklist

Use this checklist to gate a deployed AI system. Mark each row `PASS`, `FAIL`, or `UNVERIFIED`, and attach observed evidence. Do not convert missing evidence into a pass.

## Contents

- [Service Contract and Ownership](#service-contract-and-ownership)
- [SLO and Error Budget](#slo-and-error-budget)
- [Observability](#observability)
- [Quality, Safety, and Drift](#quality-safety-and-drift)
- [Security and Privacy](#security-and-privacy)
- [Resilience and Provider Fallback](#resilience-and-provider-fallback)
- [Capacity and Cost](#capacity-and-cost)
- [Incident Readiness](#incident-readiness)
- [Rollout and Rollback](#rollout-and-rollback)
- [Required Drills](#required-drills)
- [Release Gate](#release-gate)

## Service Contract and Ownership

- [ ] Name the service owner, on-call owner, security owner, data owner, and rollback authority.
- [ ] Identify critical user journeys and unacceptable outcomes.
- [ ] Classify processed data, tenants, regions, and external-egress boundaries.
- [ ] Inventory models, providers, stores, queues, tools, feature flags, and downstream dependencies.
- [ ] Record versioned deployable artifacts and configuration ownership.
- [ ] Define support hours, escalation targets, and communication channels.

## SLO and Error Budget

For each critical journey, complete:

| Journey | Indicator | Target/window | Error budget | Measurement source | Owner | Exhaustion action |
|---|---|---|---|---|---|---|
| | | | | | | |

- [ ] Cover availability, tail latency, correctness/quality, and safety where each is user-visible.
- [ ] Specify inclusion, exclusion, sampling, aggregation, and missing-data behavior.
- [ ] Verify clocks, correlation identifiers, and measurement boundaries.
- [ ] Tie burn-rate thresholds to staged action and change policy.
- [ ] Prevent maintenance exclusions from hiding user impact.

## Observability

- [ ] Correlate request, session, model/provider, tool, retrieval, and deployment identifiers.
- [ ] Capture latency by stage, token/compute usage, retries, timeouts, cancellations, queueing, and cache behavior.
- [ ] Capture bounded input/output quality and safety signals without storing unnecessary payloads.
- [ ] Record model, prompt, retrieval index, policy, tool, and configuration versions.
- [ ] Emit structured, stable error classes rather than relying on free-form text.
- [ ] Redact secrets, credentials, PII, confidential data, and sensitive model content.
- [ ] Define trace sampling that preserves rare severe events and bounds cost.
- [ ] Test dashboards and alerts using injected known signals.

## Quality, Safety, and Drift

- [ ] Define production quality indicators and their relationship to offline evaluation.
- [ ] Maintain a reviewed sample path for false positives, false negatives, and silent failures.
- [ ] Detect input, retrieval, output, latency, safety, and cost distribution shifts separately.
- [ ] Set thresholds from baselines and user impact, not arbitrary percentages.
- [ ] Distinguish data drift, concept drift, dependency change, and instrumentation change.
- [ ] Version judge models, prompts, rubrics, and sampling rules when used.
- [ ] Route regression findings to an owner with containment and reevaluation steps.
- [ ] Prevent live sensitive payloads from entering external evaluation without authorization and redaction.

## Security and Privacy

- [ ] Apply least privilege to service identities, model providers, tools, stores, and deployment systems.
- [ ] Keep secrets outside prompts, logs, traces, images, and error messages.
- [ ] Enforce tenant, workspace, environment, and data-residency boundaries server-side.
- [ ] Validate input and output size, type, destination, and content policies.
- [ ] Defend against prompt injection, tool abuse, data exfiltration, SSRF, path traversal, and confused-deputy access.
- [ ] Define retention, deletion, legal hold, audit access, and incident-evidence rules.
- [ ] Inventory supply-chain artifacts and verify provenance, integrity, and vulnerability response.
- [ ] Test authorization denial, revoked credentials, rotated secrets, and compromised dependency containment.

## Resilience and Provider Fallback

- [ ] Set per-stage timeouts from the end-to-end deadline.
- [ ] Retry only classified transient failures and cap attempts, delay, and total budget.
- [ ] Make mutation retries idempotent or reconcile ambiguous outcomes.
- [ ] Define circuit breakers, load shedding, queue bounds, backpressure, and admission control.
- [ ] Define behavior for quota exhaustion, regional failure, provider outage, corrupt output, and slow dependency.
- [ ] Verify fallback schema, tool support, context behavior, safety policy, data-egress boundary, and semantic quality.
- [ ] Measure fallback latency, capacity, availability, and unit cost under expected load.
- [ ] Prevent retry storms and synchronized failover overload.
- [ ] Define explicit degraded-mode messaging and stop conditions.
- [ ] Exercise recovery to the primary path and state reconciliation after failover.

## Capacity and Cost

- [ ] Forecast peak request rate, concurrency, queue depth, token volume, storage, and external calls.
- [ ] Measure cost per critical journey, tenant, model/provider, and deployment version.
- [ ] Set hard quotas and soft alerts with named owners and actions.
- [ ] Detect anomalous loops, retry amplification, cache misses, oversized contexts, and runaway tool calls.
- [ ] Define budget-exhaustion behavior that preserves security and data integrity.
- [ ] Validate capacity during fallback, deployment overlap, and dependency degradation.
- [ ] Reconcile provider bills or usage records with internal telemetry.

## Incident Readiness

- [ ] Define severity using user impact, safety, privacy, scope, and duration.
- [ ] Assign incident command, operations, communications, subject-matter, and evidence roles.
- [ ] Provide runbooks for critical alerts and known failure classes.
- [ ] Define containment actions: disable feature, revoke credential, isolate tenant, block tool, shed load, or roll back.
- [ ] Preserve a timestamped decision log and redacted evidence.
- [ ] Define internal, customer, provider, legal, and security communication triggers.
- [ ] Verify recovery criteria and post-recovery monitoring.
- [ ] Schedule blameless review, corrective-action ownership, and recurrence verification.

## Rollout and Rollback

- [ ] Version model, prompt, retrieval data/index, policies, tools, code, and configuration independently.
- [ ] Define compatibility and migration requirements across versions.
- [ ] Use staged exposure with representative traffic and a control group where appropriate.
- [ ] Set automated stop conditions for availability, latency, quality, safety, security, and cost.
- [ ] Define the exact artifact, state, and configuration restored by rollback.
- [ ] Account for irreversible data migrations, queued work, caches, and external side effects.
- [ ] Verify rollback permissions, commands, duration, data integrity, and postcondition.
- [ ] Preserve the failed artifact and evidence for diagnosis.

## Required Drills

Run in an authorized, controlled environment:

- [ ] critical dependency timeout and outage;
- [ ] provider quota exhaustion and rate limiting;
- [ ] fallback activation, sustained operation, and recovery;
- [ ] malformed or unsafe model/tool output;
- [ ] telemetry loss and stale dashboard data;
- [ ] cost spike or runaway recursion;
- [ ] credential revocation and rotation;
- [ ] tenant-isolation denial;
- [ ] canary abort and rollback;
- [ ] incident escalation and communication.

Record commands, timestamps, actual signals, alerts, decisions, observed user impact, and recovery duration.

## Release Gate

Approve production readiness only when:

- every critical journey has measured SLOs and actionable alerts;
- high-impact risks have tested containment and recovery;
- provider fallback has compatibility and load evidence or is explicitly disabled;
- rollout and rollback have been exercised with the target artifact class;
- security and data-boundary owners have accepted residual risk;
- cost and capacity have bounded exhaustion behavior;
- every remaining `UNVERIFIED` item has an owner, due condition, and explicit risk acceptance.

Reject the gate when ownership, authorization, rollback, data boundary, or critical telemetry is unresolved.
