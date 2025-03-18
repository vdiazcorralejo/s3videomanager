# Video Content Delivery System

A serverless video content delivery system built with AWS CDK in Python. This project implements a secure and scalable architecture for uploading, storing, and streaming video content.

## Architecture

The system consists of the following AWS components:

- **S3 Bucket**: Stores video files with versioning enabled
- **DynamoDB**: Tracks video metadata and playlist information
- **Lambda Functions**:
  - `GetPresignedUrlFunction`: Generates pre-signed URLs for upload/download
  - `ProcessVideoFunction`: Processes videos when uploaded and generates playlists
  - `ApiGatewayAuthorizer`: Handles API authorization
- **API Gateway**: Provides REST API endpoints with custom authorization
- **CloudWatch**: Handles logging and monitoring

## Features

- Secure video upload/download via pre-signed URLs
- Custom token-based authorization
- Automatic video processing on upload
- M3U playlist generation
- CORS support for web applications
- Comprehensive logging system
- Automatic cleanup of resources on stack deletion

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
source .venv/bin/activate  # On Windows: [activate.bat](http://_vscodecontentref_/1)