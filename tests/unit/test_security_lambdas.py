import importlib

import jwt

auth_index = importlib.import_module('video_content_delivery.src.lambda.auth.index')
token_generator_index = importlib.import_module('video_content_delivery.src.lambda.token_generator.index')


def test_create_jwt_token_uses_secret_manager_secret(monkeypatch):
    monkeypatch.setattr(token_generator_index, "get_secret", lambda: "super-secret")

    token = token_generator_index.create_jwt_token("user-123")
    payload = jwt.decode(token, "super-secret", algorithms=["HS256"])

    assert payload["sub"] == "user-123"


def test_auth_handler_allows_valid_bearer_token(monkeypatch):
    monkeypatch.setattr(auth_index, "get_secret", lambda: "super-secret")

    token = jwt.encode(
        {"sub": "user-123", "exp": 4102444800},
        "super-secret",
        algorithm="HS256",
    )
    event = {
        "authorizationToken": f"Bearer {token}",
        "methodArn": "arn:aws:execute-api:eu-west-1:123456789012:abc123/*/*",
    }

    response = auth_index.handler(event, object())

    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"


def test_auth_handler_denies_invalid_token(monkeypatch):
    monkeypatch.setattr(auth_index, "get_secret", lambda: "super-secret")

    event = {
        "authorizationToken": "Bearer not-a-valid-jwt",
        "methodArn": "arn:aws:execute-api:eu-west-1:123456789012:abc123/*/*",
    }

    response = auth_index.handler(event, object())

    assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"
