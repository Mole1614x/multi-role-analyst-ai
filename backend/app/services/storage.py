import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import boto3

from app.core.config import settings


def client():
    return boto3.client("s3", endpoint_url=settings().s3_endpoint or None)


def local_path(key: str) -> Path:
    root = settings().storage_dir.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("Invalid object key.")
    return path


def put(key: str, content: bytes):
    config = settings()
    if config.s3_bucket:
        client().put_object(Bucket=config.s3_bucket, Key=key, Body=content)
        return
    path = local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp_path = file.name
        file.write(content)
    try:
        os.replace(temp_path, path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def read(key: str) -> bytes:
    config = settings()
    if config.s3_bucket:
        body = client().get_object(Bucket=config.s3_bucket, Key=key)["Body"]
        try:
            return body.read()
        finally:
            body.close()
    return local_path(key).read_bytes()


def remove(key: str):
    config = settings()
    if config.s3_bucket:
        client().delete_object(Bucket=config.s3_bucket, Key=key)
    else:
        local_path(key).unlink(missing_ok=True)
