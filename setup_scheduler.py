import boto3
import json
import time
import sys

def setup():
    region = "ap-south-1"
    iam = boto3.client('iam', region_name=region)
    scheduler = boto3.client('scheduler', region_name=region)
    sts = boto3.client('sts', region_name=region)
    
    try:
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        print("Error getting AWS Account ID. Are your credentials configured?")
        sys.exit(1)

    print("1. Creating IAM Role for EventBridge Scheduler...")
    role_name = "driftlens-scheduler-role"
    state_machine_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:DriftLensPipeline"
    
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "scheduler.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            })
        )
        # Give permission to StartExecution on our specific State Machine
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="StartDriftLensPipeline",
            PolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "states:StartExecution",
                    "Resource": state_machine_arn
                }]
            })
        )
        print("   ✅ Created IAM Role. Waiting 10 seconds for propagation...")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        print("   ✅ IAM Role already exists.")

    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    print("2. Creating EventBridge Scheduler Rule...")
    schedule_name = "DriftLensHourlyRun"
    
    try:
        # As required by DL-015: cron(0 * * * ? *)
        scheduler.create_schedule(
            Name=schedule_name,
            ScheduleExpression="cron(0 * * * ? *)",
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': state_machine_arn,
                'RoleArn': role_arn,
                # Pass the input payload to the state machine
                'Input': json.dumps(["staging", "production"])
            }
        )
        print(f"   ✅ Schedule '{schedule_name}' created successfully!")
    except scheduler.exceptions.ConflictException:
        # Update if it already exists
        scheduler.update_schedule(
            Name=schedule_name,
            ScheduleExpression="cron(0 * * * ? *)",
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': state_machine_arn,
                'RoleArn': role_arn,
                'Input': json.dumps(["staging", "production"])
            }
        )
        print(f"   ✅ Schedule '{schedule_name}' updated successfully!")
    except Exception as e:
        print(f"   ❌ Failed to create schedule: {e}")

    print("\n🎉 Scheduler Setup Complete!")
    print("The Step Functions pipeline will now automatically run at the top of every hour.")

if __name__ == "__main__":
    setup()
