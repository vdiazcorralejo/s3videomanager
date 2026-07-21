# S3 Video Manager

A serverless video content delivery system built with AWS CDK in Python. This project implements a secure and scalable architecture for uploading, storing, processing, and streaming video content using AWS services.

## Architecture Overview

This is a serverless video content delivery system built with AWS CDK in Python. The core architecture includes:

- **S3 Bucket** (`video-content-delivery-bucket`): Stores video files with versioning; triggers video processing on `.mp4` uploads
- **DynamoDB Table** (`listOfVideoFiles`): Tracks video metadata with partition key `videoList` (string) and sort key `Date` (string)
- **Lambda Functions**:
  - `GetPresignedUrlFunction`: Generates secure upload/download URLs (see `video_content_delivery/src/lambda/generate_url_pre/index.py`)
  - `ProcessVideoFunction`: Processes uploaded videos and generates M3U playlists (see `video_content_delivery/src/lambda/process_video/index.py`)
  - `apigatewayAuthorizer`: Custom token-based authentication (see `video_content_delivery/src/lambda/auth/index.py`)
- **API Gateway**: REST API with custom authorizer; `/geturl` endpoint for presigned URLs with CORS support for `http://localhost:3000`

Data flows from client → API Gateway (authenticated) → Lambda → S3/DynamoDB, with S3 events triggering video processing.

## Key Patterns

- **Constructs for Modularity**: Use `LambdaConstruct`, `DynamoTable`, `ApiGatewayConstruct` for reusable AWS resources (see `video_content_delivery/` directory)
- **Environment Variables**: Pass config like `TABLE_NAME`, `BUCKET_NAME`, `REGION` to Lambdas (example in `video_content_delivery_stack.py`)
- **Permissions**: Grant minimal IAM permissions; e.g., `bucket.grant_read_write(lambda_function)` for S3 access
- **Logging**: All Lambdas and API Gateway log to CloudWatch with 1-week retention (see `LambdaConstruct` and `ApiGatewayConstruct`)
- **CORS Configuration**: S3 bucket allows `PUT`, `GET`, `POST` from `http://localhost:3000` with exposed `ETag` header

## Development Workflows

- **Setup**: Create venv with `python -m venv .venv`, activate, install deps from `requirements.txt` and `requirements-dev.txt`
- **Build/Synth**: Use `cdk synth` to generate CloudFormation templates (app defined in `app.py`)
- **Deploy**: Run `cdk deploy` to provision AWS resources; outputs include API Gateway URL
- **Test**: Execute unit tests with `pytest` (CDK assertions in `tests/unit/test_video_content_delivery_stack.py` verify resource properties)
- **Debug**: Check CloudWatch logs for Lambda executions; use `cdk diff` to preview changes before deploy

## AI Prompt Tag Convention (Team)

Use one or more tags at the top of every AI coding request to keep context focused and reduce token usage.

- `#infra`: CDK/IAM/API Gateway/S3/DynamoDB changes
- `#lambda`: Lambda handler/runtime behavior changes
- `#test`: Unit tests and regression coverage changes
- `#fast`: Small/repetitive tasks that should use minimal context

Tag to profile mapping:

- `#infra` -> `.github/instructions/infra.instructions.md`
- `#lambda` -> `.github/instructions/lambda.instructions.md`
- `#test` -> `.github/instructions/tests.instructions.md`
- `#fast` -> `.github/copilot-instructions.fast.md`

Prompt examples:

- `#infra #test Add S3 lifecycle rule for processed files and include CDK assertions.`
- `#lambda Fix validation for missing video key and keep response contract stable.`
- `#test Add regression test for token authorizer invalid token branch.`
- `#fast Rename one variable in process_video handler without refactoring.`

## Conventions

- **Naming**: Lambda functions use descriptive names like `GetPresignedUrlFunction`; table name matches construct ID
- **Error Handling**: Lambdas return JSON responses with `statusCode`, `headers` (including CORS), and `body` (see `generate_url_pre/index.py`)
- **Dependencies**: Use `boto3` for AWS SDK calls in Lambdas; CDK constructs import from `aws_cdk`
- **File Structure**: Lambda code in `video_content_delivery/src/lambda/{function_name}/index.py`; tests mirror stack structure

## Integration Points

- **External Services**: Relies on AWS S3, DynamoDB, Lambda, API Gateway, CloudWatch; no third-party APIs
- **Cross-Component Communication**: API Gateway integrates with Lambdas via `LambdaIntegration`; S3 events notify Lambdas via `LambdaDestination`
- **Security**: Custom authorizer validates tokens; S3 blocks public access; pre-signed URLs enable secure client-side uploads/downloads

## Prerequisites

- AWS CLI configured
- Python 3.12 or higher
- AWS CDK CLI
- Node.js (for CDK)

## Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

## Usage

- **Synth**: `cdk synth`
- **Deploy**: `cdk deploy`
- **Test**: `pytest`

## Features

- Secure video upload/download via pre-signed URLs
- Custom token-based authorization
- Automatic video processing on upload
- M3U playlist generation
- CORS support for web applications
- Comprehensive logging system
- Automatic cleanup of resources on stack deletion
