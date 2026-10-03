"""align_fne_documents_schema

Revision ID: 008_align_fne_documents_schema
Revises: 007_fne_dgi_real_api
Create Date: 2026-10-03 17:08:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_align_fne_documents_schema"
down_revision: Union[str, None] = "007_fne_dgi_real_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    fne_cols = [c["name"] for c in insp.get_columns("fne_documents")]

    # 1. Rendre document_type et retry_count nullables avec valeurs par défaut
    # pour éviter les violations NOT NULL lors de l'insertion via le nouveau modèle ORM
    if "document_type" in fne_cols:
        op.alter_column(
            "fne_documents",
            "document_type",
            nullable=True,
            server_default="FNE",
        )

    if "retry_count" in fne_cols:
        op.alter_column(
            "fne_documents",
            "retry_count",
            nullable=True,
            server_default="0",
        )

    # 2. Remplacer l'index unique sur order_id par un index standard + index partiel (1 vente par commande)
    existing_indexes = {idx["name"]: idx for idx in insp.get_indexes("fne_documents")}

    if "ix_fne_documents_order_id" in existing_indexes and existing_indexes["ix_fne_documents_order_id"].get("unique"):
        op.drop_index("ix_fne_documents_order_id", table_name="fne_documents")
        op.create_index("ix_fne_documents_order_id", "fne_documents", ["order_id"], unique=False)

    if "uq_fne_documents_one_sale_per_order" not in existing_indexes:
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_fne_documents_one_sale_per_order "
                "ON fne_documents (order_id) WHERE type = 'FNE';"
            )
        elif bind.dialect.name == "sqlite":
            op.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_fne_documents_one_sale_per_order "
                "ON fne_documents (order_id) WHERE type = 'FNE';"
            )


def downgrade() -> None:
    pass
