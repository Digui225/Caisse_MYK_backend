from datetime import datetime, timezone
from sqlalchemy import Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from caisse.database import Base
from caisse.models.base import TimestampMixin, generate_uuid


class StockItem(Base, TimestampMixin):
    __tablename__ = "stock_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), unique=True, nullable=False)

    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="bouteille", nullable=False)
    alert_threshold: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    # Relationships
    product = relationship("Product")
    movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="stock_item", cascade="all, delete-orphan")


class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    stock_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_items.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_after: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost_xof: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)

    # Relationships
    stock_item = relationship("StockItem", back_populates="movements")
    product = relationship("Product")
    user = relationship("User")
    order = relationship("Order")
