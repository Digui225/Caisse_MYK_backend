import uuid
from decimal import Decimal

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from caisse.models.catalog import Category, Product
from caisse.models.stock import StockItem


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return list(db.scalars(stmt))


def list_products(
    db: Session, *, category_id: uuid.UUID | None, search: str | None, is_active: bool | None
) -> list[Row[tuple[Product, Decimal | None]]]:
    """Produits + quantité en stock en une requête. Les produits personnalisés sont exclus
    du menu (00-ARCHITECTURE §7.2)."""
    stmt = (
        select(Product, StockItem.quantity)
        .outerjoin(StockItem, StockItem.product_id == Product.id)
        .where(Product.is_custom.is_(False))
        .order_by(Product.sort_order, Product.name)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
    return list(db.execute(stmt).all())  # type: ignore[arg-type]  # outer join : quantité nullable
