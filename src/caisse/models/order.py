import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import OrderStatus
from caisse.models.base import Base, Timestamps, UUIDPk, enum_column


class Order(UUIDPk, Timestamps, Base):
    __tablename__ = "orders"
    __table_args__ = (
        # une seule commande active par table
        Index(
            "uq_orders_one_active_per_table",
            "table_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN','PARTIALLY_PAID')"),
        ),
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        CheckConstraint("paid_xof >= 0", name="paid_positive"),
        CheckConstraint("total_ttc_xof >= 0", name="total_positive"),
    )

    order_number: Mapped[str] = mapped_column(String(32))  # 2026-09-24-0042
    business_date: Mapped[date] = mapped_column(Date, index=True)
    counter_number: Mapped[int | None]  # « Comptoir n° 7 » pour la vente à emporter
    cash_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="RESTRICT"), index=True
    )
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurant_tables.id", ondelete="RESTRICT")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT")
    )
    status: Mapped[OrderStatus] = mapped_column(
        enum_column(OrderStatus, "order_status"), default=OrderStatus.OPEN, index=True
    )
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    guests_count: Mapped[int | None]
    total_ttc_xof: Mapped[int] = mapped_column(default=0)
    total_ht_xof: Mapped[int] = mapped_column(default=0)
    total_vat_xof: Mapped[int] = mapped_column(default=0)
    paid_xof: Mapped[int] = mapped_column(default=0)
    due_xof: Mapped[int] = mapped_column(default=0)
    cancelled_reason: Mapped[str | None] = mapped_column(String(255))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(UUIDPk, Base):
    """Ligne figée à l'ajout. Jamais de DELETE : un retrait est tracé (removed_*)."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_xof >= 0", name="unit_price_positive"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    product_name_snapshot: Mapped[str] = mapped_column(String(120))
    category_snapshot: Mapped[str] = mapped_column(String(60))
    fiscal_group_snapshot: Mapped[str] = mapped_column(String(40))
    unit_price_xof: Mapped[int]
    quantity: Mapped[int]
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    line_total_xof: Mapped[int]
    note: Mapped[str | None] = mapped_column(String(255))
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    removal_reason: Mapped[str | None] = mapped_column(String(255))
