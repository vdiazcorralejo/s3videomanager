# Copilot Fast Mode (Ultra Short)

Use this profile when you need speed and minimal context.

- Stack: AWS CDK (Python), S3 + DynamoDB + Lambda + API Gateway.
- Keep changes minimal and backward-compatible.
- Preserve Lambda response contract: `statusCode`, `headers`, `body`.
- No hardcoded secrets; use env vars.
- IAM must be least-privilege.
- For infra edits: run `cdk diff` and `cdk synth`.
- For code edits: run `pytest` when tests are affected.
- Explain risk and rollback if infra resources change.
