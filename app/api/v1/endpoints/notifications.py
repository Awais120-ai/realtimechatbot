from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationRead,
    NotificationCreate,
    UnreadNotificationCount,
)
from app.services.notification import NotificationService

router = APIRouter()


@router.get("/", response_model=List[NotificationRead])
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    return await service.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count", response_model=UnreadNotificationCount)
async def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.get_unread_count(user_id=current_user.id)
    return UnreadNotificationCount(unread_count=count)


@router.put("/read-all")
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.mark_all_as_read(user_id=current_user.id)
    return {
        "message": "All notifications marked as read",
        "updated_count": count,
    }


@router.put("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notification = await service.mark_as_read(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return notification


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    success = await service.delete_notification(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"message": "Notification deleted successfully"}


@router.post("/", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_in: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notification = await service.create_notification(
        user_id=notification_in.user_id,
        title=notification_in.title,
        body=notification_in.body,
        type=notification_in.type,
        actor_id=notification_in.actor_id or current_user.id,
        data=notification_in.data,
    )
    return notification
