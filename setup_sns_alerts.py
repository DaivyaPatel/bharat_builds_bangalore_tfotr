import boto3
import json
import sys

def setup_sns_alerts(email_address: str):
    region = "ap-south-1"
    sns = boto3.client('sns', region_name=region)
    events = boto3.client('events', region_name=region)
    sts = boto3.client('sts', region_name=region)

    account_id = sts.get_caller_identity()["Account"]

    print("1. Creating SNS Topic for Critical Drift Alerts...")
    topic_name = "DriftLens-Critical-Alerts"
    topic_response = sns.create_topic(Name=topic_name)
    topic_arn = topic_response['TopicArn']
    print(f"   ✅ Created Topic: {topic_arn}")

    print(f"2. Subscribing {email_address} to Topic...")
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol='email',
        Endpoint=email_address
    )
    print("   ✅ Subscribed! (You must click the confirmation link in your email).")

    print("3. Allowing EventBridge to publish to the SNS Topic...")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowEventBridgePublish",
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sns:Publish",
                "Resource": topic_arn
            }
        ]
    }
    sns.set_topic_attributes(
        TopicArn=topic_arn,
        AttributeName='Policy',
        AttributeValue=json.dumps(policy)
    )

    print("4. Creating EventBridge Rule for Critical Drift...")
    rule_name = "DriftLens-Critical-Drift-Rule"
    # Matches events where source is "driftlens" and severity is "critical"
    event_pattern = {
        "source": ["driftlens"],
        "detail-type": ["DriftDetected"],
        "detail": {
            "severity": ["critical"]
        }
    }
    
    events.put_rule(
        Name=rule_name,
        EventPattern=json.dumps(event_pattern),
        State='ENABLED',
        Description='Triggers on critical drift from DriftLens'
    )

    print("5. Adding SNS Topic as Target for the Rule...")
    events.put_targets(
        Rule=rule_name,
        Targets=[
            {
                'Id': 'SNSAlertTarget',
                'Arn': topic_arn,
                'InputTransformer': {
                    'InputPathsMap': {
                        'environment': '$.detail.environment',
                        'resource': '$.detail.resource_arn',
                        'message': '$.detail.message'
                    },
                    'InputTemplate': '"\u26A0\uFE0F CRITICAL DRIFT DETECTED in <environment>!\nResource: <resource>\nDetails: <message>\nCheck DriftLens dashboard immediately."'
                }
            }
        ]
    )
    print("   ✅ EventBridge Rule configured successfully!")
    print("\n🎉 Setup Complete!")
    print(f"Make sure Dev B adds an EventBridge PutEvents call to their Lambda when critical drift happens!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup_sns_alerts.py <your-email@example.com>")
        sys.exit(1)
    setup_sns_alerts(sys.argv[1])
