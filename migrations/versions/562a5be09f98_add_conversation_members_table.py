"""add conversation members table

Revision ID: 562a5be09f98
Revises: f73beb9252a3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "562a5be09f98"
down_revision: Union[str, None] = "f73beb9252a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_members",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id",
            "user_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("conversation_members")