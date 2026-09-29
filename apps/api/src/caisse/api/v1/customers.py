from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role
from caisse.errors import CaisseException
from caisse.models.customer import Customer
from caisse.models.user import User
from caisse.repositories.customers import CustomerRepository
from caisse.schemas.customer import CustomerCreate, CustomerResponse

router = APIRouter(prefix="/customers", tags=["Clients & FNE"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    q: Optional[str] = Query(None, description="Recherche par nom, NCC ou téléphone"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CustomerRepository(db)
    return repo.search(query=q, limit=limit)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CustomerRepository(db)
    if payload.ncc:
        existing = repo.get_by_ncc(payload.ncc)
        if existing:
            raise CaisseException(
                code="CUSTOMER_NCC_EXISTS",
                title="Client déjà existant",
                detail=f"Un client avec le NCC {payload.ncc} existe déjà ({existing.name}).",
                status_code=status.HTTP_409_CONFLICT,
            )

    customer = Customer(
        name=payload.name,
        ncc=payload.ncc,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
    )
    repo.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CustomerRepository(db)
    cust = repo.get_by_id(customer_id)
    if not cust:
        raise CaisseException(
            code="CUSTOMER_NOT_FOUND",
            title="Client introuvable",
            detail=f"Aucun client trouvé avec l'ID {customer_id}.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return cust
