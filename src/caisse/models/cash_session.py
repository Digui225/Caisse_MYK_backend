import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import CashMovementType, CashSessionStatus
from caisse.models.base import Base, CreatedAt, Timestamps, UUIDPk, enum_column


class CashRegister(UUIDPk, Timestamps, Base):
    __tablename__ = "cash_registers"

    name: Mapped[str] = mapped_column(String(60), unique=True)
    printer_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)


class CashSession(UUIDPk, Timestamps, Base):
    __tablename__ = "cash_sessions"
    __table_args__ = (
        # une seule session non clôturée par caisse
        Index(
            "uq_cash_sessions_one_active_per_register",
            "cash_register_id",
            unique=True,
            postgresql_where=text("status <> 'CLOSED'"),
        ),
        Index(
            "uq_cash_sessions_z_number",
            "cash_register_id",
            "z_number",
            unique=True,
            postgresql_where=text("z_number IS NOT NULL"),
        ),
        CheckConstraint("opening_float_xof >= 0", name="opening_float_positive"),
    )

    cash_register_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_registers.id", ondelete="RESTRICT")
    )
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    business_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[CashSessionStatus] = mapped_column(
        enum_column(CashSessionStatus, "cash_session_status"), default=CashSessionStatus.OPEN
    )
    opening_float_xof: Mapped[int]
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    z_number: Mapped[int | None]
    counted_cash_xof: Mapped[int | None]
    expected_cash_xof: Mapped[int | None]
    variance_xof: Mapped[int | None]
    closing_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    totals_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(String(500))


class CashMovement(UUIDPk, CreatedAt, Base):
    __tablename__ = "cash_movements"
    __table_args__ = (CheckConstraint("amount_xof > 0", name="amount_positive"),)

    cash_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[CashMovementType] = mapped_column(
        enum_column(CashMovementType, "cash_movement_type")
    )
    amount_xof: Mapped[int]
    reason: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
