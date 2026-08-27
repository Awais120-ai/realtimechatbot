from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, chat, websocket, upload, notifications

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"],
)

api_router.include_router(
    upload.router,
    prefix="/chat",
    tags=["chat upload"],
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["notifications"],
)

api_router.include_router(
    websocket.router,
    tags=["websocket"],
)