
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_class import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    avatar_url: Mapped[str | None] = mapped_column(
    String(500),
    nullable=True,
)

    profile_picture: Mapped[str | None] = mapped_column(
    String(500),
    nullable=True,
)

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    is_online: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "Message",
        back_populates="sender",
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        secondary="conversation_members",
        back_populates="members",
    )

    notifications = relationship(
        "Notification",
        foreign_keys="Notification.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )


