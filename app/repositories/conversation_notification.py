from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_notification_state import (
    ConversationNotificationState,
)


class ConversationNotificationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_state(
        self,
        conversation_id: int,
        user_id: int,
    ) -> ConversationNotificationState | None:

        result = await self.db.execute(
            select(ConversationNotificationState).where(
                ConversationNotificationState.conversation_id
                == conversation_id,
                ConversationNotificationState.user_id
                == user_id,
            )
        )

        return result.scalar_one_or_none()

    async def is_muted(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:

        state = await self.get_state(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if not state:
            return False

        return bool(state.is_muted)

    async def set_muted(
        self,
        conversation_id: int,
        user_id: int,
        is_muted: bool,
    ) -> ConversationNotificationState:

        state = await self.get_state(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        now = datetime.now(timezone.utc)

        if state:
            state.is_muted = is_muted
            state.updated_at = now

        else:
            state = ConversationNotificationState(
                conversation_id=conversation_id,
                user_id=user_id,
                is_muted=is_muted,
                updated_at=now,
            )

            self.db.add(state)

        await self.db.commit()
        await self.db.refresh(state)

        return state