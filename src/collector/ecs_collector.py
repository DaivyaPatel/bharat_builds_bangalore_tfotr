import boto3
import datetime
from typing import List, Dict, Any
from src.collector.redaction import process_config_item

DEFAULT_SALT = "driftlens_hackathon_salt_2026"

class ECSCollector:
    def __init__(self, region_name: str = "ap-south-1", salt: str = DEFAULT_SALT, client=None):
        self.client = client or boto3.client("ecs", region_name=region_name)
        self.salt = salt

    def collect(self, cluster_name: str = "default") -> List[Dict[str, Any]]:
        resources = []
        paginator = self.client.get_paginator('list_services')
        
        service_arns = []
        try:
            for page in paginator.paginate(cluster=cluster_name):
                service_arns.extend(page.get("serviceArns", []))
        except Exception:
            # Cluster might not exist or we lack permissions
            return resources

        if not service_arns:
            return resources

        # describe_services takes up to 10 services per call
        chunk_size = 10
        for i in range(0, len(service_arns), chunk_size):
            chunk = service_arns[i:i + chunk_size]
            resp = self.client.describe_services(cluster=cluster_name, services=chunk)
            
            for service in resp.get("services", []):
                logical_name = service.get("serviceName")
                service_arn = service.get("serviceArn")
                task_def_arn = service.get("taskDefinition")
                
                if not task_def_arn:
                    continue
                    
                # Describe the task definition to get container environment variables
                task_def_resp = self.client.describe_task_definition(taskDefinition=task_def_arn)
                task_def = task_def_resp.get("taskDefinition", {})
                
                # Extract container details
                containers_config = []
                for container in task_def.get("containerDefinitions", []):
                    container_name = container.get("name")
                    image = container.get("image")
                    
                    env_vars_dict = {}
                    for env in container.get("environment", []):
                        name = env.get("name")
                        value = env.get("value", "")
                        # Pipe through redaction module
                        env_vars_dict[name] = process_config_item(name, value, self.salt)
                        
                    containers_config.append({
                        "name": container_name,
                        "image": image,
                        "env_vars": env_vars_dict
                    })
                
                # Format datetime
                created_at = service.get("createdAt")
                if isinstance(created_at, datetime.datetime):
                    created_at_str = created_at.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    created_at_str = str(created_at) if created_at else None

                resource = {
                    "resource_type": "ecs_service",
                    "logical_name": logical_name,
                    "resource_arn": service_arn,
                    "config": {
                        "task_definition_arn": task_def_arn,
                        "containers": containers_config,
                        "created_at": created_at_str
                    }
                }
                resources.append(resource)
                
        return resources
