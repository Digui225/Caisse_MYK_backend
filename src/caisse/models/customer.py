from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from caisse.models.base import Base, Timestamps, UUIDPk


class Customer(UUIDPk, Timestamps, Base):
    """Client entreprise (destinataire d'une FNE nominative)."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("uq_customers_ncc", "ncc", unique=True, postgresql_where=text("ncc IS NOT NULL")),
    )

    company_name: Mapped[str] = mapped_column(String(160))
    ncc: Mapped[str | None] = mapped_column(String(32))  # n° compte contribuable, ex. 9506466A
    tax_regime: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(160))
