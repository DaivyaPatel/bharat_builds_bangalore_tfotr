from src.collector.lambda_collector import LambdaCollector
import json

if __name__ == "__main__":
    # Ensure you are logged into AWS or have credentials set before running this!
    print("Collecting Lambda configurations...")
    collector = LambdaCollector()
    
    try:
        resources = collector.collect()
        print(f"Successfully collected {len(resources)} Lambda functions.")
        print(json.dumps(resources, indent=2))
    except Exception as e:
        print(f"Error fetching from AWS: {e}")
