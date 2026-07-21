---
applyTo: tests/**/*.py
---
# Test Task Rules

## Scope
Use for unit tests and regression coverage in this repository.

## Rules
- Prefer focused tests over broad snapshots.
- For infra changes, assert concrete CloudFormation properties.
- For Lambda logic, cover input validation and error responses.
- Keep tests deterministic; avoid real AWS calls.

## Validation
- Run `pytest` after test edits.
- Include at least one regression test for each bug fix.
- Update existing tests instead of duplicating equivalent cases.
