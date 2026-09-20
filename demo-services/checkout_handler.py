import json
import os

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "checkout processed",
            "feature_new_checkout": os.environ.get("FEATURE_NEW_CHECKOUT", "false"),
            "api_timeout_ms": os.environ.get("API_TIMEOUT_MS", "5000"),
        })
    }