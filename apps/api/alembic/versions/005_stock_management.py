"""stock_management

Revision ID: 005_stock_management
Revises: 004_payments_and_printing
Create Date: 2026-09-28 21:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_stock_management"
down_revision: Union[str, None] = "004_payments_and_printing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table stock_items
    op.create_table(
        "stock_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), unique=True, nullable=False),
        sa.Column("quantity", sa.Float(), server_default="0", nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="bouteille", nullable=False),
        sa.Column("alert_threshold", sa.Float(), server_default="5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Table stock_movements
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("stock_item_id", sa.String(length=36), sa.ForeignKey("stock_items.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("quantity_after", sa.Float(), nullable=False),
        sa.Column("unit_cost_xof", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_stock_movements_created_at", table_name="stock_movements")
    op.drop_index("ix_stock_movements_product_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("stock_items")
