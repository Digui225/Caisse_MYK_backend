"""schema initial

Revision ID: 0001
Revises: 
Create Date: 2026-09-24 14:59:15.733471
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('cash_registers',
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('printer_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_registers')),
    sa.UniqueConstraint('name', name=op.f('uq_cash_registers_name'))
    )
    op.create_table('categories',
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('kind', sa.Enum('FOOD', 'DRINK', 'OTHER', name='category_kind', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('color', sa.String(length=16), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('fiscal_group', sa.String(length=40), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categories'))
    )
    op.create_table('customers',
    sa.Column('company_name', sa.String(length=160), nullable=False),
    sa.Column('ncc', sa.String(length=32), nullable=True),
    sa.Column('tax_regime', sa.String(length=40), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('email', sa.String(length=160), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customers'))
    )
    op.create_index(op.f('ix_customers_ncc'), 'customers', ['ncc'], unique=False)
    op.create_table('device_login_throttles',
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('failed_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('device_id', name=op.f('pk_device_login_throttles'))
    )
    op.create_table('outbox_events',
    sa.Column('aggregate_type', sa.String(length=40), nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'DONE', 'FAILED', name='outbox_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    op.create_index('ix_outbox_events_pending', 'outbox_events', ['available_at'], unique=False, postgresql_where=sa.text("status = 'PENDING'"))
    op.create_table('restaurant_tables',
    sa.Column('label', sa.String(length=20), nullable=False),
    sa.Column('zone', sa.String(length=40), nullable=False),
    sa.Column('seats', sa.Integer(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('seats > 0', name=op.f('ck_restaurant_tables_seats_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_restaurant_tables')),
    sa.UniqueConstraint('label', name=op.f('uq_restaurant_tables_label'))
    )
    op.create_table('sequence_counters',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_sequence_counters'))
    )
    op.create_table('users',
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('pin_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('CAISSIER', 'RESPONSABLE', 'ADMIN', name='user_role', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_table('audit_logs',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('acting_as_user_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity', sa.String(length=64), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('device_id', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['acting_as_user_id'], ['users.id'], name=op.f('fk_audit_logs_acting_as_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_logs_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_table('cash_sessions',
    sa.Column('cash_register_id', sa.Uuid(), nullable=False),
    sa.Column('opened_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('closed_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('business_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'CLOSING', 'CLOSED', name='cash_session_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('opening_float_xof', sa.Integer(), nullable=False),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('z_number', sa.Integer(), nullable=True),
    sa.Column('counted_cash_xof', sa.Integer(), nullable=True),
    sa.Column('expected_cash_xof', sa.Integer(), nullable=True),
    sa.Column('variance_xof', sa.Integer(), nullable=True),
    sa.Column('closing_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('totals_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('opening_float_xof >= 0', name=op.f('ck_cash_sessions_opening_float_positive')),
    sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id'], name=op.f('fk_cash_sessions_cash_register_id_cash_registers'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id'], name=op.f('fk_cash_sessions_closed_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['opened_by_user_id'], ['users.id'], name=op.f('fk_cash_sessions_opened_by_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_sessions'))
    )
    op.create_index(op.f('ix_cash_sessions_business_date'), 'cash_sessions', ['business_date'], unique=False)
    op.create_index('uq_cash_sessions_one_active_per_register', 'cash_sessions', ['cash_register_id'], unique=True, postgresql_where=sa.text("status <> 'CLOSED'"))
    op.create_index('uq_cash_sessions_z_number', 'cash_sessions', ['cash_register_id', 'z_number'], unique=True, postgresql_where=sa.text('z_number IS NOT NULL'))
    op.create_table('idempotency_records',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('method', sa.String(length=8), nullable=False),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('response_status', sa.Integer(), nullable=False),
    sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_idempotency_records_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_idempotency_records'))
    )
    op.create_table('override_grants',
    sa.Column('jti', sa.Uuid(), nullable=False),
    sa.Column('granted_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('requested_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], name=op.f('fk_override_grants_granted_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], name=op.f('fk_override_grants_requested_by_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('jti', name=op.f('pk_override_grants'))
    )
    op.create_table('products',
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('short_name', sa.String(length=20), nullable=False),
    sa.Column('price_xof', sa.Integer(), nullable=False),
    sa.Column('vat_rate', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('track_stock', sa.Boolean(), nullable=False),
    sa.Column('is_custom', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('color', sa.String(length=16), nullable=True),
    sa.Column('sku', sa.String(length=40), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('price_xof >= 0', name=op.f('ck_products_price_positive')),
    sa.CheckConstraint('vat_rate >= 0', name=op.f('ck_products_vat_rate_positive')),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_products_category_id_categories'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('sku', name=op.f('uq_products_sku'))
    )
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('jti', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('replaced_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_tokens_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('jti', name=op.f('pk_refresh_tokens'))
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_settings_updated_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_settings'))
    )
    op.create_table('cash_movements',
    sa.Column('cash_session_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.Enum('IN', 'OUT', name='cash_movement_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('amount_xof', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount_xof > 0', name=op.f('ck_cash_movements_amount_positive')),
    sa.ForeignKeyConstraint(['cash_session_id'], ['cash_sessions.id'], name=op.f('fk_cash_movements_cash_session_id_cash_sessions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_cash_movements_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_movements'))
    )
    op.create_index(op.f('ix_cash_movements_cash_session_id'), 'cash_movements', ['cash_session_id'], unique=False)
    op.create_table('orders',
    sa.Column('order_number', sa.String(length=32), nullable=False),
    sa.Column('business_date', sa.Date(), nullable=False),
    sa.Column('counter_number', sa.Integer(), nullable=True),
    sa.Column('cash_session_id', sa.Uuid(), nullable=False),
    sa.Column('table_id', sa.Uuid(), nullable=True),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'PARTIALLY_PAID', 'PAID', 'CANCELLED', 'REFUNDED', name='order_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('opened_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('closed_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('guests_count', sa.Integer(), nullable=True),
    sa.Column('total_ttc_xof', sa.Integer(), nullable=False),
    sa.Column('total_ht_xof', sa.Integer(), nullable=False),
    sa.Column('total_vat_xof', sa.Integer(), nullable=False),
    sa.Column('paid_xof', sa.Integer(), nullable=False),
    sa.Column('due_xof', sa.Integer(), nullable=False),
    sa.Column('cancelled_reason', sa.String(length=255), nullable=True),
    sa.Column('cancelled_by', sa.Uuid(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('paid_xof >= 0', name=op.f('ck_orders_paid_positive')),
    sa.CheckConstraint('total_ttc_xof >= 0', name=op.f('ck_orders_total_positive')),
    sa.ForeignKeyConstraint(['cancelled_by'], ['users.id'], name=op.f('fk_orders_cancelled_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['cash_session_id'], ['cash_sessions.id'], name=op.f('fk_orders_cash_session_id_cash_sessions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id'], name=op.f('fk_orders_closed_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_orders_customer_id_customers'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['opened_by_user_id'], ['users.id'], name=op.f('fk_orders_opened_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['table_id'], ['restaurant_tables.id'], name=op.f('fk_orders_table_id_restaurant_tables'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
    sa.UniqueConstraint('order_number', name='uq_orders_order_number')
    )
    op.create_index(op.f('ix_orders_business_date'), 'orders', ['business_date'], unique=False)
    op.create_index(op.f('ix_orders_cash_session_id'), 'orders', ['cash_session_id'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index('uq_orders_one_active_per_table', 'orders', ['table_id'], unique=True, postgresql_where=sa.text("status IN ('OPEN','PARTIALLY_PAID')"))
    op.create_table('product_price_history',
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('old_price_xof', sa.Integer(), nullable=False),
    sa.Column('new_price_xof', sa.Integer(), nullable=False),
    sa.Column('changed_by', sa.Uuid(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name=op.f('fk_product_price_history_changed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_price_history_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_price_history'))
    )
    op.create_index(op.f('ix_product_price_history_product_id'), 'product_price_history', ['product_id'], unique=False)
    op.create_table('stock_items',
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('alert_threshold', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_stock_items_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_items')),
    sa.UniqueConstraint('product_id', name=op.f('uq_stock_items_product_id'))
    )
    op.create_table('fne_documents',
    sa.Column('type', sa.Enum('FNE', 'RNE', 'DAILY_SUMMARY', name='fne_document_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('cash_session_id', sa.Uuid(), nullable=True),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'PENDING', 'QUEUED', 'SUBMITTING', 'CERTIFIED', 'FAILED', 'MANUAL', name='fne_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('external_number', sa.String(length=64), nullable=True),
    sa.Column('qr_payload', sa.Text(), nullable=True),
    sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('certified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cash_session_id'], ['cash_sessions.id'], name=op.f('fk_fne_documents_cash_session_id_cash_sessions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_fne_documents_customer_id_customers'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_fne_documents_order_id_orders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fne_documents'))
    )
    op.create_index(op.f('ix_fne_documents_order_id'), 'fne_documents', ['order_id'], unique=False)
    op.create_index('ix_fne_documents_retry', 'fne_documents', ['next_retry_at'], unique=False, postgresql_where=sa.text("status = 'QUEUED'"))
    op.create_index(op.f('ix_fne_documents_status'), 'fne_documents', ['status'], unique=False)
    op.create_table('order_items',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('product_name_snapshot', sa.String(length=120), nullable=False),
    sa.Column('category_snapshot', sa.String(length=60), nullable=False),
    sa.Column('fiscal_group_snapshot', sa.String(length=40), nullable=False),
    sa.Column('unit_price_xof', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('vat_rate', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('line_total_xof', sa.Integer(), nullable=False),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('added_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removed_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('removal_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_order_items_quantity_positive')),
    sa.CheckConstraint('unit_price_xof >= 0', name=op.f('ck_order_items_unit_price_positive')),
    sa.ForeignKeyConstraint(['added_by_user_id'], ['users.id'], name=op.f('fk_order_items_added_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_items_order_id_orders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_order_items_product_id_products'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['removed_by_user_id'], ['users.id'], name=op.f('fk_order_items_removed_by_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items'))
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_table('payments',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('cash_session_id', sa.Uuid(), nullable=False),
    sa.Column('method', sa.Enum('CASH', 'MOBILE_MONEY', 'CARD', 'BANK_TRANSFER', 'CREDIT', 'OTHER', name='payment_method', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=True),
    sa.Column('amount_xof', sa.Integer(), nullable=False),
    sa.Column('tendered_xof', sa.Integer(), nullable=True),
    sa.Column('change_xof', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=64), nullable=True),
    sa.Column('status', sa.Enum('CAPTURED', 'VOIDED', name='payment_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('idempotency_key', sa.String(length=64), nullable=False),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('voided_by', sa.Uuid(), nullable=True),
    sa.Column('void_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount_xof > 0', name=op.f('ck_payments_amount_positive')),
    sa.CheckConstraint('change_xof >= 0', name=op.f('ck_payments_change_positive')),
    sa.ForeignKeyConstraint(['cash_session_id'], ['cash_sessions.id'], name=op.f('fk_payments_cash_session_id_cash_sessions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_payments_created_by_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_payments_order_id_orders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['voided_by'], ['users.id'], name=op.f('fk_payments_voided_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_payments_idempotency_key'))
    )
    op.create_index(op.f('ix_payments_cash_session_id'), 'payments', ['cash_session_id'], unique=False)
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_table('print_jobs',
    sa.Column('type', sa.Enum('RECEIPT', 'X_REPORT', 'Z_REPORT', 'FNE', 'ORDER_TICKET', name='print_job_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('session_id', sa.Uuid(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rendered', sa.Text(), nullable=True),
    sa.Column('open_drawer', sa.Boolean(), nullable=False),
    sa.Column('status', sa.Enum('QUEUED', 'PRINTING', 'DONE', 'FAILED', name='print_job_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('is_reprint', sa.Boolean(), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_print_jobs_order_id_orders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name=op.f('fk_print_jobs_requested_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['session_id'], ['cash_sessions.id'], name=op.f('fk_print_jobs_session_id_cash_sessions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_print_jobs'))
    )
    op.create_index(op.f('ix_print_jobs_order_id'), 'print_jobs', ['order_id'], unique=False)
    op.create_index(op.f('ix_print_jobs_status'), 'print_jobs', ['status'], unique=False)
    op.create_table('stock_movements',
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.Enum('PURCHASE_IN', 'SALE_OUT', 'RETURN_IN', 'LOSS_OUT', 'ADJUSTMENT', 'INVENTORY_COUNT', name='stock_movement_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('quantity_after', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('unit_cost_xof', sa.Integer(), nullable=True),
    sa.Column('reference_order_id', sa.Uuid(), nullable=True),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_stock_movements_product_id_products'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reference_order_id'], ['orders.id'], name=op.f('fk_stock_movements_reference_order_id_orders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_stock_movements_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_movements'))
    )
    op.create_index(op.f('ix_stock_movements_product_id'), 'stock_movements', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_movements_product_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_print_jobs_status'), table_name='print_jobs')
    op.drop_index(op.f('ix_print_jobs_order_id'), table_name='print_jobs')
    op.drop_table('print_jobs')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_cash_session_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_fne_documents_status'), table_name='fne_documents')
    op.drop_index('ix_fne_documents_retry', table_name='fne_documents', postgresql_where=sa.text("status = 'QUEUED'"))
    op.drop_index(op.f('ix_fne_documents_order_id'), table_name='fne_documents')
    op.drop_table('fne_documents')
    op.drop_table('stock_items')
    op.drop_index(op.f('ix_product_price_history_product_id'), table_name='product_price_history')
    op.drop_table('product_price_history')
    op.drop_index('uq_orders_one_active_per_table', table_name='orders', postgresql_where=sa.text("status IN ('OPEN','PARTIALLY_PAID')"))
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_cash_session_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_business_date'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_cash_movements_cash_session_id'), table_name='cash_movements')
    op.drop_table('cash_movements')
    op.drop_table('settings')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.drop_table('products')
    op.drop_table('override_grants')
    op.drop_table('idempotency_records')
    op.drop_index('uq_cash_sessions_z_number', table_name='cash_sessions', postgresql_where=sa.text('z_number IS NOT NULL'))
    op.drop_index('uq_cash_sessions_one_active_per_register', table_name='cash_sessions', postgresql_where=sa.text("status <> 'CLOSED'"))
    op.drop_index(op.f('ix_cash_sessions_business_date'), table_name='cash_sessions')
    op.drop_table('cash_sessions')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('sequence_counters')
    op.drop_table('restaurant_tables')
    op.drop_index('ix_outbox_events_pending', table_name='outbox_events', postgresql_where=sa.text("status = 'PENDING'"))
    op.drop_table('outbox_events')
    op.drop_table('device_login_throttles')
    op.drop_index(op.f('ix_customers_ncc'), table_name='customers')
    op.drop_table('customers')
    op.drop_table('categories')
    op.drop_table('cash_registers')
