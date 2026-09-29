from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role
from caisse.errors import CaisseException
from caisse.models.user import User
from caisse.repositories.fne import FneRepository
from caisse.schemas.fne import FneDocumentResponse, FneGenerateRequest
from caisse.services.fne_service import FneService

router = APIRouter(prefix="/fne", tags=["Facturation Normalisée (FNE)"])


@router.post("/generate", response_model=FneDocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_fne_for_order(
    payload: FneGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("CAISSIER", "RESPONSABLE", "ADMIN")),
):
    """Génère à la demande une Facture Normalisée Électronique (FNE) pour une commande soldée."""
    service = FneService(db)
    doc = await service.create_and_submit_fne_for_order(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=list[FneDocumentResponse])
def list_fne_documents(
    status: Optional[str] = Query(None, description="Filtrer par statut (QUEUED, CERTIFIED, FAILED, MANUAL_EXPORTED)"),
    start_date: Optional[datetime] = Query(None, description="Date début"),
    end_date: Optional[datetime] = Query(None, description="Date fin"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = FneRepository(db)
    return repo.list_documents(
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}", response_model=FneDocumentResponse)
def get_fne_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = FneRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise CaisseException(
            code="FNE_DOCUMENT_NOT_FOUND",
            title="Document FNE introuvable",
            detail=f"Aucun document FNE avec l'ID {document_id}.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return doc


@router.post("/documents/{document_id}/retry", response_model=FneDocumentResponse)
async def retry_fne_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FneService(db)
    doc = await service.retry_document(document_id)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/export")
def export_fne_csv(
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    start_date: Optional[datetime] = Query(None, description="Date début"),
    end_date: Optional[datetime] = Query(None, description="Date fin"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FneService(db)
    csv_content = service.export_documents_csv(
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"fne_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
