from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Conversation, conversation_members
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import ConversationCreate



class ConversationService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ConversationRepository(db)

    async def create_conversation(
        self,
        conversation_in: ConversationCreate,
        current_user_id: int,
    ):
        participant_id = conversation_in.participant_id

        # =====================================================
        # DIRECT CHAT
        # =====================================================

        if not conversation_in.is_group and participant_id:
            participant_id = int(participant_id)

            # User apne aap se chat nahi bana sakta
            if participant_id == int(current_user_id):
                raise ValueError(
                    "You cannot create a conversation with yourself."
                )

            # Check participant exists
            user_result = await self.db.execute(
                select(User).where(User.id == participant_id)
            )

            participant = user_result.scalar_one_or_none()

            if participant is None:
                raise ValueError("Selected user does not exist.")

            # =================================================
            # EXISTING DIRECT CONVERSATION CHECK
            # =================================================

            existing_result = await self.db.execute(
                select(Conversation)
                .join(
                    conversation_members,
                    conversation_members.c.conversation_id
                    == Conversation.id,
                )
                .where(
                    conversation_members.c.user_id
                    == current_user_id
                )
                .where(
                    Conversation.is_group.is_(False)
                )
                .where(
                    Conversation.id.in_(
                        select(
                            conversation_members.c.conversation_id
                        ).where(
                            conversation_members.c.user_id
                            == participant_id
                        )
                    )
                )
                .order_by(Conversation.created_at.desc())
            )

            existing_conversation = (
                existing_result.scalars().first()
            )

            # Existing chat hai to duplicate mat banao
            if existing_conversation:
                return existing_conversation

        # =====================================================
        # CREATE NEW CONVERSATION
        # =====================================================

        conversation = await self.repository.create(
            title=conversation_in.title,
            is_group=conversation_in.is_group,
        )

        # =====================================================
        # ADD CREATOR
        # =====================================================

        await self.db.execute(
            insert(conversation_members).values(
                conversation_id=conversation.id,
                user_id=current_user_id,
            )
        )

        # =====================================================
        # ADD SELECTED PARTICIPANT
        # =====================================================

        if (
            not conversation_in.is_group
            and participant_id
        ):
            await self.db.execute(
                insert(conversation_members).values(
                    conversation_id=conversation.id,
                    user_id=participant_id,
                )
            )

        await self.db.commit()
        await self.db.refresh(conversation)

        return conversation

    async def get_conversation(
        self,
        conversation_id: int,
    ):
        return await self.repository.get_by_id(conversation_id)

    async def get_conversations(
        self,
        user_id: int,
    ):
        conversations = await self.repository.get_by_user_id(
            user_id
        )

        result = []

        for conversation in conversations:

            other_user = None

            # =====================================================
            # DIRECT CHAT
            # Find the other member of this conversation
            # =====================================================

            if not conversation.is_group:

                member_result = await self.db.execute(
                    select(User)
                    .join(
                        conversation_members,
                        User.id
                        == conversation_members.c.user_id,
                    )
                    .where(
                        conversation_members.c.conversation_id
                        == conversation.id
                    )
                    .where(
                        User.id != user_id
                    )
                )

                other_user = (
                    member_result.scalars().first()
                )

            # =====================================================
            # ADD THIS CONVERSATION TO RESULT
            # =====================================================

            result.append(
                {
                    "id": conversation.id,
                    "title": conversation.title,
                    "is_group": conversation.is_group,
                    "created_at": conversation.created_at,
                    "other_user": other_user,
                }
            )

        # =========================================================
        # RETURN ALL CONVERSATIONS
        # =========================================================

        return result

    async def delete_conversation(
        self,
        conversation_id: int,
    ):
        conversation = await self.repository.get_by_id(
            conversation_id
        )

        if not conversation:
            return None

        await self.repository.delete(conversation)

        return conversation

    async def add_member(
        self,
        conversation_id: int,
        user_id: int,
    ):
        conversation = await self.repository.get_by_id(
            conversation_id
        )

        if not conversation:
            return None

        # Prevent duplicate membership
        existing = await self.db.execute(
            select(conversation_members.c.user_id).where(
                conversation_members.c.conversation_id
                == conversation_id,
                conversation_members.c.user_id
                == user_id,
            )
        )

        if existing.scalar_one_or_none() is not None:
            return True

        await self.db.execute(
            insert(conversation_members).values(
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )

        await self.db.commit()

        return True

    async def get_members(
        self,
        conversation_id: int,
    ):
        result = await self.db.execute(
            select(User)
            .join(
                conversation_members,
                User.id == conversation_members.c.user_id,
            )
            .where(
                conversation_members.c.conversation_id
                == conversation_id
            )
        )

        return result.scalars().all()

    async def remove_member(
        self,
        conversation_id: int,
        user_id: int,
    ):
        await self.db.execute(
            delete(conversation_members).where(
                conversation_members.c.conversation_id
                == conversation_id,
                conversation_members.c.user_id
                == user_id,
            )
        )

        await self.db.commit()

        return True

    async def is_member(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:
        result = await self.db.execute(
            select(conversation_members.c.user_id).where(
                conversation_members.c.conversation_id
                == conversation_id,
                conversation_members.c.user_id
                == user_id,
            )
        )

        return (
            result.scalar_one_or_none()
            is not None
        )