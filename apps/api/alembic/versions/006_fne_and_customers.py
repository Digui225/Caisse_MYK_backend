"""fne_and_customers

Revision ID: 006_fne_and_customers
Revises: 005_stock_management
Create Date: 2026-09-28 21:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006_fne_and_customers"
down_revision: Union[str, None] = "005_stock_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table customers
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("ncc", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_ncc", "customers", ["ncc"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    # 2. Table fne_documents
    op.create_table(
        "fne_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), unique=True, nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("document_type", sa.String(length=20), server_default="FNE", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="QUEUED", nullable=False),
        sa.Column("invoice_number", sa.String(length=100), unique=True, nullable=True),
        sa.Column("qr_url", sa.String(length=500), nullable=True),
        sa.Column("fne_token", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fne_documents_order_id", "fne_documents", ["order_id"])
    op.create_index("ix_fne_documents_customer_id", "fne_documents", ["customer_id"])
    op.create_index("ix_fne_documents_status", "fne_documents", ["status"])
    op.create_index("ix_fne_documents_invoice_number", "fne_documents", ["invoice_number"])

    # 3. Table outbox_events
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_next_retry_at", "outbox_events", ["next_retry_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("fne_documents")
    op.drop_table("customers")
