import boto3
from typing import List, Dict, Any
from src.collector.redaction import process_config_item

# For the hackathon, a hardcoded salt is fine. 
# In a real app this would come from an environment variable or secrets manager.
DEFAULT_SALT = "driftlens_hackathon_salt_2026"

class LambdaCollector:
    def __init__(self, region_name: str = "ap-south-1", salt: str = DEFAULT_SALT, client=None):
        """
        Allows passing in a mocked client for testing.
        """
        self.client = client or boto3.client("lambda", region_name=region_name)
        self.salt = salt

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        paginator = self.client.get_paginator('list_functions')
        
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                logical_name = func.get("FunctionName")
                
                # Fetch full config per ticket DL-004 requirements
                try:
                    config_resp = self.client.get_function_configuration(FunctionName=logical_name)
                except Exception:
                    # Fallback to list_functions data if get_function_configuration fails
                    config_resp = func
                
                env_vars_dict = {}
                raw_env = config_resp.get("Environment", {}).get("Variables", {})
                
                for key, val in raw_env.items():
                    # Our redaction module automatically removes the plaintext if redacted
                    env_vars_dict[key] = process_config_item(key, val, self.salt)
                
                # Extract layer ARNs
                layers = []
                if config_resp.get("Layers"):
                    layers = [layer.get("Arn") for layer in config_resp.get("Layers", []) if layer.get("Arn")]
                
                resource = {
                    "resource_type": "lambda",
                    "logical_name": logical_name,
                    "resource_arn": config_resp.get("FunctionArn"),
                    "config": {
                        "env_vars": env_vars_dict,
                        "runtime": config_resp.get("Runtime"),
                        "memory_mb": config_resp.get("MemorySize"),
                        "timeout_s": config_resp.get("Timeout"),
                        "layers": layers,
                        "last_modified": config_resp.get("LastModified")
                    }
                }
                resources.append(resource)
                
        return resources
