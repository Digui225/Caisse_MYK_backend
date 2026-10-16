"""Impression : print_job_id sur cash_sessions (ticket Z imprimé une seule fois, à la clôture)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('cash_sessions', sa.Column('print_job_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_cash_sessions_print_job_id_print_jobs'),
        'cash_sessions', 'print_jobs', ['print_job_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_cash_sessions_print_job_id_print_jobs'), 'cash_sessions', type_='foreignkey'
    )
    op.drop_column('cash_sessions', 'print_job_id')
