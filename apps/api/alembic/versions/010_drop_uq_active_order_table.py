"""drop_uq_single_active_order_per_table

Revision ID: 010_drop_uq_active_order_table
Revises: 009_add_note_label_to_orders
Create Date: 2026-10-15 11:23:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "010_drop_uq_active_order_table"
down_revision: Union[str, None] = "009_add_note_label_to_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes("orders")]
    if "uq_single_active_order_per_table" in indexes:
        op.drop_index("uq_single_active_order_per_table", table_name="orders")

    if "ix_orders_active_table" not in indexes:
        op.create_index(
            "ix_orders_active_table",
            "orders",
            ["table_id"],
            unique=False,
            postgresql_where=sa.text("status IN ('OPEN', 'PARTIALLY_PAID')"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes("orders")]
    if "ix_orders_active_table" in indexes:
        op.drop_index("ix_orders_active_table", table_name="orders")

    if "uq_single_active_order_per_table" not in indexes:
        op.create_index(
            "uq_single_active_order_per_table",
            "orders",
            ["table_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('OPEN', 'PARTIALLY_PAID')"),
        )
