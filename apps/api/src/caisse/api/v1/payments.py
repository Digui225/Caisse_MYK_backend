from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import require_role, require_device_id, require_idempotency_key
from caisse.models.user import User
from caisse.schemas.payments import PaymentRequest, OrderPaymentResult, PaymentResponse
from caisse.services.payment_service import PaymentService

router = APIRouter(prefix="/orders", tags=["Encaissement & Paiements"])


@router.post(
    "/{id}/payments",
    response_model=OrderPaymentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Encaisser un paiement (idempotent)",
)
async def process_payment(
    id: str,
    payload: PaymentRequest,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    idempotency_key: str = Depends(require_idempotency_key),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> OrderPaymentResult:
    service = PaymentService(db)
    return await service.process_payment(
        order_id=id,
        payload=payload,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        device_id=device_id,
    )


@router.get(
    "/{id}/payments",
    response_model=list[PaymentResponse],
    summary="Lister les règlements d'une commande",
)
async def list_order_payments(
    id: str,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    db: Session = Depends(get_db),
) -> list[PaymentResponse]:
    service = PaymentService(db)
    return service.list_order_payments(order_id=id)
