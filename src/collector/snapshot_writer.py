import boto3
import json
import datetime
from typing import Dict, Any

class SnapshotWriter:
    def __init__(self, bucket_name: str, region_name: str = "ap-south-1", client=None):
        self.bucket_name = bucket_name
        self.client = client or boto3.client("s3", region_name=region_name)

    def write_snapshot(self, environment: str, snapshot_data: Dict[str, Any]) -> str:
        """
        Writes the snapshot data to S3 securely using SSE-KMS.
        Returns the S3 URI of the written object.
        """
        # Generate strict ISO8601 timestamp with 'Z'
        now = datetime.datetime.now(datetime.timezone.utc)
        iso8601_ts = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Construct key per TICKETS.md: snapshots/{env}/{iso8601}.json
        object_key = f"snapshots/{environment}/{iso8601_ts}.json"
        
        # Serialize payload
        payload_bytes = json.dumps(snapshot_data).encode("utf-8")
        
        # Put object securely with KMS encryption (DL-007 requirement)
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=payload_bytes,
            ContentType="application/json",
            ServerSideEncryption="aws:kms"
        )
        
        return f"s3://{self.bucket_name}/{object_key}"
