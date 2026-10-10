"""Receipt file storage: a local folder in development, S3 in production."""
import uuid
from pathlib import Path

from ..config import get_settings


def save_file(user_id: int, filename: str, data: bytes, content_type: str) -> str:
    settings = get_settings()
    ext = Path(filename).suffix.lower() or ".bin"
    key = f"receipts/{user_id}/{uuid.uuid4().hex}{ext}"
    if settings.s3_bucket:
        import boto3

        boto3.client("s3", region_name=settings.aws_region).put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256"
        )
    else:
        path = Path(settings.upload_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key


def read_file(key: str) -> bytes:
    settings = get_settings()
    if settings.s3_bucket:
        import boto3

        obj = boto3.client("s3", region_name=settings.aws_region).get_object(Bucket=settings.s3_bucket, Key=key)
        return obj["Body"].read()
    return (Path(settings.upload_dir) / key).read_bytes()
