import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import CategoryKind
from caisse.models.base import Base, Timestamps, UUIDPk, enum_column


class Category(UUIDPk, Timestamps, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[CategoryKind] = mapped_column(enum_column(CategoryKind, "category_kind"))
    sort_order: Mapped[int] = mapped_column(default=0)
    color: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(default=True)
    # regroupement du récapitulatif FNE : POISSONS, VIANDES, JUS, EAU, PLATS, AUTRES…
    fiscal_group: Mapped[str] = mapped_column(String(40), default="AUTRES")


class Product(UUIDPk, Timestamps, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_xof >= 0", name="price_positive"),
        CheckConstraint("vat_rate >= 0", name="vat_rate_positive"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str] = mapped_column(String(20))  # libellé ticket
    price_xof: Mapped[int]
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("18.00"))
    track_stock: Mapped[bool] = mapped_column(default=False)
    is_custom: Mapped[bool] = mapped_column(default=False)  # produit créé à la volée
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    color: Mapped[str | None] = mapped_column(String(16))
    sku: Mapped[str | None] = mapped_column(String(40), unique=True)


class ProductPriceHistory(UUIDPk, Base):
    __tablename__ = "product_price_history"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    old_price_xof: Mapped[int]
    new_price_xof: Mapped[int]
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str] = mapped_column(String(255))
