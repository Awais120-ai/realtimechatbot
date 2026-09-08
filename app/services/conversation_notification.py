from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.conversation_notification import (
    ConversationNotificationRepository,
)


class ConversationNotificationService:

    def __init__(self, db: AsyncSession):
        self.repository = ConversationNotificationRepository(db)

    async def get_settings(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:

        is_muted = await self.repository.is_muted(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return not is_muted

    async def set_settings(
        self,
        conversation_id: int,
        user_id: int,
        notifications_enabled: bool,
    ) -> bool:

        state = await self.repository.set_muted(
            conversation_id=conversation_id,
            user_id=user_id,
            is_muted=not notifications_enabled,
        )

        return not state.is_muted

    async def is_muted(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:

        return await self.repository.is_muted(
            conversation_id=conversation_id,
            user_id=user_id,
        )