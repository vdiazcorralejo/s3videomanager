---
applyTo: video_content_delivery/src/lambda/**/*.py
---
# Lambda Task Rules

## Scope
Use for Lambda handlers, auth logic, URL signing, and video processing logic.

## Rules
- Preserve handler signatures and event contract compatibility.
- Return stable JSON shape: `statusCode`, `headers`, `body`.
- Do not hardcode secrets, tokens, bucket names, or table names.
- Prefer explicit exceptions and actionable log messages.
- Keep cold-start impact low; avoid heavy imports unless needed.

## Validation
- Test happy path plus at least one failure path.
- Confirm CORS headers when endpoint behavior is modified.
- Verify IAM/env dependencies required by the handler.
