import os
import json
import boto3
import urllib.parse
from src.resolver.snapshot_resolver import SnapshotResolver
from src.diff_engine import diff_snapshots
from src.severity import classify_all


def lambda_handler(event, context):
    print("Diff handler invoked with event:", event)
    env = event.get("environment")
    s3_uri = event.get("snapshot_s3_uri")

    if env != "staging":
        print(f"Skipping diff for {env} branch to avoid duplicate work.")
        return {"environment": env, "pair": "staging::production", "drifts": []}

    sts = boto3.client("sts", region_name="ap-south-1")
    account_id = sts.get_caller_identity()["Account"]
    bucket_name = os.environ.get("SNAPSHOT_BUCKET_NAME", f"driftlens-snapshots-{account_id}")

    resolver = SnapshotResolver(bucket_name=bucket_name, region_name="ap-south-1")

    s3 = boto3.client("s3")
    parsed_uri = urllib.parse.urlparse(s3_uri)
    key = parsed_uri.path.lstrip("/")
    resp = s3.get_object(Bucket=parsed_uri.netloc, Key=key)
    staging_snapshot = json.loads(resp["Body"].read().decode("utf-8"))

    try:
        production_snapshot = resolver.get_latest_snapshot("production")
    except Exception as e:
        print(f"Error fetching production snapshot: {e}")
        return {"environment": env, "pair": "staging::production", "drifts": []}

    drifts = diff_snapshots(staging_snapshot, production_snapshot)
    classified_drifts = classify_all(drifts)

    print(f"Found {len(classified_drifts)} drifts between staging and production.")

    return {"environment": env, "pair": "staging::production", "drifts": classified_drifts}