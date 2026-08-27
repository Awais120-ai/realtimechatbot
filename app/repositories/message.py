from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        conversation_id: int,
        sender_id: int,
        content: str | None,
        message_type: str = "text",
        file_url: str | None = None,
        file_name: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
    ) -> Message:

        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )

        self.db.add(message)

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_by_id(
        self,
        message_id: int,
    ) -> Optional[Message]:

        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.sender))
            .where(Message.id == message_id)
        )

        return result.scalars().first()

    async def get_by_conversation(
        self,
        conversation_id: int,
    ):

        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.sender))
            .where(
                Message.conversation_id == conversation_id,
                Message.is_deleted.is_(False),
            )
            .order_by(Message.created_at)
        )

        return result.scalars().all()

    async def mark_as_read(
        self,
        message_id: int,
    ) -> Message | None:

        message = await self.get_by_id(message_id)

        if not message:
            return None

        message.is_read = True

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_unread_count(
        self,
        conversation_id: int,
        user_id: int,
    ) -> int:

        result = await self.db.execute(
            select(func.count(Message.id))
            .where(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.is_read.is_(False),
            )
        )

        return result.scalar_one()

    async def edit_message(
        self,
        message_id: int,
        new_content: str,
    ) -> Message | None:

        message = await self.get_by_id(message_id)

        if not message:
            return None

        message.content = new_content
        message.is_edited = True
        message.edited_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def delete_message(
        self,
        message_id: int,
    ) -> Message | None:    

        message = await self.get_by_id(message_id)

        if not message:
            return None

        message.is_deleted = True
        message.content = None

        await self.db.commit()
        await self.db.refresh(message)

        return message