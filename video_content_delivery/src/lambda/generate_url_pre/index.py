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

    if http_method == 'GET':
        return generate_download_url(event)
    elif http_method == 'PUT':
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

def generate_upload_url(event):
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