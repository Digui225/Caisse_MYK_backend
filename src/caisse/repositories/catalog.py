import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caisse.domain import stock_rules
from caisse.models.catalog import Category, Product, ProductPriceHistory
from caisse.repositories import stock as stock_repo


def list_categories(db: Session, *, is_active: bool | None = True) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if is_active is not None:
        stmt = stmt.where(Category.is_active.is_(is_active))
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


def get_category(db: Session, category_id: uuid.UUID) -> Category | None:
    return db.get(Category, category_id)


def get_category_by_name(db: Session, name: str) -> Category | None:
    return db.scalar(select(Category).where(func.lower(Category.name) == name.lower()))


def next_category_order(db: Session) -> int:
    return int(db.scalar(select(func.coalesce(func.max(Category.sort_order) + 1, 0))) or 0)


def active_products_count(db: Session, category_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(Product.id)).where(
                Product.category_id == category_id,
                Product.is_active.is_(True),
                Product.is_custom.is_(False),
            )
        )
        or 0
    )


def get_product(db: Session, product_id: uuid.UUID) -> Product | None:
    return db.get(Product, product_id)


def get_menu_product_by_name(db: Session, name: str) -> Product | None:
    """Produit du menu (hors articles libres) de ce nom, sans tenir compte de la casse."""
    return db.scalar(
        select(Product).where(
            func.lower(Product.name) == name.lower(), Product.is_custom.is_(False)
        )
    )


def get_product_by_sku(db: Session, sku: str) -> Product | None:
    return db.scalar(select(Product).where(Product.sku == sku))


def next_product_order(db: Session, category_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.max(Product.sort_order) + 1, 0)).where(
                Product.category_id == category_id
            )
        )
        or 0
    )


def price_history(db: Session, product_id: uuid.UUID) -> list[ProductPriceHistory]:
    return list(
        db.scalars(
            select(ProductPriceHistory)
            .where(ProductPriceHistory.product_id == product_id)
            .order_by(ProductPriceHistory.changed_at.desc(), ProductPriceHistory.id.desc())
        )
    )
