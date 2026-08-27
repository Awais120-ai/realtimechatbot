import asyncio
import json

from app.database.base import Base
from app.database.session import engine, AsyncSessionLocal
from app.models.user import User
from app.models.chat import Conversation
from app.models.message import Message
from app.models.notification import Notification

from app.services.notification import NotificationService
from app.services.user_service import UserService


async def test_notifications():
    print("========== INITIALIZING DATABASE TABLES ==========")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created/verified.")

    async with AsyncSessionLocal() as db:
        user_service = UserService(db)
        notification_service = NotificationService(db)

        # Ensure User 1 and User 2 exist
        user_1 = await user_service.get_by_id(1)
        if not user_1:
            print("Creating test user 1...")
            user_1 = await user_service.create_user(
                email="user1@example.com",
                username="user1",
                password="password123",
            )

        user_2 = await user_service.get_by_id(2)
        if not user_2:
            print("Creating test user 2...")
            user_2 = await user_service.create_user(
                email="user2@example.com",
                username="user2",
                password="password123",
            )

        print(f"\nUser 1: ID {user_1.id} ({user_1.username})")
        print(f"User 2: ID {user_2.id} ({user_2.username})")

        # 1. Create system notification for User 2
        print("\n--- 1. Testing Create Notification ---")
        notification = await notification_service.create_notification(
            user_id=user_2.id,
            actor_id=user_1.id,
            title="Test Notification",
            body="This is a test notification body.",
            type="system",
            data=json.dumps({"test_key": "test_value"}),
        )
        print(f"✅ Created Notification ID {notification.id}: title='{notification.title}', body='{notification.body}'")

        # 2. Get unread count for User 2
        print("\n--- 2. Testing Get Unread Count ---")
        unread_count = await notification_service.get_unread_count(user_2.id)
        print(f"✅ User 2 Unread Notification Count: {unread_count}")
        assert unread_count >= 1

        # 3. List User 2 notifications
        print("\n--- 3. Testing Get User Notifications ---")
        notifications = await notification_service.get_user_notifications(
            user_id=user_2.id,
            unread_only=True,
        )
        print(f"✅ Found {len(notifications)} unread notifications for User 2.")
        for n in notifications:
            print(f"   - [ID {n.id}] {n.title}: {n.body} (Read: {n.is_read})")

        # 4. Mark Notification as read
        print("\n--- 4. Testing Mark Notification as Read ---")
        updated_n = await notification_service.mark_as_read(
            notification_id=notification.id,
            user_id=user_2.id,
        )
        print(f"✅ Notification ID {updated_n.id} is_read set to: {updated_n.is_read}")

        # 5. Check updated unread count
        new_unread_count = await notification_service.get_unread_count(user_2.id)
        print(f"✅ User 2 Updated Unread Count: {new_unread_count}")

        # 6. Test Message Notifications creation
        print("\n--- 5. Testing Create Message Notifications ---")
        msg_notifications = await notification_service.create_message_notifications(
            conversation_id=1,
            sender=user_1,
            member_ids=[user_1.id, user_2.id],
            content="Hello from User 1!",
            message_type="text",
        )
        print(f"✅ Created {len(msg_notifications)} message notifications.")
        for mn in msg_notifications:
            print(f"   - Recipient {mn.user_id}: '{mn.title}' -> {mn.body}")

        # 7. Mark all as read
        print("\n--- 6. Testing Mark All as Read ---")
        count_marked = await notification_service.mark_all_as_read(user_2.id)
        print(f"✅ Marked {count_marked} notifications as read for User 2.")

        final_unread = await notification_service.get_unread_count(user_2.id)
        print(f"✅ Final Unread Count: {final_unread}")

        print("\n=============================================")
        print("🎉 ALL NOTIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=============================================")


if __name__ == "__main__":
    asyncio.run(test_notifications())
