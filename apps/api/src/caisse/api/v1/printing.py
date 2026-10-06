from typing import Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role, require_device_id
from caisse.models.user import User
from caisse.models.order import Order
from caisse.errors import CaisseException
from caisse.services.printing_service import PrintingService

router = APIRouter(prefix="/printing", tags=["Impression & Tiroir"])


@router.get("/status", summary="État de l'imprimante USB et du service d'impression")
async def get_printer_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = PrintingService(db)
    return service.get_status()


@router.post("/reprint/{order_id}", status_code=status.HTTP_202_ACCEPTED, summary="Ré-imprimer un duplicata de ticket (tracé)")
async def reprint_ticket(
    order_id: str,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = PrintingService(db)
    if order_id.startswith("Z-"):
        session_id = order_id[2:]
        job = service.print_z_report(
            session_id=session_id,
            cashier_name=current_user.full_name,
            user_id=current_user.id,
            device_id=device_id,
        )
        return {
            "message": "Job d'impression du Rapport Z créé",
            "print_job_id": job.id,
            "is_reprint": False,
            "session_id": session_id,
        }

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise CaisseException(
            code="ORDER_NOT_FOUND",
            title="Commande introuvable",
            detail=f"Aucune commande trouvée avec l'ID {order_id}.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    job = service.reprint_ticket(
        order=order,
        cashier_name=current_user.full_name,
        user_id=current_user.id,
        device_id=device_id,
    )

    return {
        "message": "Job d'impression de duplicata créé",
        "print_job_id": job.id,
        "is_reprint": True,
        "order_id": order_id,
    }


@router.post("/z-report/{session_id}", status_code=status.HTTP_202_ACCEPTED, summary="Imprimer le ticket de Rapport Z fiscal")
async def print_z_report_endpoint(
    session_id: str,
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = PrintingService(db)
    job = service.print_z_report(
        session_id=session_id,
        cashier_name=current_user.full_name,
        user_id=current_user.id,
        device_id=device_id,
    )
    return {
        "message": "Job d'impression du Rapport Z créé",
        "print_job_id": job.id,
        "session_id": session_id,
    }



@router.post("/open-drawer", status_code=status.HTTP_200_OK, summary="Ouvrir le tiroir-caisse manuellement (rôle responsable)")
async def open_drawer_manually(
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = PrintingService(db)
    service.manual_open_drawer(user_id=current_user.id, device_id=device_id)
    return {"message": "Impulsion ouverture tiroir envoyée"}


class TestTicketRequest(BaseModel):
    custom_header: str | None = None
    custom_footer: str | None = None
    width: int = 32


@router.post("/test-ticket", status_code=status.HTTP_200_OK, summary="Imprimer un ticket de test directement en ESC/POS")
async def print_test_ticket(
    payload: TestTicketRequest | None = None,
    current_user: User = Depends(require_role("RESPONSABLE", "ADMIN")),
    device_id: str = Depends(require_device_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = PrintingService(db)
    custom_header = payload.custom_header if payload else None
    custom_footer = payload.custom_footer if payload else None
    width = payload.width if payload and payload.width else 32
    return service.print_test_ticket(
        user_id=current_user.id,
        device_id=device_id,
        custom_header=custom_header,
        custom_footer=custom_footer,
        width=width,
    )


