import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from caisse.errors import NotFoundError
from caisse.models.catalog import Category, Product
from caisse.repositories import settings as settings_repo
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext


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
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise NotFoundError(meta={"category_id": str(category_id)})
    name = name.strip()
    product = Product(
        category_id=category.id,
        name=name,
        short_name=name[:20].rstrip(),
        price_xof=price_xof,
        vat_rate=settings_repo.default_vat_rate(db) if vat_rate is None else vat_rate,
        track_stock=False,
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
