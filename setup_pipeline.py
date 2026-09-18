import boto3
import json
import zipfile
import os
import io
import time
import sys

def create_lambda_zip() -> bytes:
    """Zips the src folder for deployment."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for root, _, files in os.walk("src"):
            for file in files:
                if file.endswith(".pyc") or "__pycache__" in root:
                    continue
                file_path = os.path.join(root, file)
                zip_file.write(file_path, file_path)
    return zip_buffer.getvalue()

def create_dummy_zip() -> bytes:
    """Creates a basic dummy lambda function for stubbing future stages."""
    code = """
def lambda_handler(event, context):
    print("Dummy lambda invoked with event:", event)
    return {"status": "success", "event": event}
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("lambda_handler.py", code)
    return zip_buffer.getvalue()

def setup():
    region = "ap-south-1"
    iam = boto3.client('iam', region_name=region)
    lam = boto3.client('lambda', region_name=region)
    sfn = boto3.client('stepfunctions', region_name=region)
    sts = boto3.client('sts', region_name=region)
    
    try:
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        print("Error getting AWS Account ID. Are your credentials configured?")
        sys.exit(1)

    print("1. Creating Lambda Execution Role...")
    role_name = "driftlens-lambda-role"
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"}
                }]
            })
        )
        # Attach basic permissions + S3/SSM/ECS for the collector
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess")
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess")
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonECS_FullAccess")
        print("   ✅ Created IAM Role. Waiting 10 seconds for propagation...")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        print("   ✅ IAM Role already exists.")

    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    print("2. Deploying Lambdas...")
    lambda_arns = {}
    
    # We will use Python 3.10 as standard
    lambdas_to_create = [
        {"name": "driftlens-collector", "handler": "src.collector_handler.lambda_handler", "zip": create_lambda_zip()},
        {"name": "driftlens-diff", "handler": "lambda_handler.lambda_handler", "zip": create_dummy_zip()},
        {"name": "driftlens-attribute", "handler": "lambda_handler.lambda_handler", "zip": create_dummy_zip()},
        {"name": "driftlens-persist", "handler": "lambda_handler.lambda_handler", "zip": create_dummy_zip()},
    ]

    for func in lambdas_to_create:
        try:
            resp = lam.create_function(
                FunctionName=func["name"],
                Runtime="python3.10",
                Role=role_arn,
                Handler=func["handler"],
                Code={"ZipFile": func["zip"]},
                Timeout=60,
                Environment={"Variables": {"SNAPSHOT_BUCKET_NAME": f"driftlens-snapshots-{account_id}"}}
            )
            lambda_arns[func["name"]] = resp["FunctionArn"]
            print(f"   ✅ Created Lambda: {func['name']}")
        except lam.exceptions.ResourceConflictException:
            # Update code if exists
            lam.update_function_code(FunctionName=func["name"], ZipFile=func["zip"])
            # Update environment variables just in case
            lam.update_function_configuration(
                FunctionName=func["name"], 
                Environment={"Variables": {"SNAPSHOT_BUCKET_NAME": f"driftlens-snapshots-{account_id}"}}
            )
            resp = lam.get_function(FunctionName=func["name"])
            lambda_arns[func["name"]] = resp["Configuration"]["FunctionArn"]
            print(f"   ✅ Updated Lambda: {func['name']}")

    print("3. Creating Step Functions Role...")
    sfn_role_name = "driftlens-sfn-role"
    try:
        iam.create_role(
            RoleName=sfn_role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "states.amazonaws.com"}
                }]
            })
        )
        iam.attach_role_policy(RoleName=sfn_role_name, PolicyArn="arn:aws:iam::aws:policy/AWSLambda_FullAccess")
        print("   ✅ Created Step Functions Role. Waiting 10 seconds for propagation...")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        print("   ✅ Step Functions Role already exists.")

    sfn_role_arn = f"arn:aws:iam::{account_id}:role/{sfn_role_name}"

    print("4. Deploying Step Functions State Machine...")
    with open("state_machine.asl.json", "r") as f:
        asl = f.read()
    
    # Replace templates with actual ARNs
    asl = asl.replace("${CollectorLambdaArn}", lambda_arns["driftlens-collector"])
    asl = asl.replace("${DiffLambdaArn}", lambda_arns["driftlens-diff"])
    asl = asl.replace("${AttributeLambdaArn}", lambda_arns["driftlens-attribute"])
    asl = asl.replace("${PersistLambdaArn}", lambda_arns["driftlens-persist"])

    state_machine_name = "DriftLensPipeline"
    try:
        sfn.create_state_machine(
            name=state_machine_name,
            definition=asl,
            roleArn=sfn_role_arn
        )
        print("   ✅ State Machine created successfully!")
    except sfn.exceptions.StateMachineAlreadyExists:
        sfn_arn = f"arn:aws:states:ap-south-1:{account_id}:stateMachine:{state_machine_name}"
        sfn.update_state_machine(stateMachineArn=sfn_arn, definition=asl, roleArn=sfn_role_arn)
        print("   ✅ State Machine updated successfully!")

    print("\n🎉 Pipeline Deployment Complete!")
    print("Go to the AWS Console, open Step Functions, and execute 'DriftLensPipeline' with the following input:")
    print('[\"staging\", \"production\"]')

if __name__ == "__main__":
    setup()
