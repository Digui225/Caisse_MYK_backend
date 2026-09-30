import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import PaymentMethod, PaymentStatus
from caisse.models.base import Base, CreatedAt, UUIDPk, enum_column


class Payment(UUIDPk, CreatedAt, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_xof > 0", name="amount_positive"),
        CheckConstraint("change_xof >= 0", name="change_positive"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    cash_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="RESTRICT"), index=True
    )
    method: Mapped[PaymentMethod] = mapped_column(enum_column(PaymentMethod, "payment_method"))
    provider: Mapped[str | None] = mapped_column(String(20))  # ORANGE / MTN / MOOV / WAVE
    amount_xof: Mapped[int]
    tendered_xof: Mapped[int | None]
    change_xof: Mapped[int] = mapped_column(default=0)
    reference: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"), default=PaymentStatus.CAPTURED
    )
    # l'idempotence est garantie par la base, pas par un `if` applicatif
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    void_reason: Mapped[str | None] = mapped_column(String(255))
