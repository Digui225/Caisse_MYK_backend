import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import StockArticleCategory, StockMovementType, StockOutMode
from caisse.models.base import Base, CreatedAt, Timestamps, UUIDPk, enum_column


class StockArticle(UUIDPk, Timestamps, Base):
    """Article de stock (ingrédient, boisson, emballage…), distinct du produit vendu.
    `quantity` et `avg_cost_xof` ne changent que par un mouvement (`stock_movements`)."""

    __tablename__ = "stock_articles"
    __table_args__ = (CheckConstraint("avg_cost_xof >= 0", name="avg_cost_positive"),)

    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[StockArticleCategory] = mapped_column(
        enum_column(StockArticleCategory, "stock_article_category")
    )
    unit: Mapped[str] = mapped_column(String(16))
    out_mode: Mapped[StockOutMode] = mapped_column(enum_column(StockOutMode, "stock_out_mode"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    avg_cost_xof: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))  # CMP
    alert_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    is_active: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str | None] = mapped_column(String(255))


class ProductComponent(UUIDPk, Base):
    """Ligne de fiche technique : un plat vendu consomme `quantity` de l'article."""

    __tablename__ = "product_components"
    __table_args__ = (
        UniqueConstraint("product_id", "article_id", name="uq_product_components_product_article"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_articles.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))


class StockMovement(UUIDPk, CreatedAt, Base):
    """Journal du stock, jamais modifié : la quantité d'un article est la somme de ses
    mouvements. `unit_cost_xof` valorise le mouvement (prix payé à l'achat, CMP sinon)."""

    __tablename__ = "stock_movements"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_articles.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[StockMovementType] = mapped_column(
        enum_column(StockMovementType, "stock_movement_type")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # signée
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_cost_xof: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    business_date: Mapped[date] = mapped_column(Date, index=True)
    reference_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    reference_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    supplier: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(255))
    # NULL : import en ligne de commande (pas d'utilisateur connecté)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
