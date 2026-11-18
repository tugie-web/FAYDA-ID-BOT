"""Add persistent Telegram free-access whitelist.

Revision ID: 0002_free_access
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_free_access"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "free_access_users" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "free_access_users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("telegram_user_id", sa.Integer(), nullable=False),
            sa.Column("granted_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("telegram_user_id > 0", name="ck_free_access_user_id_positive"),
            sa.UniqueConstraint("telegram_user_id"),
        )
    indexes = {item["name"] for item in inspect(op.get_bind()).get_indexes("free_access_users")}
    if "ix_free_access_users_telegram_user_id" not in indexes:
        op.create_index("ix_free_access_users_telegram_user_id", "free_access_users", ["telegram_user_id"])


def downgrade() -> None:
    op.drop_index("ix_free_access_users_telegram_user_id", table_name="free_access_users")
    op.drop_table("free_access_users")
