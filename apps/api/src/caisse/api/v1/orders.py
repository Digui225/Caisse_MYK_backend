from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role, require_device_id
from caisse.models.user import User
from caisse.schemas.orders import (
    OrderResponse,
    OrderCreateRequest,
    OrderItemAddRequest,
    OrderItemRemoveRequest,
    OrderCancelRequest,
)
from caisse.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Commandes"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, summary="Créer une commande")
async def create_order(
    payload: OrderCreateRequest,
    current_user: User = Depends(require_role("CAISSIER")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    return service.create_order(payload, user_id=current_user.id, device_id=device_id)


@router.get("", response_model=list[OrderResponse], summary="Lister les commandes")
async def list_orders(
    session_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrderResponse]:
    service = OrderService(db)
    return service.list_orders(session_id=session_id, status=status, limit=limit)


@router.get("/{id}", response_model=OrderResponse, summary="Détail d'une commande")
async def get_order(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    return service.get_order(id)


@router.post("/{id}/items", response_model=OrderResponse, summary="Ajouter une ligne de commande")
async def add_order_item(
    id: str,
    payload: OrderItemAddRequest,
    current_user: User = Depends(require_role("CAISSIER")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    return service.add_item(id, payload, user_id=current_user.id, device_id=device_id)


@router.delete("/{id}/items/{item_id}", response_model=OrderResponse, summary="Retirer une ligne (tracé)")
async def remove_order_item(
    id: str,
    item_id: str,
    payload: OrderItemRemoveRequest,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    return service.remove_item(id, item_id, payload, user_id=current_user.id, device_id=device_id)


@router.post("/{id}/cancel", response_model=OrderResponse, summary="Annuler une commande (tracé)")
async def cancel_order(
    id: str,
    payload: OrderCancelRequest,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    return service.cancel_order(id, payload, user_id=current_user.id, device_id=device_id)
