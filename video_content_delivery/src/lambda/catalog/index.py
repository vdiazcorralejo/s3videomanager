import base64
import json
import os
from typing import Any

import boto3


dynamodb = boto3.client("dynamodb")

MAX_PAGE_SIZE = 20
DEFAULT_PAGE_SIZE = 20

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": HEADERS,
        "body": json.dumps(body),
    }


def _parse_page_size(raw_page_size: str | None) -> int:
    if not raw_page_size:
        return DEFAULT_PAGE_SIZE

    try:
        page_size = int(raw_page_size)
    except ValueError:
        raise ValueError("Invalid pageSize. It must be an integer.")

    if page_size < 1:
        raise ValueError("Invalid pageSize. It must be greater than 0.")

    return min(page_size, MAX_PAGE_SIZE)


def _decode_last_evaluated_key(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        key = json.loads(decoded)
        if not isinstance(key, dict):
            raise ValueError("Invalid pagination token format")
        return key
    except Exception as exc:
        raise ValueError("Invalid lastEvaluatedKey token") from exc


def _encode_last_evaluated_key(key: dict[str, Any] | None) -> str | None:
    if not key:
        return None

    encoded = base64.urlsafe_b64encode(json.dumps(key).encode("utf-8"))
    return encoded.decode("utf-8")


def _s(item: dict[str, Any], key: str, default: str = "") -> str:
    value = item.get(key, {})
    return value.get("S", default)


def _n(item: dict[str, Any], key: str, default: int = 0) -> int:
    value = item.get(key, {})
    raw = value.get("N")
    if raw is None:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def _build_video(item: dict[str, Any], bucket_name: str) -> dict[str, Any]:
    thumbnail_key = _s(item, "thumbnailKey")
    thumbnail_url = None
    if thumbnail_key:
        thumbnail_url = f"https://{bucket_name}.s3.amazonaws.com/{thumbnail_key}"

    return {
        "id": _s(item, "videoId"),
        "title": _s(item, "title"),
        "fileName": _s(item, "fileName"),
        "status": _s(item, "status", "ready"),
        "durationSeconds": _n(item, "durationSeconds", 0),
        "sizeBytes": _n(item, "sizeBytes", 0),
        "thumbnailUrl": thumbnail_url,
        "uploadDate": _s(item, "uploadDate"),
        "contentType": _s(item, "contentType", "video/mp4"),
    }


def handler(event, context):
    table_name = os.environ.get("TABLE_NAME")
    bucket_name = os.environ.get("BUCKET_NAME", "")

    if not table_name:
        return _response(500, {"error": "Server configuration error"})

    query_params = event.get("queryStringParameters") or {}

    try:
        page_size = _parse_page_size(query_params.get("pageSize"))
        status = query_params.get("status", "ready")
        last_evaluated_key = _decode_last_evaluated_key(
            query_params.get("lastEvaluatedKey")
        )
    except ValueError as exc:
        return _response(400, {"error": str(exc)})

    query_args: dict[str, Any] = {
        "TableName": table_name,
        "IndexName": "StatusIndex",
        "KeyConditionExpression": "#pk = :pk AND #st = :st",
        "ExpressionAttributeNames": {
            "#pk": "videoList",
            "#st": "status",
        },
        "ExpressionAttributeValues": {
            ":pk": {"S": "catalog"},
            ":st": {"S": status},
        },
        "Limit": page_size,
        "ScanIndexForward": False,
    }

    if last_evaluated_key:
        query_args["ExclusiveStartKey"] = last_evaluated_key

    try:
        response = dynamodb.query(**query_args)
        items = response.get("Items", [])

        videos = [_build_video(item, bucket_name) for item in items]
        next_token = _encode_last_evaluated_key(response.get("LastEvaluatedKey"))

        return _response(
            200,
            {
                "videos": videos,
                "pageSize": page_size,
                "lastEvaluatedKey": next_token,
            },
        )
    except Exception as exc:
        return _response(500, {"error": "Failed to retrieve catalog", "details": str(exc)})
