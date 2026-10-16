"""Partage de table : plusieurs commandes actives par table, chacune avec son étiquette

L'index unique « une commande active par table » devient un index simple ; la création
d'une commande verrouille la table (SELECT … FOR UPDATE) pour décider qui partage.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16 18:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE = sa.text("status IN ('OPEN','PARTIALLY_PAID')")


def upgrade() -> None:
    op.add_column('orders', sa.Column('note_label', sa.String(length=50), nullable=True))
    op.drop_index('uq_orders_one_active_per_table', table_name='orders', postgresql_where=ACTIVE)
    op.create_index(
        'ix_orders_active_per_table', 'orders', ['table_id'], unique=False,
        postgresql_where=ACTIVE,
    )


def downgrade() -> None:
    # refusé s'il reste une table partagée : la contrainte unique ne pourrait pas être recréée
    shared = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM (SELECT table_id FROM orders WHERE status IN ('OPEN','PARTIALLY_PAID')"
        " AND table_id IS NOT NULL GROUP BY table_id HAVING count(*) > 1) t"
    )).scalar_one()
    if shared:
        raise RuntimeError(
            f'{shared} table(s) portent plusieurs commandes actives : les solder ou les annuler '
            'avant de revenir à une commande par table.'
        )
    op.drop_index('ix_orders_active_per_table', table_name='orders', postgresql_where=ACTIVE)
    op.create_index(
        'uq_orders_one_active_per_table', 'orders', ['table_id'], unique=True,
        postgresql_where=ACTIVE,
    )
    op.drop_column('orders', 'note_label')
