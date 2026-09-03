import json
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.schemas.chat import MessageCreate
from app.services.message_service import MessageService
from app.services.notification import NotificationService
from app.services.websocket_service import manager
from app.services.delivery_service import mark_message_delivered
from app.websocket.typing import typing_manager


router = APIRouter()


# =============================================================
# ONLINE / OFFLINE PRESENCE
# =============================================================

# Keeps track of how many active WebSocket connections
# each user currently has.
#
# Example:
#
# user 1 -> 2 connections
# user 2 -> 1 connection
#
# This prevents a user from becoming offline when only one
# of their multiple tabs/devices disconnects.
#
# Note:
# This is process-local. It works correctly for the current
# single-process / single-worker WebSocket setup.
active_connection_counts: dict[int, int] = {}


def increment_connection_count(user_id: int) -> bool:
    """
    Increase user's active WebSocket connection count.

    Returns:
        True  -> user has just become online
        False -> user was already online
    """

    current_count = active_connection_counts.get(user_id, 0)

    active_connection_counts[user_id] = current_count + 1

    return current_count == 0


def decrement_connection_count(user_id: int) -> bool:
    """
    Decrease user's active WebSocket connection count.

    Returns:
        True  -> user has completely gone offline
        False -> user still has another active connection
    """

    current_count = active_connection_counts.get(user_id, 0)

    if current_count <= 1:
        active_connection_counts.pop(user_id, None)
        return True

    active_connection_counts[user_id] = current_count - 1

    return False


def is_user_online(user_id: int) -> bool:
    """
    Check whether a user currently has at least one
    active WebSocket connection.
    """

    return active_connection_counts.get(user_id, 0) > 0


async def get_user_conversation_members(user_id: int) -> list[int]:
    """
    Get all users who share at least one conversation
    with the specified user.
    """

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            text(
                """
                SELECT DISTINCT cm2.user_id
                FROM conversation_members cm1
                JOIN conversation_members cm2
                    ON cm1.conversation_id = cm2.conversation_id
                WHERE cm1.user_id = :user_id
                AND cm2.user_id != :user_id
                """
            ),
            {
                "user_id": user_id,
            },
        )

        return [
            int(row[0])
            for row in result.fetchall()
        ]


async def broadcast_presence(
    user_id: int,
    event_type: str,
):
    """
    Broadcast online/offline status to users who share
    conversations with the current user.
    """

    member_ids = await get_user_conversation_members(user_id)

    timestamp = datetime.now(timezone.utc).isoformat()

    is_online = event_type == "user_online"

    for member_id in member_ids:

        await manager.send_to_user(
            user_id=member_id,
            message={
                "type": event_type,
                "user_id": user_id,
                "userId": user_id,
                "is_online": is_online,
                "isOnline": is_online,
                "last_seen": None if is_online else timestamp,
            },
        )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    # =========================================================
    # GET JWT TOKEN
    # =========================================================

    token = websocket.query_params.get("token")

    print("========== WEBSOCKET DEBUG ==========")
    print("Token received:", bool(token))
    print("Token length:", len(token) if token else 0)
    print("=====================================")

    if not token:
        await websocket.close(code=1008)
        return

    # =========================================================
    # VALIDATE JWT TOKEN
    # =========================================================

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        print("JWT PAYLOAD:", payload)
        print("USER ID:", payload.get("sub"))
        print("TOKEN TYPE:", payload.get("type"))

        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None or token_type != "access":
            await websocket.close(code=1008)
            return

        user_id = int(user_id)

    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        print("========== WEBSOCKET JWT ERROR ==========")
        print("ERROR:", repr(exc))
        print("========================================")

        await websocket.close(code=1008)
        return

    # =========================================================
    # CHECK USER
    # =========================================================

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(User).where(User.id == user_id)
        )

        user = result.scalars().first()

        if user is None or not user.is_active:
            await websocket.close(code=1008)
            return

    # =========================================================
    # CONNECT USER
    # =========================================================

    await manager.connect(
        user_id=user_id,
        websocket=websocket,
    )

    # =========================================================
    # MARK USER ONLINE
    # =========================================================

    became_online = increment_connection_count(user_id)

    print(
        "USER ONLINE:",
        user_id,
        "connections:",
        active_connection_counts.get(user_id, 0),
    )

    # Only broadcast when the first connection is opened.
    if became_online:

        try:
            await broadcast_presence(
                user_id=user_id,
                event_type="user_online",
            )

        except Exception as exc:
            print(
                "ONLINE PRESENCE BROADCAST ERROR:",
                repr(exc),
            )

    try:

        while True:

            # =================================================
            # RECEIVE JSON
            # =================================================

            try:
                data = await websocket.receive_json()

            except (json.JSONDecodeError, ValueError, TypeError):

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid JSON payload.",
                    }
                )

                continue

            if not isinstance(data, dict):

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Payload must be a JSON object.",
                    }
                )

                continue

            event_type = data.get("type") or data.get("event")

            # =================================================
            # WEBRTC CALL SIGNALING
            # =================================================

            if event_type in (
                "call_invite",
                "call_accept",
                "call_reject",
                "call_end",
                "webrtc_offer",
                "webrtc_answer",
                "webrtc_ice_candidate",
            ):

                # -------------------------------------------------
                # Get target user
                # -------------------------------------------------

                target_user_id = (
                    data.get("target_user_id")
                    or data.get("targetUserId")
                    or data.get("to_user_id")
                    or data.get("toUserId")
                )

                if not target_user_id:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "target_user_id is required.",
                        }
                    )
                    continue

                # -------------------------------------------------
                # Validate target user ID
                # -------------------------------------------------

                try:
                    target_user_id = int(target_user_id)

                except (ValueError, TypeError):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "target_user_id must be an integer.",
                        }
                    )
                    continue

                # -------------------------------------------------
                # Prevent self calls
                # -------------------------------------------------

                if target_user_id == user_id:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "You cannot call yourself.",
                        }
                    )
                    continue

                # -------------------------------------------------
                # Get conversation ID
                # -------------------------------------------------

                conversation_id = (
                    data.get("conversation_id")
                    or data.get("conversationId")
                )

                if not conversation_id:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "conversation_id is required.",
                        }
                    )
                    continue

                # -------------------------------------------------
                # Validate conversation ID
                # -------------------------------------------------

                try:
                    conversation_id = int(conversation_id)

                except (ValueError, TypeError):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "conversation_id must be an integer."
                            ),
                        }
                    )
                    continue

                # -------------------------------------------------
                # Verify both users belong to conversation
                # -------------------------------------------------

                async with AsyncSessionLocal() as db:

                    current_user_result = await db.execute(
                        text(
                            """
                            SELECT 1
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            AND user_id = :user_id
                            LIMIT 1
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                            "user_id": user_id,
                        },
                    )

                    current_user_is_member = (
                        current_user_result.fetchone()
                        is not None
                    )

                    if not current_user_is_member:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )
                        continue

                    target_user_result = await db.execute(
                        text(
                            """
                            SELECT 1
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            AND user_id = :target_user_id
                            LIMIT 1
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                            "target_user_id": target_user_id,
                        },
                    )

                    target_user_is_member = (
                        target_user_result.fetchone()
                        is not None
                    )

                    if not target_user_is_member:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "Target user is not a member "
                                    "of this conversation."
                                ),
                            }
                        )
                        continue

                # -------------------------------------------------
                # Prepare signaling message
                # -------------------------------------------------

                signaling_message = dict(data)

                signaling_message["type"] = event_type

                signaling_message["from_user_id"] = user_id
                signaling_message["fromUserId"] = user_id

                signaling_message["conversation_id"] = (
                    conversation_id
                )
                signaling_message["conversationId"] = (
                    conversation_id
                )

                # -------------------------------------------------
                # CALL END
                # -------------------------------------------------

                if event_type == "call_end":

                    duration = data.get("duration", 0)
                    call_type = data.get(
                        "call_type",
                        "audio",
                    )

                    try:
                        duration = int(duration)
                    except (ValueError, TypeError):
                        duration = 0

                    if call_type not in (
                        "audio",
                        "video",
                    ):
                        call_type = "audio"

                    # ---------------------------------------------
                    # Save call history as a chat message
                    # ---------------------------------------------

                    call_content = json.dumps(
                        {
                            "call_type": call_type,
                            "duration": duration,
                        }
                    )

                    async with AsyncSessionLocal() as db:

                        service = MessageService(db)

                        message_in = MessageCreate(
                            conversation_id=conversation_id,
                            content=call_content,
                            message_type="call",
                            file_url=None,
                            file_name=None,
                            file_size=None,
                            mime_type=None,
                        )

                        try:

                            message = await service.create_message(
                                message_in=message_in,
                                sender_id=user_id,
                            )

                        except Exception as exc:

                            print(
                                "CALL MESSAGE CREATE ERROR:",
                                repr(exc),
                            )

                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": str(exc),
                                }
                            )

                            continue

                    # -----------------------------------------
                    # Get conversation members
                    # -----------------------------------------

                    result = await db.execute(
                        text(
                            """
                            SELECT user_id
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                        },
                    )

                    member_ids = [
                        row[0]
                        for row in result.fetchall()
                    ]

                    # ---------------------------------------------
                    # Prepare chat message
                    # ---------------------------------------------

                    message_data = {
                        "type": "message",
                        "id": message.id,
                        "conversation_id": message.conversation_id,
                        "sender_id": message.sender_id,
                        "content": message.content,
                        "message_type": message.message_type,
                        "file_url": None,
                        "file_name": None,
                        "file_size": None,
                        "mime_type": None,
                        "is_read": message.is_read,
                        "is_delivered": getattr(
                            message,
                            "is_delivered",
                            False,
                        ),
                        "is_edited": message.is_edited,
                        "edited_at": (
                            message.edited_at.isoformat()
                            if message.edited_at
                            else None
                        ),
                        "is_deleted": message.is_deleted,
                        "created_at": message.created_at.isoformat(),
                    }

                    print(
                        "CALL HISTORY MESSAGE:",
                        message_data,
                    )

                    # ---------------------------------------------
                    # Send call message to both users
                    # ---------------------------------------------

                    for member_id in member_ids:

                        await manager.send_to_user(
                            user_id=member_id,
                            message=message_data,
                        )

                    # ---------------------------------------------
                    # Also forward original call_end event
                    # ---------------------------------------------

                    await manager.send_to_user(
                        user_id=target_user_id,
                        message=signaling_message,
                    )

                    continue


                # -------------------------------------------------
                # Forward normal signaling event
                # -------------------------------------------------

                print(
                    "========== WEBRTC SIGNALING =========="
                )
                print("Event:", event_type)
                print("From:", user_id)
                print("To:", target_user_id)
                print("Conversation:", conversation_id)
                print("=======================================")

                await manager.send_to_user(
                    user_id=target_user_id,
                    message=signaling_message,
                )

                continue

            # =================================================
            # TYPING / STOP TYPING
            # =================================================

            if event_type in (
                "typing",
                "typing_start",
                "USER_TYPING",
                "stop_typing",
                "typing_stop",
                "USER_STOPPED_TYPING",
            ):

                conversation_id = (
                    data.get("conversation_id")
                    or data.get("conversationId")
                )

                if not conversation_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "conversation_id is required.",
                        }
                    )

                    continue

                try:
                    conversation_id = int(conversation_id)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "conversation_id must be an integer."
                            ),
                        }
                    )

                    continue

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
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
                            "user_id": user_id,
                        },
                    )

                    if result.fetchone() is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )

                        continue

                    result = await db.execute(
                        text(
                            """
                            SELECT user_id
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                        },
                    )

                    member_ids = [
                        row[0]
                        for row in result.fetchall()
                    ]

                if event_type in (
                    "typing",
                    "typing_start",
                    "USER_TYPING",
                ):

                    typing_manager.start_typing(
                        str(conversation_id),
                        str(user_id),
                    )

                    broadcast_event = "user_typing"

                else:

                    typing_manager.stop_typing(
                        str(conversation_id),
                        str(user_id),
                    )

                    broadcast_event = "user_stopped_typing"

                print(
                    event_type.upper(),
                    "EVENT:",
                    user_id,
                    "conversation:",
                    conversation_id,
                    "members:",
                    member_ids,
                )

                for member_id in member_ids:

                    if member_id == user_id:
                        continue

                    await manager.send_to_user(
                        user_id=member_id,
                        message={
                            "type": broadcast_event,
                            "conversation_id": conversation_id,
                            "conversationId": conversation_id,
                            "user_id": user_id,
                            "userId": user_id,
                        },
                    )

                continue

            # =================================================
            # CONVERSATION READ EVENT
            # =================================================

            if event_type == "conversation_read":

                conversation_id = (
                    data.get("conversation_id")
                    or data.get("conversationId")
                )

                if not conversation_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "conversation_id is required.",
                        }
                    )

                    continue

                try:
                    conversation_id = int(conversation_id)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "conversation_id must be an integer."
                            ),
                        }
                    )

                    continue

                unread_messages = []

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
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
                            "user_id": user_id,
                        },
                    )

                    if result.fetchone() is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )

                        continue

                    result = await db.execute(
                        text(
                            """
                            SELECT id, sender_id
                            FROM messages
                            WHERE conversation_id = :conversation_id
                            AND sender_id != :user_id
                            AND is_read = FALSE
                            ORDER BY id ASC
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                            "user_id": user_id,
                        },
                    )

                    unread_messages = result.fetchall()

                    if unread_messages:

                        await db.execute(
                            text(
                                """
                                UPDATE messages
                                SET is_read = TRUE
                                WHERE conversation_id = :conversation_id
                                AND sender_id != :user_id
                                AND is_read = FALSE
                                """
                            ),
                            {
                                "conversation_id": conversation_id,
                                "user_id": user_id,
                            },
                        )

                        await db.commit()

                message_ids = [
                    row[0]
                    for row in unread_messages
                ]

                sender_ids = {
                    row[1]
                    for row in unread_messages
                    if row[1] != user_id
                }

                for sender_id in sender_ids:

                    await manager.send_to_user(
                        user_id=sender_id,
                        message={
                            "type": "conversation_read",
                            "conversation_id": conversation_id,
                            "conversationId": conversation_id,
                            "user_id": user_id,
                            "userId": user_id,
                            "message_ids": message_ids,
                        },
                    )

                await websocket.send_json(
                    {
                        "type": "conversation_read",
                        "conversation_id": conversation_id,
                        "conversationId": conversation_id,
                        "user_id": user_id,
                        "userId": user_id,
                        "message_ids": message_ids,
                    }
                )

                continue

            # =================================================
            # MESSAGE READ EVENT
            # =================================================

            if event_type == "message_read":

                message_id = data.get("message_id")

                if not message_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "message_id is required.",
                        }
                    )

                    continue

                try:
                    message_id = int(message_id)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "message_id must be an integer."
                            ),
                        }
                    )

                    continue

                message_conversation_id = None
                message_sender_id = None
                message_was_unread = False

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
                        text(
                            """
                            SELECT
                                id,
                                conversation_id,
                                sender_id,
                                is_read
                            FROM messages
                            WHERE id = :message_id
                            """
                        ),
                        {
                            "message_id": message_id,
                        },
                    )

                    message_row = result.fetchone()

                    if message_row is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message not found.",
                            }
                        )

                        continue

                    message_conversation_id = message_row[1]
                    message_sender_id = message_row[2]
                    message_was_unread = not bool(message_row[3])

                    result = await db.execute(
                        text(
                            """
                            SELECT 1
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            AND user_id = :user_id
                            """
                        ),
                        {
                            "conversation_id": message_conversation_id,
                            "user_id": user_id,
                        },
                    )

                    if result.fetchone() is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )

                        continue

                    if message_sender_id == user_id:
                        continue

                    if message_was_unread:

                        await db.execute(
                            text(
                                """
                                UPDATE messages
                                SET is_read = TRUE
                                WHERE id = :message_id
                                """
                            ),
                            {
                                "message_id": message_id,
                            },
                        )

                        await db.commit()

                if message_was_unread:

                    print(
                        "MESSAGE READ:",
                        "message_id=",
                        message_id,
                        "reader=",
                        user_id,
                    )

                    await manager.send_to_user(
                        user_id=message_sender_id,
                        message={
                            "type": "message_read",
                            "message_id": message_id,
                            "conversation_id": message_conversation_id,
                            "user_id": user_id,
                        },
                    )

                continue

            # =================================================
            # GET NOTIFICATIONS EVENT
            # =================================================

            if event_type == "get_notifications":

                async with AsyncSessionLocal() as db:

                    notification_service = NotificationService(db)

                    notifications = (
                        await notification_service.get_user_notifications(
                            user_id=user_id,
                            skip=data.get("skip", 0),
                            limit=data.get("limit", 50),
                            unread_only=data.get(
                                "unread_only",
                                False,
                            ),
                        )
                    )

                    n_list = [
                        {
                            "id": n.id,
                            "user_id": n.user_id,
                            "actor_id": n.actor_id,
                            "title": n.title,
                            "body": n.body,
                            "type": n.type,
                            "data": n.data,
                            "is_read": n.is_read,
                            "created_at": n.created_at.isoformat(),
                        }
                        for n in notifications
                    ]

                    await websocket.send_json(
                        {
                            "type": "notifications_list",
                            "notifications": n_list,
                        }
                    )

                continue

            # =================================================
            # MARK NOTIFICATION READ EVENT
            # =================================================

            if event_type == "mark_notification_read":

                notification_id = data.get(
                    "notification_id"
                )

                if not notification_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "notification_id is required."
                            ),
                        }
                    )

                    continue

                try:
                    notification_id = int(
                        notification_id
                    )

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "notification_id "
                                "must be an integer."
                            ),
                        }
                    )

                    continue

                async with AsyncSessionLocal() as db:

                    notification_service = NotificationService(db)

                    notification = (
                        await notification_service.mark_as_read(
                            notification_id=notification_id,
                            user_id=user_id,
                        )
                    )

                    if not notification:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "Notification not found."
                                ),
                            }
                        )

                    else:

                        await websocket.send_json(
                            {
                                "type": "notification_marked_read",
                                "notification_id": notification_id,
                            }
                        )

                continue

            # =================================================
            # MESSAGE EDITED EVENT
            # =================================================

            if event_type == "message_edited":

                message_id = data.get("message_id")
                content = data.get("content")

                if not message_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "message_id is required.",
                        }
                    )

                    continue

                if content is None or not str(content).strip():

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "content is required.",
                        }
                    )

                    continue

                try:
                    message_id = int(message_id)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "message_id must be an integer."
                            ),
                        }
                    )

                    continue

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
                        text(
                            """
                            SELECT
                                id,
                                conversation_id,
                                sender_id,
                                is_deleted
                            FROM messages
                            WHERE id = :message_id
                            """
                        ),
                        {
                            "message_id": message_id,
                        },
                    )

                    message_row = result.fetchone()

                    if message_row is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message not found.",
                            }
                        )

                        continue

                    message_conversation_id = message_row[1]
                    message_sender_id = message_row[2]
                    message_is_deleted = message_row[3]

                    if message_is_deleted:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "Deleted messages "
                                    "cannot be edited."
                                ),
                            }
                        )

                        continue

                    if message_sender_id != user_id:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You can only edit "
                                    "your own messages."
                                ),
                            }
                        )

                        continue

                    result = await db.execute(
                        text(
                            """
                            SELECT 1
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            AND user_id = :user_id
                            """
                        ),
                        {
                            "conversation_id": message_conversation_id,
                            "user_id": user_id,
                        },
                    )

                    if result.fetchone() is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )

                        continue

                    service = MessageService(db)

                    try:

                        message = await service.edit_message(
                            message_id=message_id,
                            user_id=user_id,
                            content=str(content).strip(),
                        )

                    except Exception as exc:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": str(exc),
                            }
                        )

                        continue

                    if message is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message not found.",
                            }
                        )

                        continue

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
                        text(
                            """
                            SELECT user_id
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            """
                        ),
                        {
                            "conversation_id": (
                                message_conversation_id
                            ),
                        },
                    )

                    member_ids = [
                        row[0]
                        for row in result.fetchall()
                    ]

                event = {
                    "type": "message_edited",
                    "message_id": message.id,
                    "conversation_id": message.conversation_id,
                    "user_id": user_id,
                    "content": message.content,
                    "is_edited": message.is_edited,
                    "edited_at": (
                        message.edited_at.isoformat()
                        if message.edited_at
                        else None
                    ),
                }

                for member_id in member_ids:

                    await manager.send_to_user(
                        user_id=member_id,
                        message=event,
                    )

                continue

            # =================================================
            # MESSAGE DELETED EVENT
            # =================================================

            if event_type == "message_deleted":

                message_id = data.get("message_id")

                if not message_id:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "message_id is required.",
                        }
                    )

                    continue

                try:
                    message_id = int(message_id)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "message_id must be an integer."
                            ),
                        }
                    )

                    continue

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
                        text(
                            """
                            SELECT
                                id,
                                conversation_id,
                                sender_id,
                                is_deleted
                            FROM messages
                            WHERE id = :message_id
                            """
                        ),
                        {
                            "message_id": message_id,
                        },
                    )

                    message_row = result.fetchone()

                    if message_row is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message not found.",
                            }
                        )

                        continue

                    message_conversation_id = message_row[1]
                    message_sender_id = message_row[2]
                    message_is_deleted = message_row[3]

                    if message_is_deleted:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "Message is already deleted."
                                ),
                            }
                        )

                        continue

                    if message_sender_id != user_id:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You can only delete "
                                    "your own messages."
                                ),
                            }
                        )

                        continue

                    result = await db.execute(
                        text(
                            """
                            SELECT 1
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            AND user_id = :user_id
                            """
                        ),
                        {
                            "conversation_id": (
                                message_conversation_id
                            ),
                            "user_id": user_id,
                        },
                    )

                    if result.fetchone() is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": (
                                    "You are not a member "
                                    "of this conversation."
                                ),
                            }
                        )

                        continue

                    service = MessageService(db)

                    try:

                        message = await service.delete_message(
                            message_id=message_id,
                            user_id=user_id,
                        )

                    except Exception as exc:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": str(exc),
                            }
                        )

                        continue

                    if message is None:

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message not found.",
                            }
                        )

                        continue

                async with AsyncSessionLocal() as db:

                    result = await db.execute(
                        text(
                            """
                            SELECT user_id
                            FROM conversation_members
                            WHERE conversation_id = :conversation_id
                            """
                        ),
                        {
                            "conversation_id": (
                                message_conversation_id
                            ),
                        },
                    )

                    member_ids = [
                        row[0]
                        for row in result.fetchall()
                    ]

                event = {
                    "type": "message_deleted",
                    "message_id": message.id,
                    "conversation_id": message.conversation_id,
                    "user_id": user_id,
                    "is_deleted": True,
                }

                for member_id in member_ids:

                    await manager.send_to_user(
                        user_id=member_id,
                        message=event,
                    )

                continue

            # =================================================
            # NORMAL / ATTACHMENT CHAT MESSAGE
            # =================================================

            conversation_id = data.get(
                "conversation_id"
            )

            if not conversation_id:

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": (
                            "conversation_id is required."
                        ),
                    }
                )

                continue

            try:
                conversation_id = int(
                    conversation_id
                )

            except (ValueError, TypeError):

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": (
                            "conversation_id "
                            "must be an integer."
                        ),
                    }
                )

                continue

            # =================================================
            # MESSAGE FIELDS
            # =================================================

            content = data.get("content")

            message_type = data.get(
                "message_type",
                "text",
            )

            file_url = data.get("file_url")
            file_name = data.get("file_name")
            file_size = data.get("file_size")
            mime_type = data.get("mime_type")

            # =================================================
            # VALIDATE MESSAGE TYPE
            # =================================================

            allowed_message_types = {
                "text",
                "image",
                "file",
                "call",
            }

            if message_type not in allowed_message_types:

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": (
                            "message_type must be "
                            "text, image, file, or call."
                        ),
                    }
                )

                continue

            # =================================================
            # TEXT MESSAGE VALIDATION
            # =================================================

            if message_type == "text":

                if not content or not str(content).strip():

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "content is required "
                                "for text messages."
                            ),
                        }
                    )

                    continue

                file_url = None
                file_name = None
                file_size = None
                mime_type = None

            # =================================================
            # IMAGE / FILE VALIDATION
            # =================================================

            elif message_type in (
                "image",
                "file",
            ):

                if not file_url:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "file_url is required "
                                "for attachment messages."
                            ),
                        }
                    )

                    continue

                if not file_name:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "file_name is required "
                                "for attachment messages."
                            ),
                        }
                    )

                    continue

                if file_size is None:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "file_size is required "
                                "for attachment messages."
                            ),
                        }
                    )

                    continue

                if not mime_type:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "mime_type is required "
                                "for attachment messages."
                            ),
                        }
                    )

                    continue

                try:

                    file_size = int(file_size)

                except (ValueError, TypeError):

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "file_size must be "
                                "an integer."
                            ),
                        }
                    )

                    continue

                if file_size < 0:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "file_size cannot "
                                "be negative."
                            ),
                        }
                    )

                    continue


            # =================================================
            # CALL MESSAGE
            # =================================================

            elif message_type == "call":

                # Call history does not use attachments.
                file_url = None
                file_name = None
                file_size = None
                mime_type = None

                if not content:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "content is required "
                                "for call messages."
                            ),
                        }
                    )

                    continue

            # =================================================
            # CREATE MESSAGE
            # =================================================

            async with AsyncSessionLocal() as db:

                service = MessageService(db)

                message_in = MessageCreate(
                    conversation_id=conversation_id,
                    content=content,
                    message_type=message_type,
                    file_url=file_url,
                    file_name=file_name,
                    file_size=file_size,
                    mime_type=mime_type,
                )

                try:

                    message = await service.create_message(
                        message_in=message_in,
                        sender_id=user_id,
                    )

                except Exception as exc:

                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": str(exc),
                        }
                    )

                    continue

                result = await db.execute(
                    text(
                        """
                        SELECT user_id
                        FROM conversation_members
                        WHERE conversation_id = :conversation_id
                        """
                    ),
                    {
                        "conversation_id": conversation_id,
                    },
                )

                member_ids = [
                    row[0]
                    for row in result.fetchall()
                ]

                sender_res = await db.execute(
                    select(User).where(
                        User.id == user_id
                    )
                )

                sender = sender_res.scalars().first()

                if sender:

                    notification_service = (
                        NotificationService(db)
                    )

                    await notification_service.create_message_notifications(
                        conversation_id=conversation_id,
                        sender=sender,
                        member_ids=member_ids,
                        content=content,
                        message_type=message_type,
                    )

            # =================================================
            # PREPARE MESSAGE RESPONSE
            # =================================================

            # Safely expose delivery status if the model/schema
            # already contains is_delivered.
            is_delivered = getattr(
                message,
                "is_delivered",
                False,
            )

            message_data = {
                "type": "message",
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "message_type": message.message_type,
                "file_url": message.file_url,
                "file_name": message.file_name,
                "file_size": message.file_size,
                "mime_type": message.mime_type,
                "is_read": message.is_read,
                "is_delivered": is_delivered,
                "is_edited": message.is_edited,
                "edited_at": (
                    message.edited_at.isoformat()
                    if message.edited_at
                    else None
                ),
                "is_deleted": message.is_deleted,
                "created_at": message.created_at.isoformat(),
            }

            print(
                "MESSAGE EVENT:",
                message_data,
            )

            # =================================================
            # SEND MESSAGE TO ALL MEMBERS
            # =================================================

            for member_id in member_ids:

                try:

                    # -------------------------------------------------
                    # Send message to member
                    # -------------------------------------------------

                    await manager.send_to_user(
                        user_id=member_id,
                        message=message_data,
                    )

                    # -------------------------------------------------
                    # Sender does not need delivery confirmation
                    # for their own WebSocket connection.
                    # -------------------------------------------------

                    if member_id == user_id:
                        continue

                    # -------------------------------------------------
                    # If recipient currently has an active WebSocket,
                    # the message has reached the recipient.
                    # -------------------------------------------------

                    if is_user_online(member_id):

                        (
                            was_delivered,
                            message_sender_id,
                            message_conversation_id,
                        ) = await mark_message_delivered(
                            message_id=message.id,
                            recipient_id=member_id,
                        )

                        # -----------------------------------------
                        # Notify sender in real time.
                        # -----------------------------------------

                        # -------------------------------------------------

                        if (
                            was_delivered
                            and message_sender_id is not None
                        ):

                            await manager.send_to_user(
                                user_id=message_sender_id,
                                message={
                                    "type": "message_delivered",
                                    "message_id": message.id,
                                    "conversation_id": (
                            message_conversation_id
                        ),
                                    "user_id": member_id,
                                    "is_delivered": True,
                                },
                            )

                except Exception as exc:

                    print(
                        "MESSAGE SEND / DELIVERY ERROR:",
                        repr(exc),
                    )

    # =========================================================
    # WEBSOCKET DISCONNECTED
    # =========================================================

    except WebSocketDisconnect:

        became_offline = decrement_connection_count(
            user_id
        )

        await manager.disconnect(
            user_id=user_id,
            websocket=websocket,
        )

        print(
            "USER DISCONNECTED:",
            user_id,
            "remaining connections:",
            active_connection_counts.get(
                user_id,
                0,
            ),
        )

        # Only broadcast offline when the user has no
        # remaining active WebSocket connections.
        if became_offline:

            try:

                await broadcast_presence(
                    user_id=user_id,
                    event_type="user_offline",
                )

            except Exception as exc:

                print(
                    "OFFLINE PRESENCE BROADCAST ERROR:",
                    repr(exc),
                )

    except Exception as exc:

        print(
            "WEBSOCKET ERROR:",
            repr(exc),
        )

        became_offline = decrement_connection_count(
            user_id
        )

        await manager.disconnect(
            user_id=user_id,
            websocket=websocket,
        )

        if became_offline:

            try:

                await broadcast_presence(
                    user_id=user_id,
                    event_type="user_offline",
                )

            except Exception as presence_exc:

                print(
                    "OFFLINE PRESENCE BROADCAST ERROR:",
                    repr(presence_exc),
                )