"""FNE par API : avoirs, identifiants FNE, résultat incertain, unicité NCC

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01 16:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES_OLD = "('FNE', 'RNE', 'DAILY_SUMMARY')"
_TYPES_NEW = "('FNE', 'REFUND', 'RNE', 'DAILY_SUMMARY')"


def upgrade() -> None:
    op.drop_constraint(op.f('ck_fne_documents_fne_document_type'), 'fne_documents', type_='check')
    op.create_check_constraint(
        op.f('ck_fne_documents_fne_document_type'), 'fne_documents', f"type IN {_TYPES_NEW}"
    )
    op.add_column('fne_documents', sa.Column('template', sa.String(length=8), nullable=True))
    op.add_column('fne_documents', sa.Column('parent_document_id', sa.Uuid(), nullable=True))
    op.add_column('fne_documents', sa.Column('fne_invoice_id', sa.String(length=64), nullable=True))
    op.add_column(
        'fne_documents',
        sa.Column('items_map', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column('fne_documents', sa.Column('fne_amount_ttc_xof', sa.Integer(), nullable=True))
    op.add_column('fne_documents', sa.Column('sticker_balance', sa.Integer(), nullable=True))
    op.add_column(
        'fne_documents',
        sa.Column('is_uncertain', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column('fne_documents', sa.Column('created_by_user_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_fne_documents_parent_document_id_fne_documents'),
        'fne_documents', 'fne_documents', ['parent_document_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        op.f('fk_fne_documents_created_by_user_id_users'),
        'fne_documents', 'users', ['created_by_user_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index(
        op.f('ix_fne_documents_parent_document_id'), 'fne_documents', ['parent_document_id']
    )
    op.create_index(
        'uq_fne_documents_one_sale_per_order', 'fne_documents', ['order_id'], unique=True,
        postgresql_where=sa.text("type = 'FNE'"),
    )

    op.drop_index('ix_customers_ncc', table_name='customers')
    op.create_index(
        'uq_customers_ncc', 'customers', ['ncc'], unique=True,
        postgresql_where=sa.text('ncc IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_customers_ncc', table_name='customers')
    op.create_index('ix_customers_ncc', 'customers', ['ncc'], unique=False)

    op.drop_index('uq_fne_documents_one_sale_per_order', table_name='fne_documents')
    op.drop_index(op.f('ix_fne_documents_parent_document_id'), table_name='fne_documents')
    op.drop_constraint(
        op.f('fk_fne_documents_created_by_user_id_users'), 'fne_documents', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('fk_fne_documents_parent_document_id_fne_documents'), 'fne_documents',
        type_='foreignkey',
    )
    for column in (
        'created_by_user_id', 'is_uncertain', 'sticker_balance', 'fne_amount_ttc_xof',
        'items_map', 'fne_invoice_id', 'parent_document_id', 'template',
    ):
        op.drop_column('fne_documents', column)
    op.execute("DELETE FROM fne_documents WHERE type = 'REFUND'")
    op.drop_constraint(op.f('ck_fne_documents_fne_document_type'), 'fne_documents', type_='check')
    op.create_check_constraint(
        op.f('ck_fne_documents_fne_document_type'), 'fne_documents', f"type IN {_TYPES_OLD}"
    )
