from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserRead


class NotificationBase(BaseModel):
    title: str
    body: str
    type: str = "system"
    data: Optional[str] = None


class NotificationCreate(NotificationBase):
    user_id: int
    actor_id: Optional[int] = None


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class NotificationRead(NotificationBase):
    id: int
    user_id: int
    actor_id: Optional[int] = None
    is_read: bool
    created_at: datetime
    actor: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class UnreadNotificationCount(BaseModel):
    unread_count: int
