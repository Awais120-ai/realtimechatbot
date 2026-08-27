import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Conversation, conversation_members
from app.models.message import Message
from app.models.notification import Notification


class ConversationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(
    self,
    user_id: int,
) -> list[Conversation]:

    # =========================================================
    # 1. Conversations where user is an actual member
    # =========================================================

     member_result = await self.db.execute(
        select(
            conversation_members.c.conversation_id
        ).where(
            conversation_members.c.user_id == user_id
        )
    )

     conversation_ids = {
        int(row[0])
        for row in member_result.fetchall()
    }

    # =========================================================
    # 2. Old conversations where this user has sent messages
    # =========================================================

     sent_message_result = await self.db.execute(
        select(
            Message.conversation_id
        )
        .where(
            Message.sender_id == user_id
        )
        .distinct()
    )

     conversation_ids.update(
        int(row[0])
        for row in sent_message_result.fetchall()
    )

    # =========================================================
    # 3. Old conversations where this user received
    #    a message notification
    #
    # This repairs the case where an old conversation exists
    # but the conversation_members row is missing.
    # =========================================================

     notification_result = await self.db.execute(
        select(
            Notification.data
        ).where(
            Notification.user_id == user_id,
            Notification.type == "new_message",
        )
    )

     for row in notification_result.fetchall():

        notification_data = row[0]

        if not notification_data:
            continue

        try:
            if isinstance(
                notification_data,
                str,
            ):
                notification_data = json.loads(
                    notification_data
                )

            conversation_id = (
                notification_data.get(
                    "conversation_id"
                )
                or notification_data.get(
                    "conversationId"
                )
            )

            if conversation_id:
                conversation_ids.add(
                    int(conversation_id)
                )

        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            continue

    # =========================================================
    # 4. No conversations
    # =========================================================

     if not conversation_ids:
        return []

    # =========================================================
    # 5. Fetch ALL historical conversations
    # =========================================================

     latest_message_time = (
    select(
        Message.conversation_id.label(
            "conversation_id"
        ),
        func.max(
            Message.created_at
        ).label(
            "latest_message_at"
        ),
    )
    .where(
        Message.conversation_id.in_(
            conversation_ids
        )
    )
    .group_by(
        Message.conversation_id
    )
    .subquery()
)

     result = await self.db.execute(
        select(Conversation)
        .outerjoin(
            latest_message_time,
            latest_message_time.c.conversation_id
            == Conversation.id,
        )
    .where(
        Conversation.id.in_(
            conversation_ids
        )
    )
    .order_by(
        latest_message_time.c.latest_message_at.desc().nullslast(),
        Conversation.created_at.desc(),
    )
)

     return list(
         result.scalars().all()
    )

    async def create(
        self,
        title: str | None = None,
        is_group: bool = False,
    ) -> Conversation:
        conversation = Conversation(
            title=title,
            is_group=is_group,
        )

        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        return conversation

    async def get_by_id(
        self,
        conversation_id: int,
    ) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id
            )
        )

        return result.scalars().first()

    async def get_all(self) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation).order_by(
                Conversation.created_at.desc()
            )
        )

        return list(result.scalars().all())

    async def delete(
        self,
        conversation: Conversation,
    ) -> None:
        await self.db.delete(conversation)
        await self.db.commit()