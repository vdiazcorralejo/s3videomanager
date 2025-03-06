import os
import json
import base64
import boto3
from botocore.exceptions import ClientError
import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

def handler(event, context):
    # Check if body exists and contains file data
    try:
        if not event.get('body'):
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Missing file data'})
            }

        # Get the file data from the request body
        body = json.loads(event['body'])
        file_name = body.get('fileName')
        file_content = body.get('fileContent')  # Base64 encoded content

        if not file_name or not file_content:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Missing fileName or fileContent'})
            }

        # Validate file extension
        if not file_name.lower().endswith('.mp4'):
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Only MP4 files are allowed'})
            }

        # Decode base64 content
        file_content_decoded = base64.b64decode(file_content)
        
        bucket_name = os.environ['BUCKET_NAME']
        table_name = os.environ['TABLE_NAME']

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=file_content_decoded,
            ContentType='video/mp4'
        )

        # Store metadata in DynamoDB
        dynamodb.put_item(
            TableName=table_name,
            Item={
                'fileName': {'S': file_name},
                'creationDate': {'S': datetime.datetime.now().isoformat()},
                'fileSize': {'N': str(len(file_content_decoded))}
            }
        )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'File uploaded successfully',
                'fileName': file_name
            })
        }

    except ClientError as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': str(e)})
        }