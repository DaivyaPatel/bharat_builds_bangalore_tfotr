import pytest
import boto3
import datetime
from botocore.stub import Stubber
from src.collector.ecs_collector import ECSCollector

def test_ecs_collector_schema_and_redaction():
    client = boto3.client('ecs', region_name='ap-south-1')
    stubber = Stubber(client)
    
    # Mock list_services
    stubber.add_response('list_services', {'serviceArns': ['arn:aws:ecs:ap-south-1:111:service/default/my-service']}, expected_params={'cluster': 'default'})
    
    # Mock describe_services
    stubber.add_response('describe_services', {
        'services': [{
            'serviceName': 'my-service',
            'serviceArn': 'arn:aws:ecs:ap-south-1:111:service/default/my-service',
            'taskDefinition': 'arn:aws:ecs:ap-south-1:111:task-definition/my-task:1',
            'createdAt': datetime.datetime(2026, 9, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
        }]
    }, expected_params={'cluster': 'default', 'services': ['arn:aws:ecs:ap-south-1:111:service/default/my-service']})
    
    # Mock describe_task_definition
    stubber.add_response('describe_task_definition', {
        'taskDefinition': {
            'containerDefinitions': [{
                'name': 'web',
                'image': 'nginx:latest',
                'environment': [
                    {'name': 'PORT', 'value': '8080'},
                    {'name': 'DB_PASSWORD', 'value': 'supersecret123!'}
                ]
            }]
        }
    }, expected_params={'taskDefinition': 'arn:aws:ecs:ap-south-1:111:task-definition/my-task:1'})
    
    stubber.activate()
    collector = ECSCollector(client=client)
    resources = collector.collect('default')
    stubber.deactivate()
    
    assert len(resources) == 1
    res = resources[0]
    
    assert res['resource_type'] == 'ecs_service'
    assert res['logical_name'] == 'my-service'
    assert res['resource_arn'] == 'arn:aws:ecs:ap-south-1:111:service/default/my-service'
    
    config = res['config']
    assert config['task_definition_arn'] == 'arn:aws:ecs:ap-south-1:111:task-definition/my-task:1'
    assert config['created_at'] == '2026-09-01T10:00:00Z'
    
    containers = config['containers']
    assert len(containers) == 1
    container = containers[0]
    assert container['name'] == 'web'
    assert container['image'] == 'nginx:latest'
    
    env_vars = container['env_vars']
    assert env_vars['PORT']['redacted'] == False
    assert env_vars['PORT']['value'] == '8080'
    
    assert env_vars['DB_PASSWORD']['redacted'] == True
    assert env_vars['DB_PASSWORD']['value'] == None
    assert 'value_sha256' in env_vars['DB_PASSWORD']
