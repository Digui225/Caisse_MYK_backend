"""fne_dgi_real_api

Revision ID: 007_fne_dgi_real_api
Revises: 006_fne_and_customers
Create Date: 2026-10-02 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007_fne_dgi_real_api"
down_revision: Union[str, None] = "006_fne_and_customers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table settings (AppSetting key-value pour FNE, TVA, etc.)
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Enrichir customers avec tax_regime
    op.add_column("customers", sa.Column("tax_regime", sa.String(length=50), nullable=True))

    # 3. Enrichir fne_documents avec les champs requis par l'API DGI réelle
    op.add_column("fne_documents", sa.Column("type", sa.String(length=20), server_default="FNE", nullable=False))
    op.add_column("fne_documents", sa.Column("template", sa.String(length=8), nullable=True))
    op.add_column("fne_documents", sa.Column("cash_session_id", sa.String(length=36), sa.ForeignKey("cash_sessions.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("fne_documents", sa.Column("parent_document_id", sa.String(length=36), sa.ForeignKey("fne_documents.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("fne_documents", sa.Column("fne_invoice_id", sa.String(length=64), nullable=True))
    op.add_column("fne_documents", sa.Column("items_map", sa.JSON(), nullable=True))
    op.add_column("fne_documents", sa.Column("fne_amount_ttc_xof", sa.Integer(), nullable=True))
    op.add_column("fne_documents", sa.Column("sticker_balance", sa.Integer(), nullable=True))
    op.add_column("fne_documents", sa.Column("is_uncertain", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("fne_documents", sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("fne_documents", sa.Column("external_number", sa.String(length=64), nullable=True))
    op.add_column("fne_documents", sa.Column("qr_payload", sa.Text(), nullable=True))
    op.add_column("fne_documents", sa.Column("raw_response", sa.JSON(), nullable=True))
    op.add_column("fne_documents", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("fne_documents", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("fne_documents", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_fne_documents_external_number", "fne_documents", ["external_number"])
    op.create_index("ix_fne_documents_parent_document_id", "fne_documents", ["parent_document_id"])


def downgrade() -> None:
    op.drop_index("ix_fne_documents_parent_document_id", table_name="fne_documents")
    op.drop_index("ix_fne_documents_external_number", table_name="fne_documents")

    op.drop_column("fne_documents", "next_retry_at")
    op.drop_column("fne_documents", "last_error")
    op.drop_column("fne_documents", "attempts")
    op.drop_column("fne_documents", "raw_response")
    op.drop_column("fne_documents", "qr_payload")
    op.drop_column("fne_documents", "external_number")
    op.drop_column("fne_documents", "created_by_user_id")
    op.drop_column("fne_documents", "is_uncertain")
    op.drop_column("fne_documents", "sticker_balance")
    op.drop_column("fne_documents", "fne_amount_ttc_xof")
    op.drop_column("fne_documents", "items_map")
    op.drop_column("fne_documents", "fne_invoice_id")
    op.drop_column("fne_documents", "parent_document_id")
    op.drop_column("fne_documents", "cash_session_id")
    op.drop_column("fne_documents", "template")
    op.drop_column("fne_documents", "type")

    op.drop_column("customers", "tax_regime")
    op.drop_table("settings")
