# Copilot Instructions: video-content-delivery

## Goal
Build and maintain a serverless video delivery backend on AWS CDK (Python) with secure uploads/downloads and predictable operations.

## Instruction Profiles
- Base profile (this file): always-on, minimal global context.
- Task-specific profiles:
  - `.github/instructions/infra.instructions.md` for CDK/IAM/API/S3/DynamoDB changes.
  - `.github/instructions/lambda.instructions.md` for Lambda handlers and API behavior.
  - `.github/instructions/tests.instructions.md` for test creation and updates.
- Fast profile:
  - `.github/copilot-instructions.fast.md` for low-token, high-speed sessions.

## Routing
- If task touches infrastructure/resources, prioritize infra profile.
- If task touches handler/runtime logic, prioritize lambda profile.
- If task is test-focused, prioritize tests profile.
- If task is simple or repetitive, use fast profile.
- When multiple profiles apply, combine only the minimum required sections.

## Architecture (High Signal)
- S3 bucket: stores videos, versioned, upload events trigger processing for `.mp4`.
- DynamoDB table: `listOfVideoFiles` with PK `videoList` and SK `Date`.
- Lambda functions:
  - presigned URL generation
  - video processing and playlist generation
  - API Gateway token authorizer
- API Gateway: authenticated endpoint for URL generation with CORS for local frontend.

## Source of Truth
- CDK app entry: `app.py`
- Stack and constructs: `video_content_delivery/`
- Lambdas: `video_content_delivery/src/lambda/`
- Unit tests: `tests/unit/test_video_content_delivery_stack.py`

## Coding Rules
- Keep changes minimal and scoped; do not refactor unrelated code.
- Preserve existing public interfaces unless change is required.
- Prefer explicit error handling with stable JSON responses (`statusCode`, `headers`, `body`).
- Keep IAM least-privilege; grant only required actions/resources.
- Use environment variables for runtime config (`TABLE_NAME`, `BUCKET_NAME`, `REGION`).
- Maintain CORS consistency between API Gateway and S3 config.
- Add or update tests for behavioral changes in infra or Lambda logic.

## Workflow
- Setup: create venv, install `requirements.txt` and `requirements-dev.txt`.
- Validate infra changes with:
  - `cdk diff`
  - `cdk synth`
- Run tests with `pytest`.
- Prefer fixing root causes over patching symptoms.

## Security and Operations
- Never hardcode secrets or tokens.
- Keep S3 private; rely on presigned URLs.
- Validate auth paths when touching API or authorizer logic.
- Check CloudWatch logs for runtime debugging and regressions.

## PR/Change Quality Checklist
- What changed and why is clear.
- Impacted AWS resources are identified.
- Backward compatibility is considered.
- Tests or validation steps are included.
- Risks and rollback notes are stated for infra-impacting changes.
