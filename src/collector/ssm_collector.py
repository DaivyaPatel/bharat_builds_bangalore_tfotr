import boto3
import datetime
from typing import Dict, Any
from src.collector.redaction import process_config_item, redact_value

DEFAULT_SALT = "driftlens_hackathon_salt_2026"

class SSMCollector:
    def __init__(self, region_name: str = "ap-south-1", salt: str = DEFAULT_SALT, client=None):
        self.client = client or boto3.client("ssm", region_name=region_name)
        self.salt = salt

    def collect(self, path: str = "/") -> Dict[str, Any]:
        parameters = {}
        paginator = self.client.get_paginator('get_parameters_by_path')
        
        # We explicitly request WithoutDecryption to adhere to our strict IAM policy
        for page in paginator.paginate(Path=path, Recursive=True, WithDecryption=False):
            for param in page.get("Parameters", []):
                name = param.get("Name")
                param_type = param.get("Type")
                version = param.get("Version")
                last_modified = param.get("LastModifiedDate")
                value = param.get("Value", "")
                
                # Format datetime to match PRD iso8601 strings
                if isinstance(last_modified, datetime.datetime):
                    # boto3 returns tz-aware datetime. Convert to UTC ISO string with 'Z'
                    last_modified_str = last_modified.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    last_modified_str = str(last_modified)
                
                if param_type == "SecureString":
                    # For SecureString, AWS returns the ciphertext since WithDecryption=False.
                    # We drop the ciphertext and explicitly mark it redacted.
                    # We pass the empty string to redact_value so we don't hash the ciphertext.
                    redacted_payload = redact_value("", self.salt, "SecureString")
                    
                    parameters[name] = {
                        "value": redacted_payload["value"],
                        "type": param_type,
                        "version": version,
                        "last_modified": last_modified_str,
                        "redacted": redacted_payload["redacted"],
                        "value_sha256": redacted_payload["value_sha256"]
                    }
                else:
                    # For String or StringList, pipe it through our pattern heuristic redaction
                    processed = process_config_item(name, value, self.salt)
                    
                    param_dict = {
                        "value": processed["value"],
                        "type": param_type,
                        "version": version,
                        "last_modified": last_modified_str,
                        "redacted": processed["redacted"]
                    }
                    if processed["redacted"]:
                        param_dict["value_sha256"] = processed["value_sha256"]
                        
                    parameters[name] = param_dict
                    
        return parameters
