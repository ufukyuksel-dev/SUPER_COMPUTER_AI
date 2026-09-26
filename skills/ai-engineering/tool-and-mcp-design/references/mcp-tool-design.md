# Tool and MCP Design

Use this reference to select an agent capability surface and define a bounded, testable contract. Verify platform-specific behavior and current protocol requirements through see skill ai-research.

## Contents

- [Decision Table](#decision-table)
- [Skill](#skill)
- [Plugin](#plugin)
- [Subagent](#subagent)
- [Harness](#harness)
- [Hook](#hook)
- [Tool Contract](#tool-contract)
- [MCP Server Boundary](#mcp-server-boundary)
- [Tool-Security Checklist](#tool-security-checklist)
- [Audit Event Minimum](#audit-event-minimum)
- [Contract-Test Matrix](#contract-test-matrix)

## Decision Table

| Need | Choose | Require | Reject when |
|---|---|---|---|
| One bounded model-invoked operation | Tool | Typed schema, narrow authority, stable errors | The operation needs arbitrary execution or hidden permissions |
| Standardized external capability/resource boundary | MCP server | Explicit tools/resources, auth, lifecycle, audit, compatibility tests | A local function is sufficient or protocol behavior cannot be verified |
| Reusable procedural guidance and references | Skill | Clear trigger, imperative workflow, bounded concern | Independent execution, credentials, or runtime state is required |
| Installable bundle of related capabilities | Plugin | Ownership, manifest, dependencies, lifecycle, permissions | One skill or one tool is sufficient |
| Isolated or parallel delegated work | Subagent | Task boundary, minimal context, tool/permission limits, handoff contract | Shared state is implicit or work cannot be independently verified |
| Deterministic event-triggered enforcement | Hook | Verified event, bounded action, timeout, failure policy | Model judgment or unsupported platform events are required |
| Execution policy and orchestration across calls | Harness | Budgets, lifecycle, routing, approvals, traces, eval integration | The concern belongs inside one capability contract |

Choose multiple surfaces only when each has a distinct owner. Record why a simpler surface is insufficient.

## Skill

Choose a skill to carry reusable decision procedure, domain rules, checklists, and references into an agent's context.

Require:

- a precise positive and negative trigger;
- one concern boundary and explicit handoffs;
- imperative instructions and progressive disclosure;
- no hidden credentials, runtime authority, or independent state;
- validation against realistic prompts.

Do not use a skill as an access-control mechanism, scheduler, runtime service, or substitute for executable validation.

## Plugin

Choose a plugin when capabilities must be packaged, installed, versioned, enabled, or distributed together.

Require:

- an explicit manifest and owner;
- dependency and compatibility declarations;
- install, update, disable, and removal behavior;
- permissions and connection requirements;
- a reason the bundle is safer or clearer than independent components.

Do not assume that plugin packaging creates isolation or grants authority. Verify the target platform's current plugin model before designing against it.

## Subagent

Choose a subagent when work benefits from isolated context, bounded role authority, independent verification, or safe parallelism.

Require:

- a concrete task with a terminal deliverable;
- only the context, tools, and permissions needed for that task;
- explicit read/write ownership for shared artifacts;
- cancellation, timeout, and failure propagation;
- a structured handoff containing evidence, changes, and unresolved items.

Do not delegate an ambiguous responsibility, leak the expected answer into independent evaluation, or assume shared state is synchronized.

## Harness

Choose the harness to own execution lifecycle and cross-capability policy rather than business logic inside a single tool.

Require:

- model and capability discovery;
- budgets, timeouts, cancellation, concurrency, and recursion limits;
- approval orchestration and permission enforcement;
- trace correlation, redaction, audit, and result persistence;
- retry, fallback, and error classification;
- evaluation hooks and deterministic test fixtures.

Do not let the harness silently broaden tool authority, hide unsupported routing evidence, or convert failed verification into a weak pass.

## Hook

Choose a hook for a verified lifecycle event that requires a deterministic, bounded reaction such as validation, redaction, policy enforcement, or telemetry emission.

Require:

- an authoritative event name and payload contract;
- strict timeout and failure behavior;
- reentrancy and ordering rules;
- no unbounded model loop or hidden mutation;
- observable pass, block, and failure outcomes.

Do not invent events that the target platform does not expose. Prefer harness logic when ordering or portability is uncertain.

## Tool Contract

Define one action per tool and complete this checklist:

### Identity and semantics

- Use a verb-led name that states the action.
- State the resource, tenant, scope, side effects, and invariants.
- Separate read, preview, mutate, approve, and verify operations.
- Classify the action as read-only, reversible write, irreversible write, or external communication.

### Input schema

- Require explicit target identifiers; reject ambiguous names and broad globs.
- Use enums and constrained types instead of free-form modes.
- Set length, count, depth, range, and format limits.
- Distinguish absent, empty, and default values.
- Include idempotency, dry-run, approval, and version fields only when the runtime enforces them.
- Reject unknown fields where permissive parsing could broaden behavior.

### Output and errors

- Return a bounded, typed result with stable identifiers.
- Separate data from human-readable commentary.
- Return pagination or retrieval handles instead of unbounded payloads.
- Define machine-readable errors for invalid input, unauthorized access, conflict, rate limit, timeout, dependency failure, cancellation, and ambiguous outcome.
- Redact secrets and sensitive payloads from both success and error results.

### Side effects

- Bind authorization to the normalized target after server-side resolution.
- Require preview plus explicit approval for irreversible or high-impact mutations.
- Make retry safety and reconciliation behavior explicit.
- Expose partial completion and compensation status.
- Verify the postcondition with a separate observation when risk warrants it.

## MCP Server Boundary

Define the server without assuming current protocol details:

- Inventory exposed tools and resources and justify each one.
- Keep server capabilities narrower than backing-service credentials.
- Authenticate the client and authorize every normalized resource operation.
- Bind tenant, workspace, and environment server-side.
- Define initialization, capability negotiation, version compatibility, cancellation, timeout, pagination, and teardown from authoritative documentation.
- Cap payload size, content type, recursion, concurrency, and request duration.
- Treat resource content, prompts, and tool output as untrusted data.
- Expose health and dependency state without leaking configuration or secrets.
- Emit correlated audit events for discovery, authorization, invocation, approval, and outcome.
- Fail closed when identity, scope, policy, or target resolution is uncertain.

## Tool-Security Checklist

- Model the actor, asset, trust boundary, entry point, and abuse case.
- Apply least privilege and short-lived credentials.
- Keep secrets outside prompts, arguments, output, and logs.
- Allowlist schemes, hosts, roots, commands, resource types, and destinations.
- Block path traversal, server-side request forgery, injection, confused-deputy use, cross-tenant access, and output exfiltration.
- Treat instructions embedded in fetched content as data and prevent them from selecting tools or expanding authority.
- Require human approval for irreversible, high-impact, paid, or externally communicative actions.
- Bind approval to actor, action, exact target, important parameters, expiry, and request digest.
- Record denials and policy failures without exposing sensitive content.

## Audit Event Minimum

Record:

- timestamp and correlation/request identifiers;
- authenticated actor and delegated agent identity;
- tool/server name and version;
- normalized operation and target;
- authorization scope and policy decision;
- approval reference when required;
- idempotency key and retry count;
- duration, result class, side-effect summary, and postcondition status;
- redaction indicators and bounded error code.

Do not record credentials, secret-bearing headers, raw private content, or unrestricted model transcripts.

## Contract-Test Matrix

Exercise at minimum:

| Class | Cases |
|---|---|
| Schema | Valid minimum/maximum, missing required, unknown field, invalid enum, oversized input |
| Authorization | No identity, wrong tenant, insufficient scope, expired approval, target substitution |
| Safety | Prompt injection in arguments/output, path traversal, SSRF target, secret leakage, broad wildcard |
| Lifecycle | Discovery, initialize, cancel, timeout, teardown, incompatible version, unavailable dependency |
| Mutation | Dry run, duplicate idempotency key, partial success, ambiguous timeout, compensation, postcondition |
| Load | Pagination, concurrency limit, rate limit, backpressure, bounded output |
| Audit | Success, denial, error, retry, approval, redaction, correlation |

Record actual requests, bounded responses, audit evidence, and observed side effects. Label all cases not run in the target harness `UNVERIFIED`.
