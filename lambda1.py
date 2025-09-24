import boto3
import os

s3_client = boto3.client('s3')

SOURCE_BUCKET = os.environ['SOURCE_BUCKET']
DEST_BUCKET   = os.environ['DEST_BUCKET']
SOURCE_PREFIX = os.environ['SOURCE_PREFIX']
DEST_PREFIX   = os.environ['DEST_PREFIX']

def lambda_handler(event, context):
    for record in event["Records"]:
        event_bucket = record["s3"]["bucket"]["name"]
        source_key   = record["s3"]["object"]["key"]

        if event_bucket != SOURCE_BUCKET or not source_key.startswith(SOURCE_PREFIX):
            print(f"⚠️ Skipping {event_bucket}/{source_key}, not matching this Lambda config")
            continue

        relative_path = source_key[len(SOURCE_PREFIX):]
        dest_key = f"{DEST_PREFIX}{relative_path}"

        copy_source = {"Bucket": SOURCE_BUCKET, "Key": source_key}
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=DEST_BUCKET,
            Key=dest_key
        )

        print(f"✅ Copied {source_key} → {DEST_BUCKET}/{dest_key}")
