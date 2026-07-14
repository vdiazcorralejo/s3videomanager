import json
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"  # Use AWS Secrets Manager in production
ALGORITHM = "HS256"

def create_jwt_token(user_id: str, expires_delta: timedelta = timedelta(days=1)):
    expire = datetime.utcnow() + expires_delta
    
    payload = {
        "sub": user_id,  # subject (user identifier)
        "iat": datetime.utcnow().timestamp(),  # issued at
        "exp": expire.timestamp(),  # expiration time
        "scope": "api:access"  # custom claims
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
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