import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import StockMovementType
from caisse.models.base import Base, CreatedAt, UUIDPk, enum_column


class StockItem(UUIDPk, Base):
    __tablename__ = "stock_items"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), unique=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    unit: Mapped[str] = mapped_column(String(16), default="unité")
    alert_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockMovement(UUIDPk, CreatedAt, Base):
    __tablename__ = "stock_movements"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[StockMovementType] = mapped_column(
        enum_column(StockMovementType, "stock_movement_type")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # signée
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_cost_xof: Mapped[int | None]
    reference_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT")
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
