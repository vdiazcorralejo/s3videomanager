import os
import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

def handler(event, context):
    print('Event:', event)
    # Get the HTTP method from the event
    http_method = event.get('httpMethod', '')
    # Registrar el método HTTP y los parámetros de consulta
    print('HTTP Method:', event.get('httpMethod'))
    print('Query String Parameters:', event.get('queryStringParameters'))
    action = event.get("queryStringParameters", {}).get("action")

    if action == "list":
        return list_files()
    elif action == 'get_download_url':
        return generate_download_url(event)
    elif action == 'get_upload_url':
        return generate_upload_url(event)
    else:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Invalid HTTP method'})
        }

def list_files():

    bucket_name = os.environ['BUCKET_NAME']
    print('list_files(): Bucket name:', bucket_name)
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        files = [item["Key"] for item in response.get("Contents", [])]

        return {
            "statusCode": 200,
            "body": json.dumps({"files": files}),
            "headers": {"Content-Type": "application/json"}
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }

def generate_upload_url(event):
    print('Generating upload URL')
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

    bucket_name = os.environ['BUCKET_NAME']
    print('Bucket name:', bucket_name)

    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': key,
                'ContentType': 'video/mp4'  # Adjust content type as needed
            },
            ExpiresIn=3600  # URL valid for 1 hour
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
        print('Error generating upload URL:', e)
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': str(e)})
        }

def generate_download_url(event):
    print('Generating download URL')
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

    bucket_name = os.environ['BUCKET_NAME']
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
            'body': json.dumps({'error': str(e)})
        }