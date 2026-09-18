import pytest
import boto3
from botocore.stub import Stubber
from src.collector.lambda_collector import LambdaCollector

def test_lambda_collector_output_schema_and_redaction():
    # 1. Setup mocked boto3 client
    client = boto3.client('lambda', region_name='ap-south-1')
    stubber = Stubber(client)
    
    # 2. Mock list_functions response
    list_functions_response = {
        'Functions': [
            {
                'FunctionName': 'prod-checkout',
                'FunctionArn': 'arn:aws:lambda:ap-south-1:111122223333:function:prod-checkout',
            }
        ]
    }
    stubber.add_response('list_functions', list_functions_response)
    
    # 3. Mock get_function_configuration response
    get_config_response = {
        'FunctionName': 'prod-checkout',
        'FunctionArn': 'arn:aws:lambda:ap-south-1:111122223333:function:prod-checkout',
        'Runtime': 'python3.12',
        'MemorySize': 512,
        'Timeout': 30,
        'LastModified': '2026-09-12T02:14:55Z',
        'Environment': {
            'Variables': {
                'FEATURE_NEW_CHECKOUT': 'false',
                'DB_PASSWORD': 'supersecretpassword123!'
            }
        },
        'Layers': [
            {'Arn': 'arn:aws:lambda:ap-south-1:111122223333:layer:common:14'}
        ]
    }
    stubber.add_response('get_function_configuration', get_config_response, expected_params={'FunctionName': 'prod-checkout'})
    
    # 4. Activate stubber and run collector
    stubber.activate()
    collector = LambdaCollector(client=client)
    resources = collector.collect()
    stubber.deactivate()
    
    # 5. Assertions
    assert len(resources) == 1
    res = resources[0]
    
    # Check schema
    assert res['resource_type'] == 'lambda'
    assert res['logical_name'] == 'prod-checkout'
    assert res['resource_arn'] == 'arn:aws:lambda:ap-south-1:111122223333:function:prod-checkout'
    
    config = res['config']
    assert config['runtime'] == 'python3.12'
    assert config['memory_mb'] == 512
    assert config['timeout_s'] == 30
    assert config['last_modified'] == '2026-09-12T02:14:55Z'
    assert config['layers'] == ['arn:aws:lambda:ap-south-1:111122223333:layer:common:14']
    
    # Check env vars redaction
    env_vars = config['env_vars']
    
    # Normal env var should not be redacted
    assert env_vars['FEATURE_NEW_CHECKOUT']['redacted'] == False
    assert env_vars['FEATURE_NEW_CHECKOUT']['value'] == 'false'
    
    # Secret env var should be redacted (due to 'password' in key)
    assert env_vars['DB_PASSWORD']['redacted'] == True
    assert env_vars['DB_PASSWORD']['value'] == None
    assert 'value_sha256' in env_vars['DB_PASSWORD']
