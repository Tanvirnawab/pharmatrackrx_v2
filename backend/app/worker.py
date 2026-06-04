import asyncio
import uuid

from app.db.session import AsyncSessionLocal
from app.services.ocr_queue_service import dequeue_ocr_job
from app.services.ocr_document_service import process_ocr_job


async def main() -> None:
    print("PharmaTrackRx worker started")
    while True:
        job_id = await dequeue_ocr_job()
        if not job_id:
            continue
        try:
            async with AsyncSessionLocal() as db:
                await process_ocr_job(db, uuid.UUID(job_id))
                await db.commit()
        except Exception as exc:
            print(f"OCR job {job_id} failed in worker: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
