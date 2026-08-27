from app.websocket.typing import typing_manager
from app.websocket.manager import connection_manager

async def handle_websocket_message(data: dict, sender_user_id: str):
    """
    Handles incoming WS JSON messages and routes them.
    Accepts event payload key aliases: 'type' or 'event', 'conversationId' or 'conversation_id'.
    """
    event_type = data.get("type") or data.get("event")
    conversation_id = data.get("conversationId") or data.get("conversation_id")

    if not event_type or not conversation_id:
        return

    conversation_id = str(conversation_id)
    sender_user_id = str(sender_user_id)

    # 1. Typing Start
    if event_type in ["typing", "typing_start", "USER_TYPING"]:
        typing_manager.start_typing(conversation_id, sender_user_id)
        await connection_manager.broadcast_to_conversation(
            conversation_id=conversation_id,
            message={
                "type": "user_typing",
                "conversationId": conversation_id,
                "userId": sender_user_id,
                "conversation_id": conversation_id,
                "user_id": sender_user_id,
            },
            exclude_user_id=sender_user_id,
        )

    # 2. Typing Stop
    elif event_type in ["stop_typing", "typing_stop", "USER_STOPPED_TYPING"]:
        typing_manager.stop_typing(conversation_id, sender_user_id)
        await connection_manager.broadcast_to_conversation(
            conversation_id=conversation_id,
            message={
                "type": "user_stopped_typing",
                "conversationId": conversation_id,
                "userId": sender_user_id,
                "conversation_id": conversation_id,
                "user_id": sender_user_id,
            },
            exclude_user_id=sender_user_id,
        )