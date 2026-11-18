"""Create initial orders and payment records.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("customer_telegram_id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_orders_amount_positive"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_orders_customer_telegram_id", "orders", ["customer_telegram_id"])
    op.create_index("ix_orders_customer_created", "orders", ["customer_telegram_id", "created_at"])

    op.create_table(
        "payment_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("transaction_reference", sa.String(length=500), nullable=False),
        sa.Column("submitted_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("verification_source", sa.String(length=20), nullable=True),
        sa.Column("verified_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("receiver_name", sa.String(length=160), nullable=True),
        sa.Column("receiver_account", sa.String(length=100), nullable=True),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("submitted_amount > 0", name="ck_payment_submitted_amount_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("provider", "transaction_reference", name="uq_payment_provider_reference"),
    )
    op.create_index("ix_payment_records_order_id", "payment_records", ["order_id"])
    op.create_index("ix_payment_status_created", "payment_records", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payment_status_created", table_name="payment_records")
    op.drop_index("ix_payment_records_order_id", table_name="payment_records")
    op.drop_table("payment_records")
    op.drop_index("ix_orders_customer_created", table_name="orders")
    op.drop_index("ix_orders_customer_telegram_id", table_name="orders")
    op.drop_table("orders")
