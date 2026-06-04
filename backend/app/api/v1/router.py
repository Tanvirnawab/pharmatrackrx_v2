from fastapi import APIRouter
from app.api.v1 import (
    auth, transfer_orders, inward, discrepancies,
    reports, admin, notifications, scanning, intelligence, ocr,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(transfer_orders.router)
api_router.include_router(inward.router)
api_router.include_router(discrepancies.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
api_router.include_router(scanning.router)
api_router.include_router(intelligence.router)
api_router.include_router(ocr.router)
