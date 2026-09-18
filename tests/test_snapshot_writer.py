import pytest
import boto3
import json
import re
from botocore.stub import Stubber, ANY
from src.collector.snapshot_writer import SnapshotWriter

def test_snapshot_writer_kms_and_key_structure():
    client = boto3.client('s3', region_name='ap-south-1')
    stubber = Stubber(client)
    
    snapshot_data = {"test": "data"}
    bucket_name = "test-bucket-name"
    environment = "production"
    
    # We expect put_object to be called with exact parameters, 
    # except the Key which is dynamic (contains timestamp).
    expected_params = {
        'Bucket': bucket_name,
        'Key': ANY,
        'Body': json.dumps(snapshot_data).encode("utf-8"),
        'ContentType': "application/json",
        'ServerSideEncryption': "aws:kms"
    }
    
    stubber.add_response('put_object', {}, expected_params)
    
    stubber.activate()
    writer = SnapshotWriter(bucket_name=bucket_name, client=client)
    s3_uri = writer.write_snapshot(environment, snapshot_data)
    stubber.deactivate()
    
    # Verify the returned URI shape
    assert s3_uri.startswith(f"s3://{bucket_name}/snapshots/{environment}/")
    assert s3_uri.endswith(".json")
    
    # Extract the timestamp part and verify it matches strict ISO8601
    key_part = s3_uri.replace(f"s3://{bucket_name}/", "")
    ts_part = key_part.split("/")[-1].replace(".json", "")
    
    # Regex for YYYY-MM-DDTHH:MM:SSZ
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts_part)
