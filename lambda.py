import boto3
import os
import json

s3_client = boto3.client('s3')

CONFIG_BUCKET = os.environ['CONFIG_BUCKET']
CONFIG_KEY = os.environ['CONFIG_KEY']

def load_config():
    obj = s3_client.get_object(Bucket=CONFIG_BUCKET, Key=CONFIG_KEY)
    return json.loads(obj['Body'].read())

def lambda_handler(event, context):
    config = load_config()
    source_bucket = config["source_bucket"]
    dest_bucket   = config["dest_bucket"]
    mappings      = config["mappings"]

    for record in event["Records"]:
        event_bucket = record["s3"]["bucket"]["name"]
        source_key   = record["s3"]["object"]["key"]

        if event_bucket != source_bucket:
            print(f"⚠️ Event bucket {event_bucket} does not match configured source {source_bucket}, skipping.")
            continue

        matched = False
        for rule in mappings:
            src_prefix  = rule["source_prefix"]
            dest_prefix = rule["dest_prefix"]

            if source_key.startswith(src_prefix):
                relative_path = source_key[len(src_prefix):]
                dest_key = f"{dest_prefix}{relative_path}"

                copy_source = {"Bucket": source_bucket, "Key": source_key}
                s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=dest_bucket,
                    Key=dest_key
                )

                print(f"✅ Copied {source_key} → {dest_bucket}/{dest_key}")
                matched = True
                break

        if not matched:
            print(f"⚠️ No matching prefix for {source_key}, skipping.")
