import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.domain import stock_rules
from caisse.models.catalog import Category, Product
from caisse.repositories import stock as stock_repo


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return list(db.scalars(stmt))


def list_products(
    db: Session, *, category_id: uuid.UUID | None, search: str | None, is_active: bool | None
) -> list[tuple[Product, Decimal | None]]:
    """Produits + portions encore vendables d'après leur fiche technique (`None` : pas de
    fiche). Les produits personnalisés sont exclus du menu (00-ARCHITECTURE §7.2)."""
    stmt = (
        select(Product)
        .where(Product.is_custom.is_(False))
        .order_by(Product.sort_order, Product.name)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
    products = list(db.scalars(stmt))
    recipes = stock_repo.components_by_product(db, [p.id for p in products])
    return [
        (
            p,
            stock_rules.portions_available(
                (per_portion, article.quantity) for per_portion, article in recipes.get(p.id, [])
            ),
        )
        for p in products
    ]
