import os
import boto3
import json
from src.collector.lambda_collector import LambdaCollector
from src.collector.ssm_collector import SSMCollector
from src.collector.ecs_collector import ECSCollector
from src.collector.snapshot_writer import SnapshotWriter

def lambda_handler(event, context):
    """
    AWS Lambda entry point for the Collector stage.
    Expects event: {"environment": "staging"}
    """
    environment = event.get("environment", "unknown")
    print(f"Starting collector for environment: {environment}")
    
    # 1. Collect from all sources
    print("Collecting Lambda configurations...")
    lambda_coll = LambdaCollector()
    try:
        lambdas = lambda_coll.collect(environment=environment)
    except Exception as e:
        print(f"Error collecting Lambdas: {e}")
        lambdas = []
    
    print("Collecting SSM configurations...")
    ssm_coll = SSMCollector()
    try:
        ssms = ssm_coll.collect(path=f"/{environment}") # Parameter path usually scoped by env
    except Exception as e:
        print(f"Error collecting SSM parameters: {e}")
        ssms = {}
    
    print("Collecting ECS configurations...")
    ecs_coll = ECSCollector()
    try:
        # Assuming cluster name is the environment name for simplicity
        ecs_services = ecs_coll.collect(cluster_name=environment)
    except Exception as e:
        print(f"Error collecting ECS services: {e}")
        ecs_services = []
    
    # 2. Assemble the snapshot payload matching PRD 5.1
    snapshot_payload = {
        "metadata": {
            "environment": environment,
            "version": "1.0",
            "timestamp": "" 
        },
        "resources": lambdas + ecs_services,
        "parameters": ssms,
        "secrets": {},
        "feature_flags": {}
    }
    
    # 3. Write to S3
    bucket_name = os.environ.get("SNAPSHOT_BUCKET_NAME")
    if not bucket_name:
        # Fallback to the bucket we created in setup_s3_bucket.py
        sts = boto3.client("sts", region_name="ap-south-1")
        account_id = sts.get_caller_identity()["Account"]
        bucket_name = f"driftlens-snapshots-{account_id}"
        
    writer = SnapshotWriter(bucket_name=bucket_name, region_name="ap-south-1")
    s3_uri = writer.write_snapshot(environment, snapshot_payload)
    
    print(f"Successfully collected and wrote snapshot to {s3_uri}")
    
    # Pass the output to the next stage (Diff Engine)
    return {
        "environment": environment,
        "snapshot_s3_uri": s3_uri
    }
