from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import json


def load_generate_url_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / 'video_content_delivery'
        / 'src'
        / 'lambda'
        / 'generate_url_pre'
        / 'index.py'
    )
    spec = spec_from_file_location('generate_url_pre_index', module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def generate_presigned_url(self, operation_name, Params, ExpiresIn):
        self.calls.append(
            {
                'operation_name': operation_name,
                'params': Params,
                'expires_in': ExpiresIn,
            }
        )
        return 'https://signed.example/url'


def make_context():
    return SimpleNamespace(
        function_name='GetPresignedUrlFunction',
        memory_limit_in_mb=256,
        get_remaining_time_in_millis=lambda: 1000,
    )


def test_generate_playback_url_uses_inline_and_long_expiration(monkeypatch):
    module = load_generate_url_module()
    fake_s3 = FakeS3Client()
    monkeypatch.setattr(module, 's3_client', fake_s3)
    monkeypatch.setenv('BUCKET_NAME', 'video-bucket-dev')

    event = {
        'httpMethod': 'GET',
        'queryStringParameters': {
            'action': 'get_playback_url',
            'key': 'promo-2026.wmv',
        },
    }

    response = module.handler(event, make_context())

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert payload['mode'] == 'playback'
    assert payload['contentType'] == 'video/x-ms-wmv'
    assert payload['expiresIn'] == module.PLAYBACK_URL_EXPIRATION

    assert len(fake_s3.calls) == 1
    call = fake_s3.calls[0]
    assert call['operation_name'] == 'get_object'
    assert call['expires_in'] == module.PLAYBACK_URL_EXPIRATION
    assert call['params']['ResponseContentDisposition'] == 'inline'
    assert call['params']['ResponseContentType'] == 'video/x-ms-wmv'


def test_download_and_playback_have_different_expiration(monkeypatch):
    module = load_generate_url_module()
    fake_s3 = FakeS3Client()
    monkeypatch.setattr(module, 's3_client', fake_s3)
    monkeypatch.setenv('BUCKET_NAME', 'video-bucket-dev')

    download_event = {
        'httpMethod': 'GET',
        'queryStringParameters': {
            'action': 'get_download_url',
            'key': 'promo-2026.mp4',
        },
    }
    playback_event = {
        'httpMethod': 'GET',
        'queryStringParameters': {
            'action': 'get_playback_url',
            'key': 'promo-2026.mp4',
        },
    }

    download_response = module.handler(download_event, make_context())
    playback_response = module.handler(playback_event, make_context())

    assert download_response['statusCode'] == 200
    assert playback_response['statusCode'] == 200

    download_payload = json.loads(download_response['body'])
    playback_payload = json.loads(playback_response['body'])
    assert download_payload['mode'] == 'download'
    assert playback_payload['mode'] == 'playback'
    assert download_payload['expiresIn'] == module.DOWNLOAD_URL_EXPIRATION
    assert playback_payload['expiresIn'] == module.PLAYBACK_URL_EXPIRATION

    assert len(fake_s3.calls) == 2
    assert fake_s3.calls[0]['expires_in'] == module.DOWNLOAD_URL_EXPIRATION
    assert fake_s3.calls[1]['expires_in'] == module.PLAYBACK_URL_EXPIRATION


def test_playback_url_requires_valid_key(monkeypatch):
    module = load_generate_url_module()
    monkeypatch.setenv('BUCKET_NAME', 'video-bucket-dev')

    event = {
        'httpMethod': 'GET',
        'queryStringParameters': {
            'action': 'get_playback_url',
            'key': '../secret.mp4',
        },
    }

    response = module.handler(event, make_context())
    assert response['statusCode'] == 400
    payload = json.loads(response['body'])
    assert payload['error'] == 'Invalid key parameter'
