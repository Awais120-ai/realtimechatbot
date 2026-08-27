from sqlalchemy import text

from app.database.session import AsyncSessionLocal


async def mark_message_delivered(
    message_id: int,
    recipient_id: int,
) -> tuple[bool, int | None, int | None]:
    """
    Mark a message as delivered when it has successfully
    reached an active recipient WebSocket connection.

    Returns:
        (
            was_updated,
            sender_id,
            conversation_id,
        )
    """

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            text(
                """
                SELECT
                    id,
                    sender_id,
                    conversation_id,
                    is_delivered
                FROM messages
                WHERE id = :message_id
                """
            ),
            {
                "message_id": message_id,
            },
        )

        row = result.fetchone()

        if row is None:
            return False, None, None

        message_id_db = row[0]
        sender_id = row[1]
        conversation_id = row[2]
        is_delivered = bool(row[3])

        # Message is already delivered.
        if is_delivered:
            return (
                False,
                sender_id,
                conversation_id,
            )

        # Sender cannot be the recipient.
        if sender_id == recipient_id:
            return (
                False,
                sender_id,
                conversation_id,
            )

        # Verify recipient belongs to the conversation.
        member_result = await db.execute(
            text(
                """
                SELECT 1
                FROM conversation_members
                WHERE conversation_id = :conversation_id
                AND user_id = :user_id
                """
            ),
            {
                "conversation_id": conversation_id,
                "user_id": recipient_id,
            },
        )

        if member_result.fetchone() is None:
            return (
                False,
                sender_id,
                conversation_id,
            )

        await db.execute(
            text(
                """
                UPDATE messages
                SET is_delivered = TRUE
                WHERE id = :message_id
                """
            ),
            {
                "message_id": message_id_db,
            },
        )

        await db.commit()

        return (
            True,
            sender_id,
            conversation_id,
        )