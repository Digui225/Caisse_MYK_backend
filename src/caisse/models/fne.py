import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, false, text
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
        # une seule FNE de vente par commande : pas de double certification (PLAN-FNE D6)
        Index(
            "uq_fne_documents_one_sale_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("type = 'FNE'"),
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
    # B2C / B2B / B2G / B2F
    template: Mapped[str | None] = mapped_column(String(8))
    # avoir → FNE d'origine
    parent_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fne_documents.id", ondelete="RESTRICT"), index=True
    )
    # identifiant FNE de la facture (`invoice.id`), requis pour un avoir
    fne_invoice_id: Mapped[str | None] = mapped_column(String(64))
    # [{"order_item_id", "fne_item_id", "quantity"}] : lignes certifiées, pour les avoirs
    items_map: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    fne_amount_ttc_xof: Mapped[int | None]
    sticker_balance: Mapped[int | None]
    # issue inconnue (délai dépassé, 500…) : jamais de renvoi automatique (PLAN-FNE D5)
    is_uncertain: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
