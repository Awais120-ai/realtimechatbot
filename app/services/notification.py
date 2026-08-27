import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationRead
from app.services.websocket_service import manager


class NotificationService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NotificationRepository(db)

    async def create_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        type: str = "system",
        actor_id: Optional[int] = None,
        data: Optional[str] = None,
    ) -> Notification:
        notification = await self.repo.create(
            user_id=user_id,
            title=title,
            body=body,
            type=type,
            actor_id=actor_id,
            data=data,
        )

        # Re-fetch to include relationships if needed
        full_notification = await self.repo.get_by_id(notification.id)
        if not full_notification:
            full_notification = notification

        # Construct realtime websocket payload
        payload = {
            "type": "new_notification",
            "notification": {
                "id": full_notification.id,
                "user_id": full_notification.user_id,
                "actor_id": full_notification.actor_id,
                "title": full_notification.title,
                "body": full_notification.body,
                "type": full_notification.type,
                "data": full_notification.data,
                "is_read": full_notification.is_read,
                "created_at": full_notification.created_at.isoformat(),
                "actor": (
                    {
                        "id": full_notification.actor.id,
                        "username": full_notification.actor.username,
                        "email": full_notification.actor.email,
                    }
                    if full_notification.actor
                    else None
                ),
            },
        }

        # Dispatch realtime notification via WebSocket if user is connected
        await manager.send_to_user(user_id=user_id, message=payload)

        return full_notification

    async def create_message_notifications(
        self,
        conversation_id: int,
        sender: User,
        member_ids: List[int],
        content: Optional[str] = None,
        message_type: str = "text",
    ) -> List[Notification]:
        notifications = []
        body_text = content if content else f"Sent a {message_type}"

        for recipient_id in member_ids:
            if recipient_id == sender.id:
                continue

            data_payload = json.dumps(
                {
                    "conversation_id": conversation_id,
                    "message_type": message_type,
                }
            )

            notification = await self.create_notification(
                user_id=recipient_id,
                actor_id=sender.id,
                title=f"New message from {sender.username}",
                body=body_text,
                type="new_message",
                data=data_payload,
            )
            notifications.append(notification)

        return notifications

    async def get_user_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[Notification]:
        return await self.repo.get_user_notifications(
            user_id=user_id,
            skip=skip,
            limit=limit,
            unread_only=unread_only,
        )

    async def get_unread_count(
        self,
        user_id: int,
    ) -> int:
        return await self.repo.get_unread_count(user_id=user_id)

    async def mark_as_read(
        self,
        notification_id: int,
        user_id: int,
    ) -> Optional[Notification]:
        return await self.repo.mark_as_read(
            notification_id=notification_id,
            user_id=user_id,
        )

    async def mark_all_as_read(
        self,
        user_id: int,
    ) -> int:
        return await self.repo.mark_all_as_read(user_id=user_id)

    async def delete_notification(
        self,
        notification_id: int,
        user_id: int,
    ) -> bool:
        return await self.repo.delete(
            notification_id=notification_id,
            user_id=user_id,
        )
