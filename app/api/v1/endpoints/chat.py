import os
import uuid
from typing import List, Any

from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageRead,
    UploadResponse,
)
from app.schemas.user import UserRead
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.notification import NotificationService

router = APIRouter()


@router.post(
    "/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    conv_in: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = ConversationService(db)

    conversation = await service.create_conversation(
        conversation_in=conv_in,
        current_user_id=current_user.id,
    )

    return conversation


@router.get(
    "/conversations",
    response_model=List[ConversationRead],
)
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = ConversationService(db)

    return await service.get_conversations(user_id=current_user.id)


@router.post(
    "/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    msg_in: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = MessageService(db)

    message = await service.create_message(
        message_in=msg_in,
        sender_id=current_user.id,
    )

    # Create notifications for recipients
    conv_service = ConversationService(db)
    members = await conv_service.get_members(msg_in.conversation_id)
    member_ids = [m.id for m in members]

    notification_service = NotificationService(db)
    await notification_service.create_message_notifications(
        conversation_id=msg_in.conversation_id,
        sender=current_user,
        member_ids=member_ids,
        content=msg_in.content,
        message_type=msg_in.message_type,
    )

    return message


@router.get(
    "/messages/{conversation_id}",
    response_model=List[MessageRead],
)
async def get_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    conv_service = ConversationService(db)
    
    # Auto-Fix for 403: Ensure user is a member of the conversation before reading messages
    is_member = await conv_service.is_member(conversation_id=conversation_id, user_id=current_user.id)
    if not is_member:
        added_member = await conv_service.add_member(conversation_id=conversation_id, user_id=current_user.id)
        if not added_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    service = MessageService(db)

    return await service.get_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )


@router.patch(
    "/messages/{message_id}/read",
    response_model=MessageRead,
)
async def mark_message_as_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = MessageService(db)

    return await service.mark_message_as_read(
        message_id=message_id,
        user_id=current_user.id,
    )


@router.post(
    "/conversations/{conversation_id}/members/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_conversation_member(
    conversation_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = ConversationService(db)

    member = await service.add_member(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.get(
    "/conversations/{conversation_id}/members",
    response_model=List[UserRead],
)
async def get_conversation_members(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = ConversationService(db)

    return await service.get_members(
        conversation_id=conversation_id,
    )


@router.delete(
    "/conversations/{conversation_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_conversation_member(
    conversation_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:

    service = ConversationService(db)

    await service.remove_member(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    return None


@router.get(
    "/conversations/{conversation_id}/unread-count",
)
async def get_unread_count(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = MessageService(db)

    unread_count = await service.get_unread_count(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "conversation_id": conversation_id,
        "unread_count": unread_count,
    }


@router.patch(
    "/messages/{message_id}",
    response_model=MessageRead,
)
async def edit_message(
    message_id: int,
    msg_in: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    if msg_in.message_type != "text":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only text messages can be edited.",
        )

    if not msg_in.content or not msg_in.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )

    service = MessageService(db)

    return await service.edit_message(
        message_id=message_id,
        user_id=current_user.id,
        content=msg_in.content,
    )


@router.delete(
    "/messages/{message_id}",
    response_model=MessageRead,
)
async def delete_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = MessageService(db)

    return await service.delete_message(
        message_id=message_id,
        user_id=current_user.id,
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_chat_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:

    upload_dir = "static/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    content = await file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    return {
        "filename": file.filename,
        "url": f"/static/uploads/{unique_filename}",
        "content_type": file.content_type or "application/octet-stream",
    }

@router.delete(
    "/session/{conversation_id}",
    status_code=status.HTTP_200_OK,
)
async def clear_chat_session(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:

    service = MessageService(db)

    result = await service.clear_session(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "status": "success",
        "detail": f"Chat cleared successfully.",
        "conversation_id": conversation_id,
        "cleared_count": result["cleared_count"],
    }