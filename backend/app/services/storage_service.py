import logging
import os
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

s3_client = None

if S3_BUCKET_NAME and S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY:
    try:
        client_kwargs = {"service_name": "s3", "aws_access_key_id": S3_ACCESS_KEY_ID, "aws_secret_access_key": S3_SECRET_ACCESS_KEY, "region_name": S3_REGION, "config": Config(signature_version="s3v4")}
        if S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = S3_ENDPOINT_URL

        s3_client = boto3.client(**client_kwargs)
        logger.info(f"S3 client initialized for bucket: {S3_BUCKET_NAME}")
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")


def upload_file(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Uploads a file to an S3-compatible bucket (AWS S3 or Cloudflare R2).
    Returns the public URL of the uploaded file.
    Falls back to local storage if S3 env vars are not set.
    """
    ext = Path(filename).suffix or ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    if s3_client:
        try:
            s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=unique_filename, Body=file_bytes, ContentType=content_type)

            if S3_ENDPOINT_URL:
                # E.g., Cloudflare R2 with custom public domain or direct endpoint
                base_url = S3_ENDPOINT_URL.rstrip("/")
                # If using R2, standard virtual host format is typically not straightforward without a public dev domain,
                # so path-style or just pointing to endpoint/bucket/key is a safe default.
                # Many R2 setups use a public domain mapped to S3_ENDPOINT_URL.
                # Assuming base_url is the generic endpoint or a custom domain that serves the bucket
                return f"{base_url}/{S3_BUCKET_NAME}/{unique_filename}"
            else:
                # Standard AWS S3 URL
                return f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{unique_filename}"
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}. Falling back to local storage.")

    # Fallback to local storage (for local dev)
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    local_path = Path(UPLOAD_DIR) / unique_filename
    with open(local_path, "wb") as f:
        f.write(file_bytes)

    return f"/{UPLOAD_DIR}/{unique_filename}"
