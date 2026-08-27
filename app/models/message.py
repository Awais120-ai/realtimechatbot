from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_class import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    sender_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
    )

    file_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =========================================================
    # DELIVERY / READ STATUS
    # =========================================================

    # False = message has not been delivered to recipient
    # True  = message has reached recipient's active connection
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # False = recipient has not opened/read the message
    # True  = recipient has read the message
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =========================================================
    # EDIT MESSAGE
    # =========================================================

    is_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =========================================================
    # DELETE MESSAGE
    # =========================================================

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =========================================================
    # CREATED AT
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

    sender = relationship(
        "User",
        back_populates="messages",
    )