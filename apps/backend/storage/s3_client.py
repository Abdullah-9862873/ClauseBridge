import boto3  # type: ignore[import-untyped]
from botocore.client import Config  # type: ignore[import-untyped]

from core.config import settings

s3 = boto3.client(
    "s3",
    endpoint_url=settings.supabase_storage_endpoint,
    aws_access_key_id=settings.supabase_storage_access_key,
    aws_secret_access_key=settings.supabase_storage_secret,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def generate_presigned_upload_url(
    key: str, content_type: str, expires: int = 60
) -> str:
    url: str = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.supabase_storage_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
    )
    return url


def download_object(key: str) -> bytes:
    response = s3.get_object(
        Bucket=settings.supabase_storage_bucket,
        Key=key,
    )
    body: bytes = response["Body"].read()
    return body
