from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import conversation_members
from app.repositories.message import MessageRepository
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import MessageCreate


class MessageService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MessageRepository(db)
        self.conversation_repository = ConversationRepository(db)

    async def _check_membership(
        self,
        conversation_id: int,
        user_id: int,
    ):
        result = await self.db.execute(
            select(conversation_members.c.user_id).where(
                conversation_members.c.conversation_id == conversation_id,
                conversation_members.c.user_id == user_id,
            )
        )

        member_id = result.scalar_one_or_none()

        if member_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation.",
            )

    async def create_message(
        self,
        message_in: MessageCreate,
        sender_id: int,
    ):
        conversation = await self.conversation_repository.get_by_id(
            message_in.conversation_id
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        await self._check_membership(
            conversation_id=message_in.conversation_id,
            user_id=sender_id,
        )

        return await self.repository.create(
            conversation_id=message_in.conversation_id,
            sender_id=sender_id,
            content=message_in.content,
            message_type=message_in.message_type,
            file_url=message_in.file_url,
            file_name=message_in.file_name,
            file_size=message_in.file_size,
            mime_type=message_in.mime_type,
        )

    async def get_messages(
        self,
        conversation_id: int,
        user_id: int,
    ):
        conversation = await self.conversation_repository.get_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        await self._check_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return await self.repository.get_by_conversation(
            conversation_id,
            user_id,
        )   

    async def get_message(
        self,
        message_id: int,
    ):
        message = await self.repository.get_by_id(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found.",
            )

        return message

    async def mark_message_as_read(
        self,
        message_id: int,
        user_id: int,
    ):
        message = await self.repository.get_by_id(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found.",
            )

        await self._check_membership(
            conversation_id=message.conversation_id,
            user_id=user_id,
        )

        message = await self.repository.mark_as_read(message_id)

        return message

    async def get_unread_count(
        self,
        conversation_id: int,
        user_id: int,
    ) -> int:

        conversation = await self.conversation_repository.get_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        await self._check_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return await self.repository.get_unread_count(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    # =========================================================
    # 3 MINUTE EDIT / DELETE LIMIT
    # =========================================================

    async def _check_message_modify_time(self, message):
        """
        A message can only be edited or deleted within
        3 minutes of its original creation time.
        """

        if not message.created_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message modification time could not be determined.",
            )

        created_at = message.created_at

        # Database may return a naive datetime.
        # Treat it as UTC.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        elapsed_time = now - created_at

        if elapsed_time > timedelta(minutes=3):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Messages can only be edited or deleted "
                    "within 3 minutes of sending."
                ),
            )

    async def edit_message(
        self,
        message_id: int,
        user_id: int,
        content: str,
    ):
        message = await self.repository.get_by_id(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found.",
            )

        # Only message owner can edit
        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own messages.",
            )

        # Deleted messages cannot be edited
        if message.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deleted messages cannot be edited.",
            )

        # Message cannot be empty
        if not content or not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content cannot be empty.",
            )

        # =====================================================
        # 3 MINUTE LIMIT
        # =====================================================
        await self._check_message_modify_time(message)

        return await self.repository.edit_message(
            message_id=message_id,
            new_content=content.strip(),
        )

    async def delete_message(
        self,
        message_id: int,
        user_id: int,
    ):
        message = await self.repository.get_by_id(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found.",
            )

        # Only message owner can delete
        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own messages.",
            )

        # Already deleted
        if message.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is already deleted.",
            )

        # =====================================================
        # 3 MINUTE LIMIT
        # =====================================================
        await self._check_message_modify_time(message)

        return await self.repository.delete_message(
            message_id=message_id,
        )

    async def clear_session(
        self,
        conversation_id: int,
        user_id: int,
    ):
        # Make sure current user belongs to this conversation
        await self._check_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        cleared_count = await self.repository.clear_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return {
            "conversation_id": conversation_id,
            "cleared_count": cleared_count,
        }