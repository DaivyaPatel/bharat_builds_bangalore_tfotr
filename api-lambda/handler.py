import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
TABLE_NAME = "driftlens-drift-records"

def response(status_code, data=None, error=None):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"data": data, "error": error})
    }

def get_comparison_from_dynamodb(pair):
    """Try to read real drift records from DynamoDB. Returns None if table/data unavailable."""
    try:
        table = dynamodb.Table(TABLE_NAME)
        resp = table.query(
            KeyConditionExpression=Key('pair').eq(pair)
        )
        items = resp.get('Items', [])
        if not items:
            return None

        summary = {"critical": 0, "suspicious": 0, "expected": 0}
        for item in items:
            sev = item.get('severity')
            if sev in summary:
                summary[sev] += 1

        return {
            "comparison_id": f"live-{pair.replace('::', '-')}",
            "pair": pair,
            "summary": summary,
            "drifts": items
        }
    except Exception as e:
        print(f"DynamoDB read failed, falling back to fixtures: {type(e).__name__}: {e}")
        return None

def get_comparison_fixture():
    with open("comparison_response_sample.json") as f:
        fixture = json.load(f)
    return fixture["data"]

def lambda_handler(event, context):
    method = event.get("httpMethod")
    path = event.get("path", "")

    if method == "GET" and path == "/environments":
        return response(200, data=[
            {"environment": "staging", "last_snapshot_at": "2026-09-19T08:14:02Z"},
            {"environment": "production", "last_snapshot_at": "2026-09-19T08:14:02Z"}
        ])

    if method == "POST" and path == "/snapshots":
        return response(200, data={"execution_arn": "arn:aws:states:ap-south-1:678360600444:execution:driftlens:fake-exec-id"})

    if method == "GET" and path == "/snapshots":
        return response(200, data=[
            {"snapshot_id": "01J8XK2M4N7P9QRSTVWXYZ", "environment": "production", "captured_at": "2026-09-19T08:14:02Z"},
            {"snapshot_id": "01J8XK2M4N7P9QRSTVWXYA", "environment": "staging", "captured_at": "2026-09-19T08:14:02Z"}
        ])

    if method == "POST" and path == "/compare":
        return response(200, data={"comparison_id": "01J8XK2M4N7P9QRSTVWXYZC"})

    if method == "GET" and path.startswith("/comparisons/"):
        pair = "staging::production"
        real_data = get_comparison_from_dynamodb(pair)
        if real_data:
            return response(200, data=real_data)
        return response(200, data=get_comparison_fixture())

    return response(404, error="Route not found")