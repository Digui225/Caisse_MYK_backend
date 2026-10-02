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
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()

    # 1. Table settings (AppSetting key-value pour FNE, TVA, etc.)
    if "settings" not in tables:
        op.create_table(
            "settings",
            sa.Column("key", sa.String(length=64), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 2. Enrichir customers avec tax_regime
    customer_cols = [c["name"] for c in insp.get_columns("customers")]
    if "tax_regime" not in customer_cols:
        op.add_column("customers", sa.Column("tax_regime", sa.String(length=50), nullable=True))

    # 3. Enrichir fne_documents avec les champs requis par l'API DGI réelle
    fne_cols = [c["name"] for c in insp.get_columns("fne_documents")]
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    cols_to_add = [
        ("type", sa.String(length=20), "FNE", False),
        ("template", sa.String(length=8), None, True),
        ("cash_session_id", sa.String(length=36), None, True),
        ("parent_document_id", sa.String(length=36), None, True),
        ("fne_invoice_id", sa.String(length=64), None, True),
        ("items_map", sa.JSON(), None, True),
        ("fne_amount_ttc_xof", sa.Integer(), None, True),
        ("sticker_balance", sa.Integer(), None, True),
        ("is_uncertain", sa.Boolean(), False, False),
        ("created_by_user_id", sa.String(length=36), None, True),
        ("external_number", sa.String(length=64), None, True),
        ("qr_payload", sa.Text(), None, True),
        ("raw_response", sa.JSON(), None, True),
        ("attempts", sa.Integer(), 0, False),
        ("last_error", sa.Text(), None, True),
        ("next_retry_at", sa.DateTime(timezone=True), None, True),
    ]

    for col_name, col_type, default, nullable in cols_to_add:
        if col_name not in fne_cols:
            if default is not None:
                op.add_column(
                    "fne_documents",
                    sa.Column(col_name, col_type, server_default=str(default).lower() if isinstance(default, bool) else str(default), nullable=nullable)
                )
            else:
                op.add_column(
                    "fne_documents",
                    sa.Column(col_name, col_type, nullable=nullable)
                )

    existing_indexes = [idx["name"] for idx in insp.get_indexes("fne_documents")]
    if "ix_fne_documents_external_number" not in existing_indexes:
        op.create_index("ix_fne_documents_external_number", "fne_documents", ["external_number"])
    if "ix_fne_documents_parent_document_id" not in existing_indexes:
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
