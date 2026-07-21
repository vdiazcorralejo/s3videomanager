import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

dynamodb = boto3.client('dynamodb')

HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}


def _response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': HEADERS,
        'body': json.dumps(body)
    }


def _build_catalog_item(bucket_name, key, size_bytes):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    file_name = os.path.basename(key)
    title = os.path.splitext(file_name)[0].replace('_', ' ').replace('-', ' ').title()
    video_id = f"vid-{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"

    return {
        'videoList': {'S': 'catalog'},
        'videoId': {'S': video_id},
        'title': {'S': title},
        'fileName': {'S': file_name},
        'contentType': {'S': 'video/mp4'},
        'sizeBytes': {'N': str(size_bytes)},
        'durationSeconds': {'N': '0'},
        'thumbnailKey': {'S': ''},
        'uploadDate': {'S': now},
        'updatedAt': {'S': now},
        'status': {'S': 'ready'},
        'bucket': {'S': bucket_name},
        'sourceKey': {'S': key},
    }

def handler(event, context):
    print("=== Lambda Execution Started ===")
    print(f"Event received: {json.dumps(event, indent=2)}")
    print(f"Function name: {context.function_name}")
    print(f"Memory limit: {context.memory_limit_in_mb}MB")

    try:
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        raw_key = record['s3']['object']['key']
        key = unquote_plus(raw_key)
        size_bytes = int(record['s3']['object'].get('size', 0))

        print(f"\n=== Processing Upload ===")
        print(f"Bucket: {bucket}")
        print(f"File: {key}")

        if not key.lower().endswith('.mp4'):
            print("Skipping non-MP4 object")
            return _response(200, {
                'message': 'Skipped non-MP4 object',
                'fileName': key
            })

        table_name = os.environ.get('TABLE_NAME')
        if not table_name:
            print('Error: TABLE_NAME environment variable not set')
            return _response(500, {
                'error': 'Server configuration error'
            })

        item = _build_catalog_item(bucket, key, size_bytes)

        print('\n=== Updating DynamoDB ===')
        print(f"Table: {table_name}")
        print(f"Catalog item id: {item['videoId']['S']}")

        response = dynamodb.put_item(
            TableName=table_name,
            Item=item
        )

        print(f"\n=== DynamoDB Update Complete ===")
        print(f"Response: {json.dumps(response, default=str, indent=2)}")

        return _response(200, {
            'message': 'Catalog item stored successfully',
            'videoId': item['videoId']['S'],
            'fileName': item['fileName']['S'],
            'status': item['status']['S'],
            'uploadDate': item['uploadDate']['S']
        })

    except KeyError as e:
        print(f"Malformed event: {str(e)}")
        return _response(400, {
            'error': 'Malformed event',
            'details': str(e)
        })
    except Exception as e:
        print(f"\n=== Error Occurred ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return _response(500, {
            'error': str(e)
        })
    finally:
        print("\n=== Lambda Execution Completed ===")