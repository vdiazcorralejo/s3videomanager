<div align="center">
  <br/>
  <h1>🎬 S3 Video Manager</h1>
  <p>
    <strong>Serverless Video Content Delivery System</strong>
  </p>
  <p>
    Built with <a href="https://aws.amazon.com/cdk/">AWS CDK</a> (Python) •
    Serverless • Secure • Scalable
  </p>
  <br/>

  [![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
  [![AWS CDK](https://img.shields.io/badge/aws--cdk-2.173.2-orange.svg)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

  <br/>
</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Development](#-development)
- [Testing](#-testing)
- [Security](#-security)
- [Cost Optimization](#-cost-optimization)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**S3 Video Manager** is a production-ready, serverless video content delivery system built entirely with AWS CDK in Python. It provides a secure, scalable, and cost-effective solution for uploading, storing, managing, and streaming video content using native AWS services.

The system is designed for **progressive download** scenarios — ideal for legacy applications (e.g., Windows Media Player embedded in MFC C++ apps), digital signage, or any environment where HLS/DASH streaming is unnecessary overhead.

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Serverless First** | Zero servers to manage; auto-scaling Lambda functions |
| **Security by Design** | Presigned URLs, custom JWT authorizer, private S3 bucket |
| **Cost Optimized** | S3 Intelligent-Tiering, lifecycle policies, no unnecessary transcoding |
| **Infrastructure as Code** | Full AWS infrastructure defined with CDK (Python) |
| **Observability** | CloudWatch logs, metrics, and structured logging throughout |

---

## 🏗 Architecture

### High-Level Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────▶│  API Gateway  │────▶│  Custom Authorizer│
│  (Web/MFC)  │     │  (REST API)   │     │  (JWT Token)     │
└─────────────┘     └──────────────┘     └─────────────────┘
       │                    │                       │
       │                    ▼                       │
       │            ┌──────────────┐                │
       └───────────▶│   Lambda     │◀───────────────┘
                    │  Functions   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │    S3    │ │ DynamoDB │ │CloudWatch│
       │  Bucket  │ │  Table   │ │   Logs   │
       └──────────┘ └──────────┘ └──────────┘
```

### Component Breakdown

#### 🪣 S3 Bucket (`video-content-delivery-bucket`)
- Stores video files with **versioning enabled**
- **CORS configured** for `http://localhost:3000` (PUT, GET, POST)
- **Blocked public access** — all access via presigned URLs only
- **Lifecycle rules**: Intelligent-Tiering immediately, Glacier Instant Retrieval after 90 days
- Triggers video processing Lambda on `.mp4` uploads

#### 🗄️ DynamoDB Table (`listOfVideoFiles`)
- **Partition key**: `videoList` (String)
- **Sort key**: `videoId` (String)
- **Billing mode**: Pay-per-request (auto-scaling)
- **GSIs**:
  - `StatusIndex`: Query by status (`ready`, `processing`, `failed`)
  - `UploadDateIndex`: Sort by upload date (recent-first)

#### ⚡ Lambda Functions

| Function | Runtime | Memory | Trigger | Purpose |
|----------|---------|--------|---------|---------|
| `GetPresignedUrlFunction` | Python 3.12 | 256 MB | API Gateway | Generate upload/download/playback URLs |
| `ProcessVideoFunction` | Python 3.12 | 512 MB | S3 Event | Process uploaded videos, store metadata |
| `apigatewayAuthorizer` | Python 3.12 | 256 MB | API Gateway | Custom JWT token validation |
| `CatalogFunction` | Python 3.12 | 256 MB | API Gateway | Paginated video catalog with metadata |
| `TokenGeneratorFunction` | Python 3.12 | 256 MB | API Gateway | Generate JWT tokens for auth |

#### 🌐 API Gateway (`MyVideoFilesAPI`)
- **Type**: REST API (Regional)
- **Authentication**: Custom JWT authorizer on protected endpoints
- **CORS**: Configured for `http://localhost:3000`
- **Logging**: CloudWatch with 1-week retention, structured JSON format
- **Throttling**: 100 req/s rate limit, 200 burst capacity
- **Error responses**: Custom gateway responses for 401, 403, 429, 4xx, 5xx

### Data Flow

1. **Client** authenticates via `POST /token` → receives JWT
2. **Client** requests `GET /catalog` with JWT → receives paginated video list
3. **Client** selects a video → requests `GET /geturl?action=get_playback_url&key=<file>` with JWT
4. **API Gateway** validates JWT via custom authorizer
5. **Lambda** generates a time-limited presigned S3 URL
6. **Client** streams/downloads video directly from S3 using the presigned URL
7. **On upload**: S3 event triggers `ProcessVideoFunction` → metadata stored in DynamoDB

---

## ✨ Features

### ✅ Current

- **🔐 Secure Authentication**: Custom JWT-based token authorization
- **📤 Secure Uploads**: Presigned URLs for direct-to-S3 uploads
- **📥 Secure Downloads**: Time-limited download URLs
- **▶️ Optimized Playback**: Presigned URLs with correct content types and inline disposition
- **📋 Video Catalog**: Paginated catalog with metadata, filtering by status
- **🖼️ Thumbnail Support**: Placeholder thumbnails with infrastructure for real thumbnails
- **📊 Observability**: CloudWatch logs, metrics, and structured logging
- **🌐 CORS Support**: Configured for web application development
- **💰 Cost Optimization**: S3 lifecycle rules, Intelligent-Tiering, pay-per-request DynamoDB
- **🧪 Comprehensive Tests**: CDK assertions + Lambda unit tests

### 🔜 Planned

- [ ] Externalize JWT secrets to AWS Secrets Manager
- [ ] S3 → SQS → Lambda for resilient processing
- [ ] CloudWatch alarms and operational dashboard
- [ ] WAF integration for API Gateway
- [ ] Multi-environment deployment (dev/staging/prod)
- [ ] CI/CD pipeline with CDK Pipelines
- [ ] Real thumbnail generation with FFmpeg Lambda layer
- [ ] ARM64 architecture for Lambda cost reduction
- [ ] CDK Nag compliance checks

---

## 📁 Project Structure

```
├── app.py                                    # CDK app entry point
├── cdk.json                                  # CDK configuration
├── requirements.txt                          # Production dependencies
├── requirements-dev.txt                      # Development dependencies
├── source.bat                                # Windows venv activation helper
│
├── video_content_delivery/                   # CDK infrastructure
│   ├── __init__.py
│   ├── video_content_delivery_stack.py       # Main stack definition
│   ├── lambda_construct.py                   # Reusable Lambda construct
│   ├── dynamo_table.py                       # DynamoDB table construct
│   ├── apigateway_construct.py               # API Gateway construct
│   │
│   └── src/lambda/                           # Lambda function code
│       ├── auth/
│       │   └── index.py                      # JWT token authorizer
│       ├── catalog/
│       │   └── index.py                      # Video catalog with pagination
│       ├── generate_url_pre/
│       │   └── index.py                      # Presigned URL generation
│       ├── process_video/
│       │   └── index.py                      # Video processing on upload
│       └── token_generator/
│           └── index.py                      # JWT token generation
│
├── tests/                                    # Test suite
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_video_content_delivery_stack.py  # CDK infrastructure tests
│       └── test_lambda_handlers/
│           ├── test_generate_url_pre.py      # Presigned URL handler tests
│           └── test_process_video.py         # Video processing handler tests
│
├── docs/
│   ├── PLAN_MEJORA_PRODUCCION.md             # Production improvement plan (Spanish)
│   └── PLAN_CDN_CLIENTES_GRANDES.md          # Detailed CDN distribution plan for large clients
│
└── .github/
    ├── copilot-instructions.md               # AI coding assistant instructions
    ├── copilot-instructions.fast.md           # Fast mode instructions
    └── instructions/
        ├── infra.instructions.md             # Infrastructure task profile
        ├── lambda.instructions.md            # Lambda task profile
        └── tests.instructions.md             # Test task profile
```

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

| Tool | Version | Purpose |
|------|---------|---------|
| [Python](https://www.python.org/downloads/) | 3.12+ | Runtime for CDK and Lambdas |
| [AWS CLI](https://aws.amazon.com/cli/) | Latest | AWS account interaction |
| [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html) | 2.x | Infrastructure deployment |
| [Node.js](https://nodejs.org/) | 18+ | Required by CDK CLI |
| [Git](https://git-scm.com/) | Latest | Version control |

### AWS Account Setup

1. Configure AWS CLI with your credentials:
   ```bash
   aws configure
   ```

2. Bootstrap CDK in your target region (required once per account/region):
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION
   ```

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/s3-video-manager.git
cd s3-video-manager
```

### 2. Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (testing, etc.)
pip install -r requirements-dev.txt
```

### 4. Synthesize CloudFormation Template

```bash
cdk synth
```

This generates the CloudFormation template in the `cdk.out/` directory without deploying.

### 5. Deploy to AWS

```bash
cdk deploy
```

After deployment, you'll see outputs like:
```
Outputs:
VideoContentDeliveryStack.ApiGatewayUrl = https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/
VideoContentDeliveryStack.GetUrlEndpoint = https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/geturl
VideoContentDeliveryStack.CatalogEndpoint = https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/catalog
VideoContentDeliveryStack.BucketName = video-content-xxxxxxxxxxxx-eu-west-1
VideoContentDeliveryStack.DynamoDBTableName = listOfVideoFiles
```

### 6. Generate an Authentication Token

```bash
# Replace with your API Gateway URL
API_URL="https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod"

# Generate a token (requires token_generator Lambda to be exposed)
curl -X POST "$API_URL/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo-user"}'
```

> **Note**: The `POST /token` endpoint needs to be connected in API Gateway. For development, you can use the default token `valid-token` with the `Authorization` header.

---

## 📖 Usage

### Authentication Flow

All protected endpoints require a JWT token in the `Authorization` header:

```bash
TOKEN="valid-token"  # Replace with your JWT token

curl -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/catalog"
```

### Upload a Video

```bash
# 1. Get a presigned upload URL
UPLOAD_URL=$(curl -s -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/geturl?action=get_upload_url&key=videos/my-video.mp4" \
  | jq -r '.url')

# 2. Upload directly to S3 using the presigned URL
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: video/mp4" \
  --data-binary @my-video.mp4
```

### Browse the Catalog

```bash
# List all ready videos (paginated, 20 per page)
curl -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/catalog?status=ready&pageSize=20"

# Paginate using lastEvaluatedKey
curl -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/catalog?lastEvaluatedKey=<base64_token>"
```

### Play a Video

```bash
# Get a playback URL (24-hour expiration, inline content disposition)
PLAYBACK_URL=$(curl -s -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/geturl?action=get_playback_url&key=videos/my-video.mp4" \
  | jq -r '.url')

# Stream the video (e.g., with ffplay, VLC, or embed in a player)
ffplay "$PLAYBACK_URL"
```

### Download a Video

```bash
# Get a download URL (5-minute expiration)
DOWNLOAD_URL=$(curl -s -H "Authorization: $TOKEN" \
  "https://xxxxxxxxxx.execute-api.eu-west-1.amazonaws.com/prod/geturl?action=get_download_url&key=videos/my-video.mp4" \
  | jq -r '.url')

# Download the file
curl -o my-video.mp4 "$DOWNLOAD_URL"
```

---

## 📚 API Reference

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/geturl` | ✅ JWT | Generate presigned URLs (upload/download/playback) |
| `GET` | `/catalog` | ✅ JWT | Paginated video catalog with metadata |
| `POST` | `/token` | ❌ | Generate JWT authentication token |
| `OPTIONS` | `/*` | ❌ | CORS preflight (auto-configured) |

### Query Parameters

#### `GET /geturl`

| Parameter | Required | Values | Description |
|-----------|----------|--------|-------------|
| `action` | ✅ | `get_upload_url`, `get_download_url`, `get_playback_url`, `list` | Type of URL to generate |
| `key` | ✅ (except `list`) | S3 object key | Path to the video file |

#### `GET /catalog`

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `pageSize` | ❌ | `20` | Items per page (max: 20) |
| `lastEvaluatedKey` | ❌ | — | Base64-encoded pagination token |
| `status` | ❌ | `ready` | Filter by processing status |

### Response Format

All endpoints return a consistent JSON structure:

```json
{
  "statusCode": 200,
  "headers": {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json"
  },
  "body": "{ ... }"
}
```

#### Success: `GET /geturl?action=get_playback_url`

```json
{
  "url": "https://s3.eu-west-1.amazonaws.com/...?X-Amz-Signature=...",
  "contentType": "video/mp4",
  "expiresIn": 86400,
  "mode": "playback"
}
```

#### Success: `GET /catalog`

```json
{
  "videos": [
    {
      "id": "vid-abc123def456",
      "title": "Promo Summer 2026",
      "fileName": "promo-summer-2026.mp4",
      "status": "ready",
      "durationSeconds": 32,
      "sizeBytes": 52428800,
      "thumbnailUrl": "https://via.placeholder.com/320x180?text=Video",
      "uploadDate": "2026-07-10T14:30:00+00:00",
      "contentType": "video/mp4"
    }
  ],
  "pageSize": 20,
  "lastEvaluatedKey": null
}
```

#### Error

```json
{
  "error": "Missing key parameter"
}
```

---

## 🛠 Development

### AI-Assisted Development

This project includes **AI prompt tag conventions** for efficient AI-assisted coding. Use tags at the top of your prompts to focus context:

| Tag | Profile | Scope |
|-----|---------|-------|
| `#infra` | `infra.instructions.md` | CDK/IAM/API Gateway/S3/DynamoDB |
| `#lambda` | `lambda.instructions.md` | Lambda handler/runtime behavior |
| `#test` | `tests.instructions.md` | Unit tests and regression coverage |
| `#fast` | `copilot-instructions.fast.md` | Small/repetitive tasks (minimal context) |

**Examples:**
- `#infra #test Add S3 lifecycle rule for processed files and include CDK assertions.`
- `#lambda Fix validation for missing video key and keep response contract stable.`
- `#test Add regression test for token authorizer invalid token branch.`
- `#fast Rename one variable in process_video handler without refactoring.`

### Useful Commands

```bash
# Preview infrastructure changes
cdk diff

# Synthesize CloudFormation template
cdk synth

# Deploy stack
cdk deploy

# Destroy stack (⚠️ careful with production data)
cdk destroy

# Run tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_video_content_delivery_stack.py
```

### Code Conventions

- **Naming**: Lambda functions use descriptive names like `GetPresignedUrlFunction`; table name matches construct ID
- **Error Handling**: All Lambdas return JSON responses with `statusCode`, `headers` (including CORS), and `body`
- **Dependencies**: Use `boto3` for AWS SDK calls in Lambdas; CDK constructs import from `aws_cdk`
- **Environment Variables**: Pass config like `TABLE_NAME`, `BUCKET_NAME`, `REGION` to Lambdas
- **Permissions**: Grant minimal IAM permissions; avoid `grant_full_access()` in production

---

## 🧪 Testing

### Test Structure

```
tests/
├── unit/
│   ├── test_video_content_delivery_stack.py    # CDK infrastructure assertions
│   └── test_lambda_handlers/
│       ├── test_generate_url_pre.py            # Presigned URL handler tests
│       └── test_process_video.py               # Video processing handler tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage (if pytest-cov is installed)
pytest --cov=video_content_delivery

# Run infrastructure tests only
pytest tests/unit/test_video_content_delivery_stack.py -v

# Run Lambda handler tests only
pytest tests/unit/test_lambda_handlers/ -v
```

### What's Tested

- **Infrastructure Tests**: Verify S3 bucket configuration, DynamoDB table schema, Lambda function properties, API Gateway resources, and authorizer setup
- **Lambda Handler Tests**: Validate presigned URL generation (playback vs download, content types, expiration), video processing logic (catalog item creation, non-MP4 skipping), and error handling

---

## 🔒 Security

### Current Security Measures

| Measure | Implementation |
|---------|---------------|
| **Private S3 Bucket** | `BlockPublicAccess.BLOCK_ALL` — no public access |
| **Presigned URLs** | Time-limited URLs for all S3 operations |
| **JWT Authentication** | Custom authorizer validates tokens on every request |
| **CORS Restrictions** | Limited to `http://localhost:3000` |
| **Input Validation** | Key sanitization (no path traversal), extension whitelist |
| **IAM Least Privilege** | Granular permissions per Lambda function |
| **API Throttling** | 100 req/s rate limit, 200 burst capacity |
| **CloudWatch Logging** | All API and Lambda activity logged |

### Security Best Practices

- **Never hardcode secrets** — use environment variables or AWS Secrets Manager
- **Validate all inputs** — sanitize keys, check extensions, limit sizes
- **Use presigned URLs** — never expose S3 bucket directly
- **Rotate tokens regularly** — JWT tokens should have short expiration
- **Monitor access patterns** — use CloudWatch Logs and metrics

### Planned Security Enhancements

- [ ] Externalize JWT secret to AWS Secrets Manager
- [ ] Change `RemovalPolicy` from `DESTROY` to `RETAIN` for production
- [ ] Replace `grant_full_access()` with granular `grant_read_write_data()`
- [ ] Add AWS WAF with managed rule sets
- [ ] Enable S3 server access logs
- [ ] Enforce SSL for all S3 operations

---

## 💰 Cost Optimization

### Current Optimizations

| Feature | Savings |
|---------|---------|
| **S3 Intelligent-Tiering** | Auto-optimizes storage costs for unpredictable access patterns |
| **Glacier Instant Retrieval (90 days)** | Lowers cost for older content with retrieval flexibility |
| **DynamoDB Pay-per-Request** | No provisioned capacity costs; scales with usage |
| **Lambda on-demand** | No idle compute costs; pay only for execution time |
| **No unnecessary transcoding** | MP4 progressive download avoids MediaConvert costs |
| **No mandatory CDN** | S3 direct access avoids CloudFront costs when not needed |

### Estimated Monthly Costs

| Service | Conservative (500 videos, 50 screens) | Optimistic (200 videos, 10 screens) |
|---------|--------------------------------------|-------------------------------------|
| S3 Storage | ~$2.30 | ~$2.30 |
| S3 Data Transfer | ~$27.00 | ~$5.40 |
| S3 Requests | ~$1.00 | ~$0.20 |
| Lambda | ~$0.50 | ~$0.10 |
| API Gateway | ~$1.00 | ~$0.20 |
| DynamoDB | ~$0.00 | ~$0.00 |
| CloudWatch Logs | ~$0.50 | ~$0.50 |
| **Total** | **~$32/mo** | **~$9/mo** |

> **Note**: Actual costs depend on usage patterns. The dominant cost factor is S3 data transfer, not compute.

---

## 🗺 Roadmap

### Phase 0 — WMP/Legacy Adaptation ✅ (Completed)
- [x] Catalog endpoint with pagination
- [x] Playback-optimized presigned URLs
- [x] DynamoDB schema redesign (item-per-video)
- [x] GSI for status and upload date queries
- [x] Upload extension validation
- [x] S3 lifecycle rules for cost optimization
- [x] Placeholder thumbnail support

### Phase 1 — Security 🔒 (In Progress)
- [ ] Externalize JWT secret to AWS Secrets Manager
- [ ] Change RemovalPolicy to RETAIN for production
- [ ] Implement least-privilege IAM policies
- [ ] Add AWS WAF to API Gateway
- [ ] Enforce S3 encryption and SSL

### Phase 2 — Resilience 📊
- [ ] S3 → SQS → Lambda for reliable processing
- [ ] CloudWatch alarms and operational dashboard
- [ ] Lambda timeout and memory tuning
- [ ] Configurable log retention by environment

### Phase 3 — Scalability 🚀
- [ ] Expose `POST /token` endpoint
- [ ] Shared response utilities module
- [ ] CloudFront evaluation for multi-region scenarios
- [ ] ARM64 Lambda architecture

### Phase 4 — Operations 🔧
- [ ] Multi-environment deployment (dev/staging/prod)
- [ ] CI/CD pipeline with CDK Pipelines
- [ ] Integration tests for full flow
- [ ] CDK Nag compliance

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit your changes**: `git commit -m 'Add amazing feature'`
4. **Push to the branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

### Development Workflow

1. Create a virtual environment and install dependencies
2. Make your changes (infra, Lambda, or tests)
3. Run `cdk diff` to preview infrastructure changes
4. Run `pytest` to ensure all tests pass
5. Run `cdk synth` to verify CloudFormation generation
6. Submit your PR with a clear description

### Coding Standards

- Follow existing code structure and naming conventions
- Include tests for new functionality
- Update documentation as needed
- Keep changes minimal and focused
- Use AI prompt tags for efficient AI-assisted development

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [AWS CDK](https://aws.amazon.com/cdk/)
- Inspired by serverless best practices from the AWS Well-Architected Framework
- Special thanks to the open-source community for tools and libraries

---

<div align="center">
  <sub>Built with ❤️ using AWS CDK and Python</sub>
  <br/>
  <sub>© 2026 — S3 Video Manager Team</sub>
</div>
