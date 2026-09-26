# Intake Checklist

Capture only facts that can change the design. Separate answers into `known`, `assumed`, and `unresolved`.

## Outcome and scope

- Define the user, decision, workflow, intended outcome, and explicit non-goals.
- Describe inputs, outputs, quality expectations, failure tolerance, and human review points.
- Identify the existing system, integration surface, owner, and delivery boundary.

## Data and trust

- Identify data sources, owners, rights, sensitivity, retention, residency, freshness, and deletion needs.
- Define tenant, role, authorization, audit, and provenance requirements.
- Define allowed network and data-egress boundaries, including model/provider exposure.

## Workload and constraints

- Bound traffic, concurrency, payload size, context length, latency, availability, and recovery objectives.
- Record hardware, deployment environment, model/provider constraints, licenses, budget, and schedule.
- Identify current facts requiring primary-source verification.

## Quality and operations

- Define task success, unacceptable outcomes, critical slices, baselines, and decision thresholds.
- Identify monitoring, drift, incident, rollback, cost, and support ownership.
- Identify schedules, triggers, approval gates, and irreversible actions.

## Ambiguity gate

- Ask the smallest question whose answer would change a major option, trust boundary, or acceptance threshold.
- Use at most two focused evidence passes for an ambiguous term; then ask the human.
- Never manufacture business meaning, traffic, data sensitivity, or risk tolerance to keep planning moving.
