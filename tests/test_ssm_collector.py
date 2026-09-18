import pytest
import boto3
import datetime
from botocore.stub import Stubber
from src.collector.ssm_collector import SSMCollector

def test_ssm_collector_schema_and_redaction():
    client = boto3.client('ssm', region_name='ap-south-1')
    stubber = Stubber(client)
    
    mock_response = {
        'Parameters': [
            {
                'Name': '/app/api_timeout',
                'Type': 'String',
                'Value': '30',
                'Version': 4,
                'LastModifiedDate': datetime.datetime(2026, 9, 1, 11, 2, 0, tzinfo=datetime.timezone.utc)
            },
            {
                'Name': '/app/db_password',
                'Type': 'SecureString',
                'Value': 'ciphertext12345',
                'Version': 1,
                'LastModifiedDate': datetime.datetime(2026, 9, 1, 11, 5, 0, tzinfo=datetime.timezone.utc)
            },
            {
                'Name': '/app/secret_api_key',
                'Type': 'String', # Accidentally stored as String instead of SecureString!
                'Value': 'supersecretkey99',
                'Version': 2,
                'LastModifiedDate': datetime.datetime(2026, 9, 1, 11, 10, 0, tzinfo=datetime.timezone.utc)
            }
        ]
    }
    
    stubber.add_response('get_parameters_by_path', mock_response, expected_params={'Path': '/', 'Recursive': True, 'WithDecryption': False})
    
    stubber.activate()
    collector = SSMCollector(client=client)
    params = collector.collect(path='/')
    stubber.deactivate()
    
    # Assertions
    assert len(params) == 3
    
    # 1. Normal String
    assert params['/app/api_timeout']['type'] == 'String'
    assert params['/app/api_timeout']['value'] == '30'
    assert params['/app/api_timeout']['redacted'] == False
    assert params['/app/api_timeout']['version'] == 4
    assert params['/app/api_timeout']['last_modified'] == '2026-09-01T11:02:00Z'
    
    # 2. SecureString
    assert params['/app/db_password']['type'] == 'SecureString'
    assert params['/app/db_password']['value'] == None
    assert params['/app/db_password']['redacted'] == True
    assert 'value_sha256' in params['/app/db_password']
    
    # 3. String containing secret (caught by heuristics)
    assert params['/app/secret_api_key']['type'] == 'String'
    assert params['/app/secret_api_key']['value'] == None
    assert params['/app/secret_api_key']['redacted'] == True
    assert 'value_sha256' in params['/app/secret_api_key']
