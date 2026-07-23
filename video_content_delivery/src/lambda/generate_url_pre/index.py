import os
import json

try:
    import boto3
except ImportError:  # pragma: no cover - exercised in local/unit-test environments
    boto3 = None
try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - exercised in local/unit-test environments
    ClientError = Exception
from datetime import datetime

REGION = os.environ.get('REGION', 'eu-west-1')
s3_client = None
dynamodb = None


def get_s3_client():
    global s3_client
    if s3_client is None:
        if boto3 is None:
            raise RuntimeError('boto3 is required to generate presigned URLs')
        s3_client = boto3.client('s3', region_name=REGION)
    return s3_client


def get_dynamodb_client():
    global dynamodb
    if dynamodb is None:
        if boto3 is None:
            raise RuntimeError('boto3 is required to access DynamoDB')
        dynamodb = boto3.client('dynamodb', region_name=REGION)
    return dynamodb

DOWNLOAD_URL_EXPIRATION = 300
PLAYBACK_URL_EXPIRATION = 86400

PLAYBACK_CONTENT_TYPES = {
    '.mp4': 'video/mp4',
    '.wmv': 'video/x-ms-wmv',
    '.avi': 'video/x-msvideo',
    '.webm': 'video/webm',
}

# Only these extensions are accepted for upload.
ALLOWED_UPLOAD_EXTENSIONS = {'.mp4', '.wmv', '.avi', '.mov', '.m4v'}


def _response(status_code, payload):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(payload)
    }


def _get_query_params(event):
    return event.get('queryStringParameters') or {}


def _get_validated_key(event):
    query_params = _get_query_params(event)
    key = query_params.get('key')
    if not key:
        return None, _response(400, {'error': 'Missing key parameter'})

    if '..' in key or key.startswith('/') or not key.strip():
        print(f"Error: Invalid key parameter: {key}")
        return None, _response(400, {'error': 'Invalid key parameter'})

    return key, None


def _get_bucket_name():
    bucket_name = os.environ.get('BUCKET_NAME')
    if not bucket_name:
        print("Error: BUCKET_NAME environment variable not set")
        return None, _response(500, {'error': 'Server configuration error'})
    return bucket_name, None


def _playback_content_type_for_key(key):
    ext = os.path.splitext(key)[1].lower()
    return PLAYBACK_CONTENT_TYPES.get(ext, 'application/octet-stream')

def handler(event, context):
    print("=== Lambda Execution Started ===")
    print(f"Event received: {json.dumps(event, indent=2)}")
    print(f"Function name: {context.function_name}")
    print(f"Memory limit: {context.memory_limit_in_mb}MB")

    # Get the HTTP method from the event
    http_method = event.get('httpMethod', '')
    print(f"HTTP Method: {http_method}")
    print(f"Query Parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")

    action = _get_query_params(event).get("action")
    print(f"Requested action: {action}")

    try:
        if action == "list":
            return list_files()
        elif action == 'get_download_url':
            return generate_download_url(event)
        elif action == 'get_playback_url':
            return generate_playback_url(event)
        elif action == 'get_upload_url':
            return generate_upload_url(event)
        else:
            print(f"Invalid action requested: {action}")
            return _response(400, {'error': 'Invalid action'})
    finally:
        print("\n=== Lambda Execution Completed ===")
        print(f"Remaining time: {context.get_remaining_time_in_millis()}ms")

def list_files():
    print("\n=== Listing Files from DynamoDB ===")
    table_name = os.environ.get('TABLE_NAME')
    if not table_name:
        print("Error: TABLE_NAME environment variable not set")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Server configuration error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    print(f"Table name: {table_name}")

    try:
        print("Querying DynamoDB for video list...")
        response = get_dynamodb_client().get_item(
            TableName=table_name,
            Key={
                'videoList': {'S': 'all_videos'},
                'Date': {'S': 'current'}
            }
        )

        if 'Item' not in response:
            print("No video list found in DynamoDB")
            return {
                "statusCode": 200,
                "body": json.dumps({"files": []}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }

        # Parse the JSON string from DynamoDB
        videos_json = response['Item']['videos']['S']
        videos = json.loads(videos_json)

        print(f"Found {len(videos)} videos in DynamoDB")
        print(f"Videos: {json.dumps(videos, indent=2)}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "files": videos,
                "lastUpdated": response['Item']['lastUpdated']['S']
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }
    except Exception as e:
        print(f"\n=== Error in list_files ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to retrieve video list"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

def _validate_upload_extension(key: str):
    ext = os.path.splitext(key)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        print(f"Error: Extension '{ext}' not allowed")
        return _response(400, {
            'error': f'Extension "{ext}" not allowed',
            'allowedExtensions': sorted(ALLOWED_UPLOAD_EXTENSIONS)
        })
    return None


def generate_upload_url(event):
    print("\n=== Generating Upload URL ===")
    print(f"Event parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")

    if not _get_query_params(event):
        print("Error: Missing query parameters")
        return _response(400, {'error': 'Missing query parameters'})

    key, key_error = _get_validated_key(event)
    if key_error:
        return key_error

    ext_error = _validate_upload_extension(key)
    if ext_error:
        return ext_error

    bucket_name, bucket_error = _get_bucket_name()
    if bucket_error:
        return bucket_error

    print(f"Generating presigned URL for bucket: {bucket_name}, key: {key}")

    try:
        url = get_s3_client().generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': key,
                'ContentType': 'video/mp4'
            },
            ExpiresIn=3600
        )

        print("Successfully generated upload URL")
        return _response(200, {'url': url})

    except ClientError as e:
        print(f"\n=== Error generating upload URL ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return _response(500, {'error': 'Failed to generate upload URL'})

def generate_download_url(event):
    print("\n=== Generating Download URL ===")
    print(f"Event parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")

    if not _get_query_params(event):
        return _response(400, {'error': 'Missing query parameters'})

    key, key_error = _get_validated_key(event)
    if key_error:
        return key_error

    bucket_name, bucket_error = _get_bucket_name()
    if bucket_error:
        return bucket_error

    print('Bucket name:', bucket_name)

    try:
        url = get_s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=DOWNLOAD_URL_EXPIRATION
        )

        return _response(200, {
            'url': url,
            'expiresIn': DOWNLOAD_URL_EXPIRATION,
            'mode': 'download'
        })

    except ClientError as e:
        print('Error generating download URL:', e)
        return _response(500, {'error': 'Failed to generate download URL'})


def generate_playback_url(event):
    print("\n=== Generating Playback URL ===")
    print(f"Event parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")

    if not _get_query_params(event):
        return _response(400, {'error': 'Missing query parameters'})

    key, key_error = _get_validated_key(event)
    if key_error:
        return key_error

    bucket_name, bucket_error = _get_bucket_name()
    if bucket_error:
        return bucket_error

    content_type = _playback_content_type_for_key(key)

    try:
        url = get_s3_client().generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': key,
                'ResponseContentType': content_type,
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=PLAYBACK_URL_EXPIRATION
        )

        return _response(200, {
            'url': url,
            'contentType': content_type,
            'expiresIn': PLAYBACK_URL_EXPIRATION,
            'mode': 'playback'
        })
    except ClientError as e:
        print('Error generating playback URL:', e)
        return _response(500, {'error': 'Failed to generate playback URL'})