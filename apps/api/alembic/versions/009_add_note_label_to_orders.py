"""add_note_label_to_orders

Revision ID: 009_add_note_label_to_orders
Revises: 008_align_fne_documents_schema
Create Date: 2026-10-15 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "009_add_note_label_to_orders"
down_revision: Union[str, None] = "008_align_fne_documents_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    order_cols = [c["name"] for c in insp.get_columns("orders")]
    if "note_label" not in order_cols:
        op.add_column("orders", sa.Column("note_label", sa.String(50), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    order_cols = [c["name"] for c in insp.get_columns("orders")]
    if "note_label" in order_cols:
        op.drop_column("orders", "note_label")
