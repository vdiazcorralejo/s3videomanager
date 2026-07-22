import json
import os
from datetime import datetime, timedelta
from functools import lru_cache

import boto3
import jwt

ALGORITHM = "HS256"


@lru_cache(maxsize=1)
def get_secret():
    secret_name = os.environ.get('JWT_SECRET_NAME')
    if not secret_name:
        raise RuntimeError('JWT_SECRET_NAME environment variable is not set')

    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    secret_payload = json.loads(response['SecretString'])
    return secret_payload['JWT_SECRET_KEY']


def create_jwt_token(user_id: str, expires_delta: timedelta = timedelta(days=1)):
    expire = datetime.utcnow() + expires_delta
    secret_key = get_secret()

    payload = {
        "sub": user_id,  # subject (user identifier)
        "iat": datetime.utcnow().timestamp(),  # issued at
        "exp": expire.timestamp(),  # expiration time
        "scope": "api:access"  # custom claims
    }

    token = jwt.encode(payload, secret_key, algorithm=ALGORITHM)
    return token

def handler(event, context):
    print("=== Token Generator Started ===")

    try:
        body = json.loads(event.get('body', '{}'))
        user_id = body.get('user_id')

        if not user_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'user_id is required'}),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }

        token = create_jwt_token(user_id)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'token': f"Bearer {token}",  # Include Bearer prefix
                'type': 'Bearer',
                'expires_in': 86400  # 24 hours in seconds
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }

    except Exception as e:
        print(f"Error generating token: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }