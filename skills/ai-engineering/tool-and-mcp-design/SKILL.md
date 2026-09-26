---
name: tool-and-mcp-design
description: "Use when designing agent capabilities — tool schemas, MCP servers, harness integration, and the distinctions and selection between skills, plugins, subagents, and hooks; includes tool-security (scoping, audit, injection defenses). Do NOT use for context/prompt layout (see skill context-engineering)."
---

# Tool and MCP Design

## Operating Boundary

- Own capability-surface selection, tool contracts, MCP boundaries, harness integration, permissions, audit, and tool-output injection defenses.
- For prompt and context placement, see skill context-engineering.
- For scheduled or unattended execution, see skill ai-automation.
- For deployed-service operations, see skill production-ops.
- For current protocol, SDK, or platform claims, see skill ai-research.

## Decision Workflow

1. **Define the capability contract.** Record the actor, intended outcome, resources, trust boundary, side effects, latency, volume, and forbidden actions.
2. **Select the surface.** Choose a tool, MCP server, skill, plugin, subagent, hook, or harness responsibility from [mcp-tool-design.md](references/mcp-tool-design.md). Use the smallest surface that owns the concern without hiding authority.
3. **Design the operation.** Give each tool one bounded action, explicit inputs and outputs, stable errors, resource limits, and a side-effect class. Separate reads from writes and reversible changes from irreversible actions.
4. **Constrain authority.** Apply least-privilege scopes, tenant and resource binding, target allowlists, approval gates, time bounds, secret isolation, and server-side authorization.
5. **Defend the boundary.** Treat arguments and returned content as untrusted data. Validate structure and semantics, delimit content, reject embedded instructions, redact sensitive data, and cap size and recursion.
6. **Integrate lifecycle behavior.** Define discovery, connection, timeout, cancellation, retry, idempotency, pagination, concurrency, version negotiation, and teardown behavior.
7. **Make actions auditable.** Emit actor, authorization, tool/version, normalized target, request identifier, approval evidence, outcome, and redacted error data without logging secrets.
8. **Exercise the contract.** Test valid, invalid, unauthorized, duplicate, partial-failure, timeout, injection, oversized, and unavailable-dependency paths in the actual harness.

## Required Deliverable

Return:

- the selected capability surface and rejected alternatives;
- trust-boundary and data-flow notes;
- bounded input/output/error schemas;
- permission, approval, and side-effect classifications;
- lifecycle, idempotency, and audit contracts;
- injection and data-egress controls;
- contract-test cases and observed evidence;
- every unexercised claim labeled `UNVERIFIED`.

## Decision Rules

- Prefer several narrow tools over one mode-switched tool with broad authority.
- Keep authorization and validation server-side; never rely on prompt instructions as an access-control boundary.
- Require explicit approval tied to the exact target and action before irreversible or high-impact writes.
- Make retries safe by design or declare the operation non-retryable.
- Return typed, bounded results and stable machine-readable errors; keep verbose diagnostics behind controlled references.
- Reject capability surfaces whose permissions, ownership, or audit path cannot be explained.

## Failure Modes

- Do not expose generic shell, arbitrary URL fetch, raw database execution, or unrestricted file access when a bounded operation suffices.
- Do not combine discovery, approval, mutation, and verification into an opaque call.
- Do not trust tool descriptions, arguments, or outputs merely because they are machine generated.
- Do not leak credentials, tokens, private payloads, or raw sensitive content into logs or model context.
- Do not retry non-idempotent mutations after an ambiguous outcome without reconciliation.
- Do not claim MCP or harness compatibility from schema inspection alone.

## Tool Requirements & Degradation

- Require access to the target harness/runtime, authoritative protocol or SDK documentation, schema validation, and a test endpoint or sandbox for executable compatibility claims.
- Require authorization-policy and audit-sink visibility for security and traceability claims.
- When protocol versions, platform support, transports, or APIs may have changed, see skill ai-research.
- If the runtime or sandbox is unavailable, deliver schemas, threat controls, and contract tests but label discovery, invocation, cancellation, and error behavior `UNVERIFIED`.
- If authoritative protocol documentation is unavailable, refuse to invent fields or lifecycle semantics; identify the exact document or human decision required.
- If authorization or audit facilities are unavailable, do not downgrade them to prompt rules. Mark the design unsafe for writes and restrict the proposed capability to read-only or no execution.
