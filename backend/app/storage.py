"""Private AWS S3 only. Credentials come from boto3's standard credential chain."""
import boto3
from botocore.config import Config

from .config import settings


def client():
    cfg = settings()

    return boto3.client(
        "s3",
        region_name=cfg.aws_region,
        endpoint_url=f"https://s3.{cfg.aws_region}.amazonaws.com",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 3},
        ),
    )


def presign(method, params, seconds=3600):
    return client().generate_presigned_url(
        method,
        Params={"Bucket": settings().s3_bucket, **params},
        ExpiresIn=seconds,
    )