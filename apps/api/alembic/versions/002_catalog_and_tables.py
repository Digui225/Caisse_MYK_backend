"""catalog_and_tables

Revision ID: 002_catalog_and_tables
Revises: 001_initial_auth_and_sessions
Create Date: 2026-09-28 16:58:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_catalog_and_tables"
down_revision: Union[str, None] = "001_initial_auth_and_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table categories
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=20), server_default="FOOD", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("fiscal_group", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Table products
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("category_id", sa.String(length=36), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("short_name", sa.String(length=20), nullable=False),
        sa.Column("price_xof", sa.Integer(), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=4, scale=2), server_default="18.00", nullable=False),
        sa.Column("track_stock", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_custom", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("sku", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Table product_price_history
    op.create_table(
        "product_price_history",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("old_price_xof", sa.Integer(), nullable=False),
        sa.Column("new_price_xof", sa.Integer(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. Table restaurant_tables
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("label", sa.String(length=50), nullable=False, unique=True),
        sa.Column("zone", sa.String(length=50), server_default="Salle", nullable=False),
        sa.Column("seats", sa.Integer(), server_default="4", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("restaurant_tables")
    op.drop_table("product_price_history")
    op.drop_table("products")
    op.drop_table("categories")
