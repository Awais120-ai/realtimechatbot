"""add message attachment fields

Revision ID: 5663cda66a56
Revises: 562a5be09f98
Create Date: 2026-08-12 10:43:40.094042

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5663cda66a56"
down_revision: Union[str, None] = "562a5be09f98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add message_type with a temporary server default.
    # Existing messages will automatically become "text".
    op.add_column(
        "messages",
        sa.Column(
            "message_type",
            sa.String(length=20),
            nullable=False,
            server_default="text",
        ),
    )

    # Remove the server default after existing rows
    # have been populated.
    op.alter_column(
        "messages",
        "message_type",
        server_default=None,
    )

    # Attachment fields
    op.add_column(
        "messages",
        sa.Column(
            "file_url",
            sa.String(length=500),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "file_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # Text content becomes optional because
    # file messages may not have text content.
    op.alter_column(
        "messages",
        "content",
        existing_type=sa.TEXT(),
        nullable=True,
    )


def downgrade() -> None:
    # Restore content requirement
    op.alter_column(
        "messages",
        "content",
        existing_type=sa.TEXT(),
        nullable=False,
    )

    # Remove attachment fields
    op.drop_column("messages", "mime_type")
    op.drop_column("messages", "file_size")
    op.drop_column("messages", "file_name")
    op.drop_column("messages", "file_url")

    # Remove message type
    op.drop_column("messages", "message_type")