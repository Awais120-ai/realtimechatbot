from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserRead


class MessageCreate(BaseModel):
    conversation_id: int
    content: Optional[str] = None

    message_type: str = "text"

    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class MessageRead(BaseModel):
    id: int
    conversation_id: int
    sender_id: int

    content: Optional[str] = None

    message_type: str

    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

    is_read: bool
    is_edited: bool
    edited_at: Optional[datetime] = None
    is_deleted: bool

    created_at: datetime

    sender: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    is_group: bool = False
    participant_id: Optional[int] = None

class ConversationRead(BaseModel):
    id: int
    title: Optional[str] = None
    is_group: bool
    created_at: datetime

    # For direct chats this is the OTHER participant
    # from the perspective of the currently logged-in user.
    other_user: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class UploadResponse(BaseModel):
    filename: str
    url: str
    content_type: str