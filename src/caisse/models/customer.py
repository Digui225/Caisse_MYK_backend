from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from caisse.models.base import Base, Timestamps, UUIDPk


class Customer(UUIDPk, Timestamps, Base):
    """Client entreprise (destinataire d'une FNE nominative)."""

    __tablename__ = "customers"

    company_name: Mapped[str] = mapped_column(String(160))
    ncc: Mapped[str | None] = mapped_column(String(32), index=True)  # n° compte contribuable
    tax_regime: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(160))
