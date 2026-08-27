import asyncio

# IMPORTANT:
# Load all SQLAlchemy models before using the ORM.
from app.models.user import User
from app.models.chat import Conversation
from app.models.message import Message

from app.database.session import AsyncSessionLocal
from app.services.message_service import MessageService


async def test():

    async with AsyncSessionLocal() as db:

        service = MessageService(db)

        user_1_count = await service.get_unread_count(
            conversation_id=1,
            user_id=1,
        )

        user_2_count = await service.get_unread_count(
            conversation_id=1,
            user_id=2,
        )

        print(
            f"User 1 unread messages: {user_1_count}"
        )

        print(
            f"User 2 unread messages: {user_2_count}"
        )


if __name__ == "__main__":
    asyncio.run(test())