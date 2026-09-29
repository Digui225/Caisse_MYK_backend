from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role, require_device_id
from caisse.models.user import User
from caisse.schemas.stock import StockItemResponse, StockMovementRequest, StockMovementResponse
from caisse.services.stock_service import StockService

router = APIRouter(prefix="/stock", tags=["Gestion des Stocks"])


class InventoryCountRequest(BaseModel):
    product_id: str
    counted_quantity: float = Field(..., ge=0)
    reason: str = Field(default="Inventaire physique périodique", min_length=3)


@router.get("", response_model=list[StockItemResponse], summary="Lister l'état des stocks")
async def list_stock(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StockItemResponse]:
    service = StockService(db)
    return service.list_stock_items()


@router.get("/movements", response_model=list[StockMovementResponse], summary="Historique des mouvements de stock")
async def list_stock_movements(
    product_id: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StockMovementResponse]:
    service = StockService(db)
    return service.list_movements(product_id=product_id, limit=limit)


@router.post(
    "/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer une entrée/sortie/ajustement de stock",
)
async def create_stock_movement(
    payload: StockMovementRequest,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> StockMovementResponse:
    service = StockService(db)
    return service.record_movement(
        payload=payload,
        user_id=current_user.id,
        device_id=device_id,
    )


@router.post(
    "/inventory",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajustement par inventaire physique",
)
async def record_inventory(
    payload: InventoryCountRequest,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> StockMovementResponse:
    service = StockService(db)
    return service.record_inventory_count(
        product_id=payload.product_id,
        counted_quantity=payload.counted_quantity,
        user_id=current_user.id,
        reason=payload.reason,
        device_id=device_id,
    )
