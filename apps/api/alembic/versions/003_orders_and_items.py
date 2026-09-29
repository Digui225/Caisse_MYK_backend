"""orders_and_items

Revision ID: 003_orders_and_items
Revises: 002_catalog_and_tables
Create Date: 2026-09-28 17:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_orders_and_items"
down_revision: Union[str, None] = "002_catalog_and_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_number", sa.String(length=50), nullable=False, unique=True),
        sa.Column("cash_session_id", sa.String(length=36), sa.ForeignKey("cash_sessions.id"), nullable=False),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("restaurant_tables.id"), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("opened_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("closed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("guests_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("total_ttc_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_ht_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_vat_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paid_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancelled_reason", sa.String(length=255), nullable=True),
        sa.Column("cancelled_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Partial index on table_id for active orders
    op.create_index(
        "uq_single_active_order_per_table",
        "orders",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'PARTIALLY_PAID')"),
    )

    # 2. Table order_items
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("product_name_snapshot", sa.String(length=150), nullable=False),
        sa.Column("category_snapshot", sa.String(length=100), nullable=False),
        sa.Column("unit_price_xof", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=4, scale=2), server_default="18.00", nullable=False),
        sa.Column("line_total_xof", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("added_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("removal_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_index("uq_single_active_order_per_table", table_name="orders")
    op.drop_table("orders")
