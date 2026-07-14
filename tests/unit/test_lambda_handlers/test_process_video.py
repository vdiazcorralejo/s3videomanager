from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import json


def load_process_video_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / 'video_content_delivery'
        / 'src'
        / 'lambda'
        / 'process_video'
        / 'index.py'
    )
    spec = spec_from_file_location('process_video_index', module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeDynamoDB:
    def __init__(self):
        self.calls = []

    def put_item(self, **kwargs):
        self.calls.append(kwargs)
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}


def make_context():
    return SimpleNamespace(function_name='ProcessVideoFunction', memory_limit_in_mb=512)


def test_handler_stores_single_catalog_item(monkeypatch):
    module = load_process_video_module()
    fake_dynamodb = FakeDynamoDB()
    monkeypatch.setattr(module, 'dynamodb', fake_dynamodb)
    monkeypatch.setenv('TABLE_NAME', 'listOfVideoFiles')

    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'video-content-delivery-bucket'},
                    'object': {
                        'key': 'promo-verano-2026.mp4',
                        'size': 12345,
                    },
                }
            }
        ]
    }

    response = module.handler(event, make_context())

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert payload['message'] == 'Catalog item stored successfully'
    assert payload['fileName'] == 'promo-verano-2026.mp4'
    assert payload['status'] == 'ready'
    assert len(fake_dynamodb.calls) == 1

    call = fake_dynamodb.calls[0]
    assert call['TableName'] == 'listOfVideoFiles'
    assert call['Item']['videoList']['S'] == 'catalog'
    assert call['Item']['fileName']['S'] == 'promo-verano-2026.mp4'
    assert call['Item']['status']['S'] == 'ready'
    assert call['Item']['sizeBytes']['N'] == '12345'


def test_handler_skips_non_mp4(monkeypatch):
    module = load_process_video_module()
    fake_dynamodb = FakeDynamoDB()
    monkeypatch.setattr(module, 'dynamodb', fake_dynamodb)
    monkeypatch.setenv('TABLE_NAME', 'listOfVideoFiles')

    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'video-content-delivery-bucket'},
                    'object': {
                        'key': 'notes.txt',
                        'size': 10,
                    },
                }
            }
        ]
    }

    response = module.handler(event, make_context())

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert payload['message'] == 'Skipped non-MP4 object'
    assert payload['fileName'] == 'notes.txt'
    assert fake_dynamodb.calls == []