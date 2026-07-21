---
applyTo: app.py,video_content_delivery/*stack.py,video_content_delivery/*construct.py,video_content_delivery/**/*.py
---
# Infra Task Rules (CDK)

## Scope
Use for CDK resources, IAM, API Gateway, S3, DynamoDB, and deployment-impacting changes.

## Rules
- Keep least-privilege IAM; never use wildcard permissions without explicit need.
- Preserve resource logical intent and avoid accidental replacement risks.
- Prefer additive and backward-compatible infra updates.
- Validate CORS consistency between API Gateway and S3.
- Keep environment variables explicit and documented for Lambdas.

## Validation
- Run `cdk diff` and explain resource deltas.
- Run `cdk synth` before finalizing.
- Call out rollback considerations for destructive changes.
