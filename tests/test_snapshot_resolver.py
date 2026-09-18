import pytest
import boto3
import json
import datetime
import io
from botocore.response import StreamingBody
from botocore.stub import Stubber
from src.resolver.snapshot_resolver import SnapshotResolver

def get_list_mock_response():
    return {
        'Contents': [
            {
                'Key': 'snapshots/staging/2026-09-18T10:00:00Z.json',
                'LastModified': datetime.datetime(2026, 9, 18, 10, 0, 0, tzinfo=datetime.timezone.utc)
            },
            {
                'Key': 'snapshots/staging/2026-09-18T12:00:00Z.json', # This is the newest
                'LastModified': datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)
            },
            {
                'Key': 'snapshots/staging/2026-09-18T09:00:00Z.json',
                'LastModified': datetime.datetime(2026, 9, 18, 9, 0, 0, tzinfo=datetime.timezone.utc)
            }
        ]
    }

def test_snapshot_resolver_list_and_get():
    client = boto3.client('s3', region_name='ap-south-1')
    stubber = Stubber(client)
    
    bucket_name = "test-bucket"
    environment = "staging"
    
    list_mock_response = get_list_mock_response()
    
    # It gets called twice in our tests (once directly, once via get_latest_snapshot)
    stubber.add_response('list_objects_v2', list_mock_response, expected_params={'Bucket': bucket_name, 'Prefix': 'snapshots/staging/'})
    stubber.add_response('list_objects_v2', list_mock_response, expected_params={'Bucket': bucket_name, 'Prefix': 'snapshots/staging/'})
    
    fake_payload = {"metadata": {"environment": "staging"}, "resources": []}
    encoded_payload = json.dumps(fake_payload).encode("utf-8")
    
    get_mock_response = {
        'Body': StreamingBody(io.BytesIO(encoded_payload), len(encoded_payload))
    }
    
    stubber.add_response('get_object', get_mock_response, expected_params={'Bucket': bucket_name, 'Key': 'snapshots/staging/2026-09-18T12:00:00Z.json'})
    
    stubber.activate()
    resolver = SnapshotResolver(bucket_name=bucket_name, client=client)
    
    keys = resolver.list_snapshots(environment, limit=2)
    assert len(keys) == 2
    assert keys[0] == 'snapshots/staging/2026-09-18T12:00:00Z.json' 
    assert keys[1] == 'snapshots/staging/2026-09-18T10:00:00Z.json'
    
    latest_snapshot = resolver.get_latest_snapshot(environment)
    assert latest_snapshot == fake_payload
    
    stubber.deactivate()

def test_snapshot_resolver_time_travel():
    client = boto3.client('s3', region_name='ap-south-1')
    stubber = Stubber(client)
    
    bucket_name = "test-bucket"
    environment = "staging"
    
    # Target time is 11:00am. It should completely ignore the 12:00pm snapshot, 
    # and select the 10:00am snapshot.
    target_time = "2026-09-18T11:00:00Z"
    
    stubber.add_response('list_objects_v2', get_list_mock_response(), expected_params={'Bucket': bucket_name, 'Prefix': 'snapshots/staging/'})
    
    fake_payload_old = {"metadata": {"environment": "staging", "time": "10am"}, "resources": []}
    encoded_payload = json.dumps(fake_payload_old).encode("utf-8")
    get_mock_response = {'Body': StreamingBody(io.BytesIO(encoded_payload), len(encoded_payload))}
    
    # Assert that it requests the 10:00:00Z key!
    stubber.add_response('get_object', get_mock_response, expected_params={'Bucket': bucket_name, 'Key': 'snapshots/staging/2026-09-18T10:00:00Z.json'})
    
    stubber.activate()
    resolver = SnapshotResolver(bucket_name=bucket_name, client=client)
    
    resolved_snapshot = resolver.get_snapshot_at(environment, target_time)
    assert resolved_snapshot == fake_payload_old
    
    stubber.deactivate()
