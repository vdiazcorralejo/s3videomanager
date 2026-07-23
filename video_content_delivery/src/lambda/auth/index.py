import json
import os
from functools import lru_cache

try:
    import boto3
except ImportError:  # pragma: no cover - exercised in local/unit-test environments
    boto3 = None

import jwt

ALGORITHM = 'HS256'


@lru_cache(maxsize=1)
def get_secret():
    secret_name = os.environ.get('JWT_SECRET_NAME')
    if secret_name:
        if boto3 is None:
            raise RuntimeError('boto3 is required when JWT_SECRET_NAME is configured')

        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_name)
        secret_payload = json.loads(response['SecretString'])
        return secret_payload['JWT_SECRET_KEY']

    direct_secret = os.environ.get('JWT_SECRET_KEY')
    if direct_secret:
        return direct_secret

    raise RuntimeError('JWT_SECRET_NAME environment variable is not set')


def _extract_token(token):
    if not token:
        return None
    if token.lower().startswith('bearer '):
        return token.split(' ', 1)[1]
    return token


def handler(event, context):
    token = event.get('authorizationToken')
    method_arn = event.get('methodArn')
    print('token received:', token)
    print('Method ARN:', method_arn)

    if not token:
        print('ERROR: no token received!!')
        return generate_policy('user', 'Deny', method_arn)

    try:
        secret = get_secret()
        raw_token = _extract_token(token)
        if not raw_token:
            raise ValueError('Token is empty')

        jwt.decode(raw_token, secret, algorithms=[ALGORITHM], options={'require': ['sub', 'exp']})
        return generate_policy('user', 'Allow', method_arn)
    except Exception as exc:
        print('JWT validation failed:', exc)
        return generate_policy('user', 'Deny', method_arn)


def generate_policy(principal_id, effect, resource):
    auth_response = {
        'principalId': principal_id
    }

    if effect and resource:
        policy_document = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
        auth_response['policyDocument'] = policy_document
        print('Generated policyDocument:', json.dumps(policy_document, indent=2))

    print('Return authResponse:', json.dumps(auth_response, indent=2))
    return auth_response