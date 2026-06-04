import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional
import boto3
from botocore.client import Config
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_notif import FileUpload


@dataclass
class StoredFile:
    upload: FileUpload
    key: str


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _ensure_bucket_sync(bucket: str) -> None:
    client = _client()
    existing = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
    if bucket not in existing:
        client.create_bucket(Bucket=bucket)


async def ensure_bucket(bucket: Optional[str] = None) -> None:
    await asyncio.to_thread(_ensure_bucket_sync, bucket or settings.s3_bucket)


async def store_upload(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    uploader_id: uuid.UUID | None,
    filename: str,
    mime_type: str,
    content: bytes,
    folder: str = "ocr",
) -> StoredFile:
    bucket = settings.s3_bucket
    await ensure_bucket(bucket)
    safe_name = filename.replace("\\", "_").replace("/", "_")
    key = f"tenants/{tenant_id}/{folder}/{uuid.uuid4()}-{safe_name}"

    await asyncio.to_thread(
        _client().put_object,
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=mime_type,
    )

    upload = FileUpload(
        tenant_id=tenant_id,
        uploader_id=uploader_id,
        bucket=bucket,
        key=key,
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(content),
    )
    db.add(upload)
    await db.flush()
    return StoredFile(upload=upload, key=key)


async def read_upload_bytes(upload: FileUpload) -> bytes:
    def _read() -> bytes:
        obj = _client().get_object(Bucket=upload.bucket, Key=upload.key)
        return obj["Body"].read()

    return await asyncio.to_thread(_read)
