import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caisse.models.base import Base, CreatedAt


class AppSetting(Base):
    """Paramètres métier modifiables par l'admin (mentions du ticket, TVA, arrondi…)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SequenceCounter(Base):
    """Compteurs verrouillés par `SELECT ... FOR UPDATE` (n° de Z par caisse, n° de commande
    par journée…). Clé libre, ex. `z:<register_id>` ou `order:2026-09-24`."""

    __tablename__ = "sequence_counters"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


class IdempotencyRecord(CreatedAt, Base):
    """03-CONTRAT-API §3 : clé + hachage du corps + réponse d'origine, rejouée à l'identique."""

    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int]
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB)
