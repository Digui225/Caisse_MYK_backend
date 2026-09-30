import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from caisse.deps import CurrentUser, DbSession
from caisse.repositories import catalog as catalog_repo
from caisse.schemas.catalog import CategoryOut, ProductOut
from caisse.schemas.common import Page

router = APIRouter(tags=["Catalogue"])


@router.get("/categories", response_model=Page[CategoryOut], summary="Lister les catégories")
def list_categories(_: CurrentUser, db: DbSession) -> Page[CategoryOut]:
    """Catégories actives, dans l'ordre d'affichage."""
    return Page(items=[CategoryOut.model_validate(c) for c in catalog_repo.list_categories(db)])


@router.get("/products", response_model=Page[ProductOut], summary="Lister les produits")
def list_products(
    _: CurrentUser,
    db: DbSession,
    category_id: Annotated[
        uuid.UUID | None, Query(description="Limiter à une catégorie")
    ] = None,
    search: Annotated[
        str | None, Query(description="Recherche dans le nom (sans tenir compte de la casse)")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="true : produits vendables ; false : produits désactivés")
    ] = True,
) -> Page[ProductOut]:
    """Produits du menu avec leur stock, dans l'ordre d'affichage. Les produits créés à la
    volée pendant une commande n'y figurent pas."""
    rows = catalog_repo.list_products(
        db, category_id=category_id, search=search, is_active=is_active
    )
    items = [
        ProductOut.model_validate(product).model_copy(
            update={
                "stock_quantity": float(qty) if product.track_stock and qty is not None else None,
            }
        )
        for product, qty in rows
    ]
    return Page(items=items)
