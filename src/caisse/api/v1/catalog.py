import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from caisse.deps import Ctx, CurrentUser, DbSession, Responsable
from caisse.errors import NotFoundError
from caisse.repositories import catalog as catalog_repo
from caisse.schemas.catalog import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CustomProductCreate,
    PriceChangeOut,
    PriceUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from caisse.schemas.common import Page
from caisse.services import catalog_service

router = APIRouter(tags=["Catalogue"])

CategoryId = Annotated[uuid.UUID, Path(description="Identifiant de la catégorie")]
ProductId = Annotated[uuid.UUID, Path(description="Identifiant du produit")]


@router.get("/categories", response_model=Page[CategoryOut], summary="Lister les catégories")
def list_categories(
    _: CurrentUser,
    db: DbSession,
    is_active: Annotated[
        bool | None, Query(description="true (défaut) : actives ; false : désactivées")
    ] = True,
) -> Page[CategoryOut]:
    """Catégories dans l'ordre d'affichage."""
    categories = catalog_repo.list_categories(db, is_active=is_active)
    return Page(items=[CategoryOut.model_validate(c) for c in categories])


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une catégorie",
)
def create_category(
    body: CategoryCreate, user: Responsable, db: DbSession, ctx: Ctx
) -> CategoryOut:
    """Erreurs : `409 CATEGORY_NAME_EXISTS` (`meta.category_id`), `422 VALIDATION_ERROR`."""
    category = catalog_service.create_category(db, body, actor_id=user.id, ctx=ctx)
    return CategoryOut.model_validate(category)


@router.patch(
    "/categories/{category_id}", response_model=CategoryOut, summary="Modifier une catégorie"
)
def update_category(
    category_id: CategoryId, body: CategoryUpdate, user: Responsable, db: DbSession, ctx: Ctx
) -> CategoryOut:
    """Seuls les champs envoyés changent ; `is_active: true` réactive une catégorie.

    Erreurs : `404 NOT_FOUND`, `409 CATEGORY_NAME_EXISTS`, `409 CATEGORY_NOT_EMPTY`
    (désactivation avec des produits actifs : `meta.active_products`).
    """
    category = catalog_service.update_category(db, category_id, body, actor_id=user.id, ctx=ctx)
    return CategoryOut.model_validate(category)


@router.delete(
    "/categories/{category_id}", response_model=CategoryOut, summary="Désactiver une catégorie"
)
def delete_category(
    category_id: CategoryId, user: Responsable, db: DbSession, ctx: Ctx
) -> CategoryOut:
    """Suppression logique (`is_active: false`) : l'historique des ventes reste lisible.
    Refusée tant que la catégorie a des produits actifs.

    Erreurs : `404 NOT_FOUND`, `409 CATEGORY_NOT_EMPTY` (`meta.active_products`).
    """
    category = catalog_service.update_category(
        db, category_id, CategoryUpdate(is_active=False), actor_id=user.id, ctx=ctx
    )
    return CategoryOut.model_validate(category)


@router.get("/products", response_model=Page[ProductOut], summary="Lister les produits")
def list_products(
    _: CurrentUser,
    db: DbSession,
    category_id: Annotated[uuid.UUID | None, Query(description="Limiter à une catégorie")] = None,
    search: Annotated[
        str | None, Query(description="Recherche dans le nom (sans tenir compte de la casse)")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="true : produits vendables ; false : produits désactivés")
    ] = True,
) -> Page[ProductOut]:
    """Produits du menu dans l'ordre d'affichage. `track_stock` : le produit a une fiche
    technique ; `stock_quantity` : portions encore vendables avec le stock actuel (minimum sur
    les articles de la fiche). Les produits créés à la volée n'y figurent pas."""
    rows = catalog_repo.list_products(
        db, category_id=category_id, search=search, is_active=is_active
    )
    items = [
        ProductOut.model_validate(product).model_copy(
            update={
                "track_stock": portions is not None,
                "stock_quantity": float(portions) if portions is not None else None,
            }
        )
        for product, portions in rows
    ]
    return Page(items=items)


@router.get("/products/{product_id}", response_model=ProductOut, summary="Détail d'un produit")
def get_product(product_id: ProductId, _: CurrentUser, db: DbSession) -> ProductOut:
    """Même format que `GET /products`, articles libres compris. Erreurs : `404 NOT_FOUND`."""
    product = catalog_repo.get_product(db, product_id)
    if product is None:
        raise NotFoundError(meta={"product_id": str(product_id)})
    return catalog_service.product_out(db, product)


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un produit",
)
def create_product(body: ProductCreate, user: Responsable, db: DbSession, ctx: Ctx) -> ProductOut:
    """Produit du menu, actif dès sa création. Pour qu'il déstocke, lui donner une fiche
    technique (`PUT /products/{id}/components`).

    Erreurs : `404 NOT_FOUND` (catégorie inconnue ou désactivée), `409 PRODUCT_NAME_EXISTS`
    (`meta.product_id`), `409 PRODUCT_SKU_EXISTS`, `422 VALIDATION_ERROR`.
    """
    product = catalog_service.create_product(db, body, actor_id=user.id, ctx=ctx)
    return catalog_service.product_out(db, product)


@router.patch("/products/{product_id}", response_model=ProductOut, summary="Modifier un produit")
def update_product(
    product_id: ProductId, body: ProductUpdate, user: Responsable, db: DbSession, ctx: Ctx
) -> ProductOut:
    """Seuls les champs envoyés changent ; `is_active: false` retire le produit du menu.
    Le prix ne se change pas ici : `PATCH /products/{id}/price`. Les commandes déjà saisies
    gardent leurs libellés, prix et TVA.

    Erreurs : `404 NOT_FOUND` (produit, ou catégorie inconnue ou désactivée),
    `409 PRODUCT_NAME_EXISTS`, `409 PRODUCT_SKU_EXISTS`, `422 VALIDATION_ERROR`.
    """
    product = catalog_service.update_product(db, product_id, body, actor_id=user.id, ctx=ctx)
    return catalog_service.product_out(db, product)


@router.patch("/products/{product_id}/price", response_model=ProductOut, summary="Changer le prix")
def change_price(
    product_id: ProductId, body: PriceUpdate, user: Responsable, db: DbSession, ctx: Ctx
) -> ProductOut:
    """Motif obligatoire ; historisé (`GET /products/{id}/price-history`) et tracé dans
    l'audit. Vaut pour les lignes ajoutées ensuite : une commande en cours garde ses prix.
    Un prix identique ne change rien.

    Erreurs : `404 NOT_FOUND`, `422 VALIDATION_ERROR`.
    """
    product = catalog_service.change_price(db, product_id, body, actor_id=user.id, ctx=ctx)
    return catalog_service.product_out(db, product)


@router.get(
    "/products/{product_id}/price-history",
    response_model=Page[PriceChangeOut],
    summary="Historique des prix",
)
def price_history(product_id: ProductId, _: Responsable, db: DbSession) -> Page[PriceChangeOut]:
    """Du plus récent au plus ancien. Erreurs : `404 NOT_FOUND`."""
    if catalog_repo.get_product(db, product_id) is None:
        raise NotFoundError(meta={"product_id": str(product_id)})
    rows = catalog_repo.price_history(db, product_id)
    return Page(items=[PriceChangeOut.model_validate(r) for r in rows])


@router.post(
    "/products/custom",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un article libre",
)
def create_custom_product(
    body: CustomProductCreate, user: CurrentUser, db: DbSession, ctx: Ctx
) -> ProductOut:
    """Produit créé à la volée pendant une commande (`is_custom: true`). Il n'apparaît jamais
    dans `GET /products` ; l'ajouter ensuite à la commande avec `POST /orders/{id}/items`.

    Erreurs : `404 NOT_FOUND` (catégorie inconnue ou désactivée), `422 VALIDATION_ERROR`.
    """
    product = catalog_service.create_custom_product(
        db,
        name=body.name,
        price_xof=body.price_xof,
        category_id=body.category_id,
        vat_rate=body.vat_rate,
        actor_id=user.id,
        ctx=ctx,
    )
    return ProductOut.model_validate(product)
