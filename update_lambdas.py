import os
import boto3
import zipfile
import time
from botocore.exceptions import ClientError

def create_zip():
    print("Creating zip file of src/ directory...")
    zip_path = "lambda_payload.zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk("src"):
            if "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".pyc"):
                    continue
                file_path = os.path.join(root, file)
                zf.write(file_path, file_path)
    return zip_path

def wait_for_lambda(client, function_name):
    print(f"Waiting for {function_name} to be ready...")
    waiter = client.get_waiter('function_updated_v2')
    waiter.wait(FunctionName=function_name)

def update_lambda(function_name, zip_path, handler_name):
    client = boto3.client('lambda', region_name='ap-south-1')
    print(f"Updating {function_name} with {handler_name}...")
    
    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()
        
    try:
        wait_for_lambda(client, function_name)
        
        print(f"Updating configuration for {function_name}...")
        client.update_function_configuration(
            FunctionName=function_name,
            Handler=handler_name
        )
        
        wait_for_lambda(client, function_name)
        
        print(f"Updating code for {function_name}...")
        client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_bytes
        )
        print(f"Successfully updated {function_name}")
    except ClientError as e:
        print(f"Failed to update {function_name}: {e}")

if __name__ == "__main__":
    zip_path = create_zip()
    update_lambda("driftlens-collector", zip_path, "src.collector_handler.lambda_handler")
    update_lambda("driftlens-diff", zip_path, "src.diff_handler.lambda_handler")
    update_lambda("driftlens-attribute", zip_path, "src.attribute_handler.lambda_handler")
    update_lambda("driftlens-persist", zip_path, "src.persist_handler.lambda_handler")
    print("All lambdas updated successfully!")
    if os.path.exists(zip_path):
        os.remove(zip_path)
