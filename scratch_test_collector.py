from src.collector.lambda_collector import LambdaCollector
from src.collector.ssm_collector import SSMCollector
from src.collector.ecs_collector import ECSCollector
import json

if __name__ == "__main__":
    # Ensure you are logged into AWS or have credentials set before running this!
    print("Collecting Lambda configurations...")
    lambda_collector = LambdaCollector()
    
    try:
        lambda_resources = lambda_collector.collect()
        print(f"Successfully collected {len(lambda_resources)} Lambda functions.")
        print(json.dumps(lambda_resources, indent=2))
    except Exception as e:
        print(f"Error fetching Lambda from AWS: {e}")
        
    print("\nCollecting SSM parameters...")
    ssm_collector = SSMCollector()
    try:
        ssm_params = ssm_collector.collect(path="/")
        print(f"Successfully collected {len(ssm_params)} SSM parameters.")
        print(json.dumps(ssm_params, indent=2))
    except Exception as e:
        print(f"Error fetching SSM from AWS: {e}")
        
    print("\nCollecting ECS services...")
    ecs_collector = ECSCollector()
    try:
        ecs_resources = ecs_collector.collect(cluster_name="default")
        print(f"Successfully collected {len(ecs_resources)} ECS services.")
        print(json.dumps(ecs_resources, indent=2))
    except Exception as e:
        print(f"Error fetching ECS from AWS: {e}")
