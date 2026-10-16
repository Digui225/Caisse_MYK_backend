"""FNE : solde prépayé (`balance_funds`) et alerte DGI au lieu du stock de stickers

La DGI renvoie désormais `balance_funds` (XOF) et plus `balance_sticker` : l'ancienne colonne
est toujours restée vide avec l'API réelle, ses valeurs ne sont pas reprises.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06 12:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('fne_documents', 'sticker_balance')
    op.add_column('fne_documents', sa.Column('balance_funds_xof', sa.Integer(), nullable=True))
    op.add_column(
        'fne_documents',
        sa.Column(
            'low_balance_warning', sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.execute("DELETE FROM settings WHERE key = 'fne.sticker_alert_threshold'")


def downgrade() -> None:
    op.drop_column('fne_documents', 'low_balance_warning')
    op.drop_column('fne_documents', 'balance_funds_xof')
    op.add_column('fne_documents', sa.Column('sticker_balance', sa.Integer(), nullable=True))
