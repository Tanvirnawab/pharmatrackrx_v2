import uuid
from redis.asyncio import Redis
from app.core.config import settings

QUEUE_NAME = "pharmatrackrx:ocr_jobs"


async def enqueue_ocr_job(job_id: uuid.UUID) -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.rpush(QUEUE_NAME, str(job_id))
    finally:
        await redis.aclose()


async def dequeue_ocr_job(timeout: int = 5) -> str | None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        item = await redis.blpop(QUEUE_NAME, timeout=timeout)
        if not item:
            return None
        return item[1]
    finally:
        await redis.aclose()
