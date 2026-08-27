from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MessageBase(BaseModel):
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class MessageCreate(MessageBase):
    conversation_id: int


class MessageUpdate(BaseModel):
    content: Optional[str] = None


class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int

    # Message status
    is_delivered: bool = False
    is_read: bool = False

    # Edit / delete status
    is_edited: bool = False
    edited_at: Optional[datetime] = None

    is_deleted: bool = False

    created_at: datetime