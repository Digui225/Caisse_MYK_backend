import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from caisse.errors import CustomerNccExistsError
from caisse.models.customer import Customer
from caisse.repositories import customers as customers_repo
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext


def create_customer(
    db: Session,
    *,
    company_name: str,
    ncc: str | None,
    tax_regime: str | None,
    address: str | None,
    phone: str | None,
    email: str | None,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> Customer:
    """Un NCC n'appartient qu'à un client : un doublon renvoie l'existant dans `meta`."""
    if ncc is not None:
        existing = customers_repo.get_by_ncc(db, ncc)
        if existing is not None:
            raise CustomerNccExistsError(meta={"customer_id": str(existing.id), "ncc": ncc})
    customer = Customer(
        company_name=company_name,
        ncc=ncc,
        tax_regime=tax_regime,
        address=address,
        phone=phone,
        email=email,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = customers_repo.get_by_ncc(db, ncc) if ncc else None
        raise CustomerNccExistsError(
            meta={"customer_id": str(existing.id) if existing else None, "ncc": ncc}
        ) from None
    audit_service.log(
        db,
        "customer.create",
        ctx=ctx,
        user_id=actor_id,
        entity="customer",
        entity_id=customer.id,
        after={"company_name": company_name, "ncc": ncc},
    )
    db.commit()
    return customer
