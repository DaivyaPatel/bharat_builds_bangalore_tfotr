import boto3
import sys

def setup_bucket():
    region = "ap-south-1"
    sts = boto3.client('sts', region_name=region)
    s3 = boto3.client('s3', region_name=region)
    
    try:
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        print("Error getting AWS Account ID. Are your credentials configured?")
        print(e)
        sys.exit(1)
        
    bucket_name = f"driftlens-snapshots-{account_id}"
    
    print(f"1. Creating bucket: {bucket_name}")
    try:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
        print("   ✅ Bucket created.")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print("   ✅ Bucket already exists and you own it.")
    except Exception as e:
        print(f"   ❌ Failed to create bucket: {e}")
        sys.exit(1)
        
    print("2. Enabling Bucket Versioning...")
    try:
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        print("   ✅ Versioning enabled.")
    except Exception as e:
        print(f"   ❌ Failed to enable versioning: {e}")
        
    print("3. Enabling Block Public Access (High Security)...")
    try:
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )
        print("   ✅ Public Access Blocked successfully.")
    except Exception as e:
        print(f"   ❌ Failed to block public access: {e}")
        
    print("\n🎉 Setup Complete!")
    print(f"Your Snapshot Bucket Name is: {bucket_name}")
    
if __name__ == "__main__":
    setup_bucket()
