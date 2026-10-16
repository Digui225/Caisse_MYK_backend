"""Catalogue (03-CONTRAT-API §4.3) : catégories, produits, prix historisé, articles libres.

Les lignes de commande figent nom, catégorie, prix et TVA à l'ajout : modifier le catalogue
ne change jamais une commande déjà saisie.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from caisse.domain import stock_rules
from caisse.errors import (
    CategoryNameExistsError,
    CategoryNotEmptyError,
    NotFoundError,
    ProductNameExistsError,
    ProductSkuExistsError,
)
from caisse.models.catalog import Category, Product, ProductPriceHistory
from caisse.repositories import catalog as catalog_repo
from caisse.repositories import settings as settings_repo
from caisse.repositories import stock as stock_repo
from caisse.schemas.catalog import (
    CategoryCreate,
    CategoryUpdate,
    PriceUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from caisse.security import utcnow
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext

# champs que `null` ne peut pas effacer
_CATEGORY_REQUIRED = {"name", "kind", "fiscal_group", "sort_order", "is_active"}
_PRODUCT_REQUIRED = {"category_id", "name", "short_name", "vat_rate", "sort_order", "is_active"}


def _changes(body: CategoryUpdate | ProductUpdate, required: set[str]) -> dict[str, Any]:
    return {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None or key not in required
    }


def _jsonable(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v if v is None or isinstance(v, bool | int) else str(v) for k, v in values.items()}


def product_out(db: Session, product: Product) -> ProductOut:
    """Format de `GET /products` : portions vendables d'après la fiche technique."""
    recipe = stock_repo.components_by_product(db, [product.id]).get(product.id, [])
    portions = stock_rules.portions_available(
        (per_portion, article.quantity) for per_portion, article in recipe
    )
    return ProductOut.model_validate(product).model_copy(
        update={
            "track_stock": portions is not None,
            "stock_quantity": float(portions) if portions is not None else None,
        }
    )


def _active_category(db: Session, category_id: uuid.UUID) -> Category:
    category = catalog_repo.get_category(db, category_id)
    if category is None or not category.is_active:
        raise NotFoundError(meta={"category_id": str(category_id)})
    return category


# --- Catégories --------------------------------------------------------------------------


def create_category(
    db: Session, body: CategoryCreate, *, actor_id: uuid.UUID, ctx: RequestContext
) -> Category:
    existing = catalog_repo.get_category_by_name(db, body.name)
    if existing is not None:
        raise CategoryNameExistsError(meta={"category_id": str(existing.id)})
    category = Category(
        name=body.name,
        kind=body.kind,
        fiscal_group=body.fiscal_group.upper(),
        color=body.color,
        sort_order=(
            body.sort_order if body.sort_order is not None else catalog_repo.next_category_order(db)
        ),
        is_active=True,
    )
    db.add(category)
    db.flush()
    audit_service.log(
        db,
        "category.create",
        ctx=ctx,
        user_id=actor_id,
        entity="category",
        entity_id=category.id,
        after=_jsonable(body.model_dump()),
    )
    db.commit()
    return category


def update_category(
    db: Session,
    category_id: uuid.UUID,
    body: CategoryUpdate,
    *,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> Category:
    """Mise à jour partielle. Désactiver une catégorie qui a des produits actifs est refusé :
    les retirer du menu d'abord, pour ne pas masquer de produits par accident."""
    category = catalog_repo.get_category(db, category_id)
    if category is None:
        raise NotFoundError(meta={"category_id": str(category_id)})
    changes = _changes(body, _CATEGORY_REQUIRED)
    name = changes.get("name")
    if name is not None and name.lower() != category.name.lower():
        existing = catalog_repo.get_category_by_name(db, name)
        if existing is not None:
            raise CategoryNameExistsError(meta={"category_id": str(existing.id)})
    if changes.get("is_active") is False and category.is_active:
        active = catalog_repo.active_products_count(db, category.id)
        if active:
            raise CategoryNotEmptyError(
                meta={"category_id": str(category.id), "active_products": active}
            )
    if "fiscal_group" in changes:
        changes["fiscal_group"] = changes["fiscal_group"].upper()
    before = {key: getattr(category, key) for key in changes}
    for key, value in changes.items():
        setattr(category, key, value)
    audit_service.log(
        db,
        "category.update",
        ctx=ctx,
        user_id=actor_id,
        entity="category",
        entity_id=category.id,
        before=_jsonable(before),
        after=_jsonable(changes),
    )
    db.commit()
    return category


# --- Produits ----------------------------------------------------------------------------


def _check_product_unique(
    db: Session, *, name: str | None, sku: str | None, exclude: uuid.UUID | None = None
) -> None:
    if name is not None:
        existing = catalog_repo.get_menu_product_by_name(db, name)
        if existing is not None and existing.id != exclude:
            raise ProductNameExistsError(meta={"product_id": str(existing.id)})
    if sku:
        existing = catalog_repo.get_product_by_sku(db, sku)
        if existing is not None and existing.id != exclude:
            raise ProductSkuExistsError(meta={"product_id": str(existing.id), "sku": sku})


def _flush_product(db: Session, product: Product) -> None:
    try:
        db.flush()
    except IntegrityError:  # sku saisi en même temps sur un autre poste
        db.rollback()
        raise ProductSkuExistsError(meta={"sku": product.sku}) from None


def create_product(
    db: Session, body: ProductCreate, *, actor_id: uuid.UUID, ctx: RequestContext
) -> Product:
    category = _active_category(db, body.category_id)
    _check_product_unique(db, name=body.name, sku=body.sku)
    product = Product(
        category_id=category.id,
        name=body.name,
        short_name=body.short_name or body.name[:20].rstrip(),
        price_xof=body.price_xof,
        vat_rate=settings_repo.default_vat_rate(db) if body.vat_rate is None else body.vat_rate,
        is_custom=False,
        is_active=True,
        sort_order=(
            body.sort_order
            if body.sort_order is not None
            else catalog_repo.next_product_order(db, category.id)
        ),
        color=body.color,
        sku=body.sku or None,
    )
    db.add(product)
    _flush_product(db, product)
    audit_service.log(
        db,
        "product.create",
        ctx=ctx,
        user_id=actor_id,
        entity="product",
        entity_id=product.id,
        after=_jsonable(body.model_dump()),
    )
    db.commit()
    return product


def _product(db: Session, product_id: uuid.UUID) -> Product:
    product = catalog_repo.get_product(db, product_id)
    if product is None:
        raise NotFoundError(meta={"product_id": str(product_id)})
    return product


def update_product(
    db: Session,
    product_id: uuid.UUID,
    body: ProductUpdate,
    *,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> Product:
    product = _product(db, product_id)
    changes = _changes(body, _PRODUCT_REQUIRED)
    if "category_id" in changes:
        _active_category(db, changes["category_id"])
    if changes.get("sku") == "":
        changes["sku"] = None
    _check_product_unique(
        db,
        name=changes.get("name") if not product.is_custom else None,
        sku=changes.get("sku"),
        exclude=product.id,
    )
    before = {key: getattr(product, key) for key in changes}
    for key, value in changes.items():
        setattr(product, key, value)
    _flush_product(db, product)
    audit_service.log(
        db,
        "product.update",
        ctx=ctx,
        user_id=actor_id,
        entity="product",
        entity_id=product.id,
        before=_jsonable(before),
        after=_jsonable(changes),
    )
    db.commit()
    return product


def change_price(
    db: Session,
    product_id: uuid.UUID,
    body: PriceUpdate,
    *,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> Product:
    """Nouveau prix, historisé avec son motif. Un prix identique ne crée pas d'historique."""
    product = _product(db, product_id)
    old_price = product.price_xof
    if body.price_xof == old_price:
        return product
    product.price_xof = body.price_xof
    db.add(
        ProductPriceHistory(
            product_id=product.id,
            old_price_xof=old_price,
            new_price_xof=body.price_xof,
            changed_by=actor_id,
            changed_at=utcnow(),
            reason=body.reason,
        )
    )
    audit_service.log(
        db,
        "product.price_change",
        ctx=ctx,
        user_id=actor_id,
        entity="product",
        entity_id=product.id,
        before={"price_xof": old_price},
        after={"price_xof": body.price_xof},
        reason=body.reason,
    )
    db.commit()
    return product


def create_custom_product(
    db: Session,
    *,
    name: str,
    price_xof: int,
    category_id: uuid.UUID,
    vat_rate: Decimal | None,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> Product:
    """Article créé à la volée pendant une commande : jamais listé dans le menu (§7.2)."""
    category = _active_category(db, category_id)
    name = name.strip()
    product = Product(
        category_id=category.id,
        name=name,
        short_name=name[:20].rstrip(),
        price_xof=price_xof,
        vat_rate=settings_repo.default_vat_rate(db) if vat_rate is None else vat_rate,
        is_custom=True,
        is_active=True,
    )
    db.add(product)
    db.flush()
    audit_service.log(
        db,
        "product.create_custom",
        ctx=ctx,
        user_id=actor_id,
        entity="product",
        entity_id=product.id,
        after={"name": name, "price_xof": price_xof, "category_id": str(category_id)},
    )
    db.commit()
    return product
