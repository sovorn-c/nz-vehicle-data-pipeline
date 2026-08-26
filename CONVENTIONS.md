# Conventions

## Conventional Commits and Versioning

All commits MUST follow Conventional Commits 1.0.0.
Releases MUST follow Semantic Versioning 2.0.0.

Use `<type>(<scope>): <description>` for every commit subject.
Use `feat` for features and `fix` for defects.
Use `BREAKING CHANGE:` or `!` for incompatible changes.
Do NOT add AI attribution footers.

## Git Workflow

Use feature branches for production work.
Keep `main` green and releasable.
Use `solo-git` workflow mode from `specs/state.yaml`.
Run Preflight before integration.
Check remote CI with `gh pr checks` when a pull request exists.
NEVER push directly to protected branches.
NEVER run destructive Git commands without explicit user approval.

## Agent Workflow

Read `AGENTS.md` and `specs/` before changing code.
Route product work through bigpowers skills.
Write approved scope before implementation tasks.
Write runnable verification commands into every implementation plan.
Use TDD for non-trivial behavior and defect fixes.
Keep planning output under `specs/`.

## Always Green and Shift Left

Preflight defines the complete local verification stack.
Preflight MUST pass before implementation, verification, or integration advances.
CI MUST pass before integration when remote CI applies.
A reproducible gate failure blocks forward work.
Fix failures while feedback remains cheap.

### Preflight

Run this command after the Python package scaffold exists:

```bash
uv run ruff check . && uv run mypy src tests && uv run pytest && uv build
```

## Discovered Defects

Treat every reproducible gate failure as a defect.
Use this mandatory fix-or-log ladder:

1. Use `quick-fix` for eligible data-only changes.
2. Use `fix-bug` when logic or investigation is required.
3. Log a bug only when reproduction remains blocked.

Keep discovered fixes in separate Conventional Commits.
Do NOT continue while Preflight or CI remains red.

### Banned Failure Dismissals

| Do not say | Required action |
|---|---|
| Pre-existing issue | Reproduce, fix, or log the defect. |
| Unrelated to this session | Reproduce, fix, or log the defect. |
| Not introduced by this change | Prove with isolation, then fix or log. |
| Out of scope | Stop forward work and apply the ladder. |

## Planning Cockpit

All planning output MUST live under `specs/`.
`specs/state.yaml` owns active workflow state and handoff signals.
`specs/release-plan.yaml` owns epic ordering and release intent.
`specs/execution-status.yaml` owns story and epic status.
`specs/product/` owns vision, scope, and glossary artifacts.
`specs/epics/` owns story requirements and implementation tasks.
`specs/tech-architecture/` owns architecture and quality plans.
`specs/verifications/` owns verification evidence.
`specs/bugs/` owns defect investigations and registry data.
Do NOT duplicate status across cockpit files.

## Architecture

Use four explicit layers:

1. Connectors ingest source-specific records.
2. Normalization validates and maps source fields.
3. Reconciliation creates canonical records and evidence history.
4. API and persistence expose validated canonical results.

Dependencies MUST point inward toward domain models.
Keep external SDK types inside connector boundaries.
Keep reconciliation deterministic and independently testable.
Use interfaces only where multiple implementations exist.
Do NOT add abstractions for future needs.

## Python Style

Target Python 3.12 or newer.
Use a `src/` package layout.
Use explicit types on public functions.
Use strict Pydantic models at trust boundaries.
Use early returns instead of nested control flow.
Keep functions focused and modules cohesive.
Prefer standard library features before dependencies.
Delete dead code instead of commenting it out.
Use Ruff for formatting and lint rules.
Use mypy strict mode.

## Data Integrity

Preserve immutable raw inputs before transformation.
Track source, record identifier, and retrieval time for every field.
Archive replaced provenance instead of deleting it.
Record both values when trusted sources disagree.
Apply explicit deterministic conflict rules.
Store confidence calculations with their inputs.
Label synthetic data in files, fixtures, APIs, and demonstrations.
NEVER imply synthetic records came from official systems.
NEVER store real PPSR, stolen, or write-off details without authorization.

## API and Error Contracts

Validate all request and response bodies.
Return structured errors with actionable messages.
Include the offending value only when disclosure is safe.
Use idempotency for repeatable ingestion operations.
Bound pagination and bulk ingestion sizes.
Do NOT leak stack traces or credentials through APIs.

## Tests

Tests MUST be Fast, Independent, Repeatable, Self-Validating, and Timely.
Test behavior through public interfaces.
Add one focused test for every non-trivial branch.
Add a regression test for every defect fix.
Cover empty, minimum, maximum, and malformed inputs.
Use fake connectors for external I/O.
Keep unit tests offline and deterministic.
Use integration tests for PostgreSQL and HTTP boundaries.
Do NOT skip tests without a documented unresolved ambiguity.

## Logging

Use structured JSON for application logs.
Include source, operation, record identifier, and correlation identifier.
Redact secrets and personal data before logging.
Do NOT log complete credentials, tokens, or sensitive source payloads.

## Defensive Code

Implement these approved defensive categories:

- Rate limit external API requests.
- Retry transient failures with bounded exponential backoff.
- Apply explicit timeouts to network and database operations.
- Degrade gracefully when optional sources are unavailable.

Do NOT add circuit breakers before failure volume justifies them.
