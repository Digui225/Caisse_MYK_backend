"""initial_auth_and_sessions

Revision ID: 001_initial_auth_and_sessions
Revises: 
Create Date: 2026-09-28 15:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_auth_and_sessions"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table users
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="CAISSIER", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Table cash_registers
    op.create_table(
        "cash_registers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("printer_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Table cash_sessions
    op.create_table(
        "cash_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("cash_register_id", sa.String(length=36), sa.ForeignKey("cash_registers.id"), nullable=False),
        sa.Column("opened_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("closed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("opening_float_xof", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("z_number", sa.Integer(), nullable=True),
        sa.Column("expected_cash_xof", sa.Integer(), nullable=True),
        sa.Column("counted_cash_xof", sa.Integer(), nullable=True),
        sa.Column("variance_xof", sa.Integer(), nullable=True),
        sa.Column("closing_breakdown", sa.JSON(), nullable=True),
        sa.Column("totals_snapshot", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_cash_register_single_open_session",
        "cash_sessions",
        ["cash_register_id"],
        unique=True,
        postgresql_where=sa.text("status != 'CLOSED'"),
    )

    # 4. Table cash_movements
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("cash_session_id", sa.String(length=36), sa.ForeignKey("cash_sessions.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("amount_xof", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 5. Table audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acting_as_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.Column("ip", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. Table idempotency_records
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("request_path", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_logs")
    op.drop_table("cash_movements")
    op.drop_index("uq_cash_register_single_open_session", table_name="cash_sessions")
    op.drop_table("cash_sessions")
    op.drop_table("cash_registers")
    op.drop_table("users")
