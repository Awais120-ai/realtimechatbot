from typing import Optional, List
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.notification import Notification


class NotificationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        title: str,
        body: str,
        type: str = "system",
        actor_id: Optional[int] = None,
        data: Optional[str] = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            actor_id=actor_id,
            title=title,
            body=body,
            type=type,
            data=data,
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def get_by_id(
        self,
        notification_id: int,
    ) -> Optional[Notification]:
        result = await self.db.execute(
            select(Notification)
            .options(joinedload(Notification.actor))
            .where(Notification.id == notification_id)
        )
        return result.scalars().first()

    async def get_user_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[Notification]:
        query = (
            select(Notification)
            .options(joinedload(Notification.actor))
            .where(Notification.user_id == user_id)
        )

        if unread_only:
            query = query.where(Notification.is_read.is_(False))

        query = (
            query.order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(
        self,
        user_id: int,
    ) -> int:
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one()

    async def mark_as_read(
        self,
        notification_id: int,
        user_id: int,
    ) -> Optional[Notification]:
        notification = await self.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            return None

        notification.is_read = True
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def mark_all_as_read(
        self,
        user_id: int,
    ) -> int:
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self.db.commit()
        return result.rowcount

    async def delete(
        self,
        notification_id: int,
        user_id: int,
    ) -> bool:
        notification = await self.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            return False

        await self.db.delete(notification)
        await self.db.commit()
        return True
