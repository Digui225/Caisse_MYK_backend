from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role, require_device_id
from caisse.models.user import User
from caisse.schemas.catalog import (
    CategoryResponse,
    CategoryCreateRequest,
    ProductResponse,
    ProductCreateRequest,
    ProductPriceUpdateRequest,
)
from caisse.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalogue"])


@router.get("/categories", response_model=list[CategoryResponse], summary="Lister les catégories actives")
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    service = CatalogService(db)
    return service.list_categories()


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une catégorie (Responsable/Admin)",
)
async def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    service = CatalogService(db)
    return service.create_category(payload, user_id=current_user.id, device_id=device_id)


@router.get("/products", response_model=list[ProductResponse], summary="Lister les produits actifs du menu")
async def list_products(
    category_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    service = CatalogService(db)
    return service.list_products(category_id=category_id)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un produit (Responsable/Admin)",
)
async def create_product(
    payload: ProductCreateRequest,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> ProductResponse:
    service = CatalogService(db)
    return service.create_product(payload, user_id=current_user.id, device_id=device_id)


@router.patch(
    "/products/{id}/price",
    response_model=ProductResponse,
    summary="Modifier le prix d'un produit (tracé, Responsable/Admin)",
)
async def update_product_price(
    id: str,
    payload: ProductPriceUpdateRequest,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> ProductResponse:
    service = CatalogService(db)
    return service.update_product_price(id, payload, user_id=current_user.id, device_id=device_id)
