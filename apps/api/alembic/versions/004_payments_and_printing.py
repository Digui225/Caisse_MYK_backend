"""payments_and_printing

Revision ID: 004_payments_and_printing
Revises: 003_orders_and_items
Create Date: 2026-09-28 21:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004_payments_and_printing"
down_revision: Union[str, None] = "003_orders_and_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table payments
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("cash_session_id", sa.String(length=36), sa.ForeignKey("cash_sessions.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("amount_xof", sa.Integer(), nullable=False),
        sa.Column("tendered_xof", sa.Integer(), nullable=True),
        sa.Column("change_xof", sa.Integer(), server_default="0", nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="CAPTURED", nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Index sur idempotency_key et order_id
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_cash_session_id", "payments", ["cash_session_id"])

    # 2. Table print_jobs
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("job_type", sa.String(length=30), server_default="RECEIPT", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="QUEUED", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("open_drawer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cut", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_print_jobs_status", "print_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_print_jobs_status", table_name="print_jobs")
    op.drop_table("print_jobs")
    op.drop_index("ix_payments_cash_session_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")
