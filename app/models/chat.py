from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Integer, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_class import Base


conversation_members = Table(
    "conversation_members",
    Base.metadata,
    Column(
        "conversation_id",
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_group: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    members = relationship(
        "User",
        secondary=conversation_members,
        back_populates="conversations",
    )