from app.models import conversation_user_state
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func,or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation_user_state import ConversationUserState

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

    async def get_by_conversation(self, conversation_id, user_id):
     query = (
        select(Message)
        .options(selectinload(Message.sender))
        .outerjoin(
            ConversationUserState,
            (
                ConversationUserState.conversation_id
                == Message.conversation_id
            )
            & (
                ConversationUserState.user_id
                == user_id
            ),
        )
        .where(
            Message.conversation_id == conversation_id,
            Message.is_deleted.is_(False),
        )
        .where(
            or_(
                ConversationUserState.cleared_at.is_(None),
                Message.created_at > ConversationUserState.cleared_at,
            )
        )
        .order_by(Message.created_at.asc())
     )

     result = await self.db.execute(query)

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


    async def clear_conversation(self, conversation_id, user_id):
    # Get messages currently visible to this user
     messages = await self.get_by_conversation(
        conversation_id,
        user_id,
     )

     cleared_count = len(messages)

    # Check whether this user already has a state
     result = await self.db.execute(
        select(ConversationUserState).where(
            ConversationUserState.conversation_id == conversation_id,
            ConversationUserState.user_id == user_id,
        )
    )

     state = result.scalar_one_or_none()

    # Current time
     now = datetime.now(timezone.utc)

     if state:
        state.cleared_at = now
     else:
        state = ConversationUserState(
            conversation_id=conversation_id,
            user_id=user_id,
            cleared_at=now,
        )
        self.db.add(state)

     await self.db.commit()

     return cleared_count