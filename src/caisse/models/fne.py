import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import FneDocumentType, FneStatus
from caisse.models.base import Base, Timestamps, UUIDPk, enum_column


class FneDocument(UUIDPk, Timestamps, Base):
    __tablename__ = "fne_documents"
    __table_args__ = (
        Index(
            "ix_fne_documents_retry", "next_retry_at", postgresql_where=text("status = 'QUEUED'")
        ),
    )

    type: Mapped[FneDocumentType] = mapped_column(enum_column(FneDocumentType, "fne_document_type"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    cash_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="RESTRICT")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT")
    )
    status: Mapped[FneStatus] = mapped_column(
        enum_column(FneStatus, "fne_status"), default=FneStatus.PENDING, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)  # snapshot figé
    external_number: Mapped[str | None] = mapped_column(String(64))
    qr_payload: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
