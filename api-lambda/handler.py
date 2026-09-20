import json

def response(status_code, data=None, error=None):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"data": data, "error": error})
    }

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
        with open("comparison_response_sample.json") as f:
            fixture = json.load(f)
        return response(200, data=fixture["data"])

    return response(404, error="Route not found")