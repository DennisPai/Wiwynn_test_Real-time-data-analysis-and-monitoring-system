from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.data import router as data_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.admin import router as admin_router
from app.api.v1.realtime import router as realtime_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(data_router)
api_router.include_router(analytics_router)
api_router.include_router(admin_router)
api_router.include_router(realtime_router)

# WS router 掛在根路徑（/ws/realtime），不走 /api/v1 prefix
# 由 main.py 直接 include（此處匯出供 main.py 使用）
__all__ = ["api_router", "ws_router"]
