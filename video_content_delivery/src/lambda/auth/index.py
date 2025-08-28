import json
import os

def handler(event, context):
    token = event.get('authorizationToken')
    print('token received:', token)
    print('Method ARN:', event.get('methodArn'))

    if not token:
        print('ERROR: no token received!!')
        return generate_policy('user', 'Deny', event.get('methodArn'))
    
    # Use environment variable for expected token, fallback to default for backwards compatibility
    expected_token = os.environ.get('EXPECTED_TOKEN', 'valid-token')

    if token == expected_token:
        return generate_policy('user', 'Allow', event.get('methodArn'))
    else:
        return generate_policy('user', 'Deny', event.get('methodArn'))

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