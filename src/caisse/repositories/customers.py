import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from caisse.models.customer import Customer


def get(db: Session, customer_id: uuid.UUID) -> Customer | None:
    return db.get(Customer, customer_id)


def get_by_ncc(db: Session, ncc: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.ncc == ncc))


def search(db: Session, *, text: str | None, ncc: str | None, limit: int = 50) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.company_name).limit(limit)
    if ncc:
        stmt = stmt.where(Customer.ncc.startswith(ncc))
    if text:
        pattern = f"%{text}%"
        stmt = stmt.where(or_(Customer.company_name.ilike(pattern), Customer.ncc.ilike(pattern)))
    return list(db.scalars(stmt))
