import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

def handler(event, context):
    print("=== Lambda Execution Started ===")
    print(f"Event received: {json.dumps(event, indent=2)}")
    print(f"Function name: {context.function_name}")
    print(f"Memory limit: {context.memory_limit_in_mb}MB")
    
    # Get the HTTP method from the event
    http_method = event.get('httpMethod', '')
    print(f"HTTP Method: {http_method}")
    print(f"Query Parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")
    
    action = event.get("queryStringParameters", {}).get("action")
    print(f"Requested action: {action}")

    try:
        if action == "list":
            return list_files()
        elif action == 'get_download_url':
            return generate_download_url(event)
        elif action == 'get_upload_url':
            return generate_upload_url(event)
        else:
            print(f"Invalid action requested: {action}")
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Invalid action'})
            }
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
        response = dynamodb.get_item(
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

def generate_upload_url(event):
    print("\n=== Generating Upload URL ===")
    print(f"Event parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")
    
    if not event.get('queryStringParameters'):
        print("Error: Missing query parameters")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Missing query parameters'})
        }

    key = event['queryStringParameters'].get('key')
    if not key:
        print("Error: Missing key parameter")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Missing key parameter'})
        }

    # Validate key to prevent path traversal and ensure it's a valid filename
    if '..' in key or key.startswith('/') or not key.strip():
        print(f"Error: Invalid key parameter: {key}")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Invalid key parameter'})
        }

    bucket_name = os.environ.get('BUCKET_NAME')
    if not bucket_name:
        print("Error: BUCKET_NAME environment variable not set")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Server configuration error'})
        }

    print(f"Generating presigned URL for bucket: {bucket_name}, key: {key}")

    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': key,
                'ContentType': 'video/mp4'
            },
            ExpiresIn=3600
        )
        
        print("Successfully generated upload URL")
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'url': url})
        }

    except ClientError as e:
        print(f"\n=== Error generating upload URL ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Failed to generate upload URL'})
        }

def generate_download_url(event):
    print("\n=== Generating Download URL ===")
    print(f"Event parameters: {json.dumps(event.get('queryStringParameters'), indent=2)}")
    
    if not event.get('queryStringParameters'):
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Missing query parameters'})
        }

    key = event['queryStringParameters'].get('key')
    if not key:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Missing key parameter'})
        }

    # Validate key to prevent path traversal and ensure it's a valid filename
    if '..' in key or key.startswith('/') or not key.strip():
        print(f"Error: Invalid key parameter: {key}")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Invalid key parameter'})
        }

    bucket_name = os.environ.get('BUCKET_NAME')
    if not bucket_name:
        print("Error: BUCKET_NAME environment variable not set")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Server configuration error'})
        }

    print('Bucket name:', bucket_name)

    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=300
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'url': url})
        }

    except ClientError as e:
        print('Error generating download URL:', e)
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Failed to generate download URL'})
        }