import boto3
import json
import datetime
from typing import List, Dict, Any

class SnapshotResolver:
    def __init__(self, bucket_name: str, region_name: str = "ap-south-1", client=None):
        self.bucket_name = bucket_name
        self.client = client or boto3.client("s3", region_name=region_name)

    def list_snapshots(self, environment: str, limit: int = 10) -> List[str]:
        """
        Lists the latest snapshots for an environment, sorted by most recent first.
        Returns a list of S3 object keys.
        """
        prefix = f"snapshots/{environment}/"
        response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        
        if "Contents" not in response:
            return []
            
        # Sort objects by LastModified date (descending)
        objects = response["Contents"]
        objects.sort(key=lambda obj: obj["LastModified"], reverse=True)
        
        # Return the top N keys
        keys = [obj["Key"] for obj in objects[:limit]]
        return keys

    def get_latest_snapshot(self, environment: str) -> Dict[str, Any]:
        """
        Fetches and parses the latest snapshot JSON payload for an environment.
        Raises an Exception if no snapshot exists.
        """
        latest_keys = self.list_snapshots(environment, limit=1)
        if not latest_keys:
            raise FileNotFoundError(f"No snapshots found for environment: {environment}")
            
        latest_key = latest_keys[0]
        
        response = self.client.get_object(Bucket=self.bucket_name, Key=latest_key)
        payload_bytes = response["Body"].read()
        
        return json.loads(payload_bytes.decode("utf-8"))

    def get_snapshot_at(self, environment: str, target_timestamp: str) -> Dict[str, Any]:
        """
        Fetches the most recent snapshot that existed AT OR BEFORE the target_timestamp.
        target_timestamp must be ISO8601 (e.g. '2026-09-18T10:00:00Z').
        """
        # Parse target timestamp string to datetime object
        target_dt = datetime.datetime.strptime(target_timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        
        prefix = f"snapshots/{environment}/"
        response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        
        if "Contents" not in response:
            raise FileNotFoundError(f"No snapshots found for environment: {environment}")
            
        # Filter objects where LastModified <= target_timestamp
        valid_objects = [
            obj for obj in response["Contents"] 
            if obj["LastModified"] <= target_dt
        ]
        
        if not valid_objects:
            raise FileNotFoundError(f"No snapshots found for environment {environment} before {target_timestamp}")
            
        # Sort by LastModified date (descending) to get the most recent one before the target
        valid_objects.sort(key=lambda obj: obj["LastModified"], reverse=True)
        
        target_key = valid_objects[0]["Key"]
        
        response = self.client.get_object(Bucket=self.bucket_name, Key=target_key)
        payload_bytes = response["Body"].read()
        
        return json.loads(payload_bytes.decode("utf-8"))
