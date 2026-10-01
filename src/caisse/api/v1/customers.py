from typing import Annotated

from fastapi import APIRouter, Query, status

from caisse.deps import Ctx, CurrentUser, DbSession
from caisse.repositories import customers as customers_repo
from caisse.schemas.common import Page
from caisse.schemas.customers import CustomerCreate, CustomerOut
from caisse.services import customer_service

router = APIRouter(prefix="/customers", tags=["Clients entreprise"])


@router.get("", response_model=Page[CustomerOut], summary="Rechercher un client entreprise")
def list_customers(
    _: CurrentUser,
    db: DbSession,
    search: Annotated[
        str | None, Query(max_length=80, description="Raison sociale ou NCC (contient)")
    ] = None,
    ncc: Annotated[
        str | None, Query(max_length=32, description="NCC (commence par), ex. 9506466A")
    ] = None,
) -> Page[CustomerOut]:
    """50 résultats au plus, par raison sociale. Sert à retrouver un client par son NCC au
    moment d'émettre une FNE."""
    normalized = ncc.replace(" ", "").upper() if ncc else None
    customers = customers_repo.search(db, text=search, ncc=normalized)
    return Page(items=[CustomerOut.model_validate(c) for c in customers])


@router.post(
    "",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un client entreprise",
)
def create_customer(
    body: CustomerCreate, user: CurrentUser, db: DbSession, ctx: Ctx
) -> CustomerOut:
    """Le NCC (7 chiffres + 1 lettre) est contrôlé ici : la FNE ne le vérifie pas à la saisie.

    Erreurs : `409 CUSTOMER_NCC_EXISTS` (`meta.customer_id` : client existant à réutiliser),
    `422 VALIDATION_ERROR` (format du NCC : `meta.fields[0].loc = ["body", "ncc"]`).
    """
    customer = customer_service.create_customer(db, **body.model_dump(), actor_id=user.id, ctx=ctx)
    return CustomerOut.model_validate(customer)
