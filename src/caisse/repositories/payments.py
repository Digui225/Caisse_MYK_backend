import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caisse.domain.enums import PaymentStatus
from caisse.models.payment import Payment


def get(db: Session, payment_id: uuid.UUID) -> Payment | None:
    return db.get(Payment, payment_id)


def for_order(db: Session, order_id: uuid.UUID) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.created_at, Payment.id)
        )
    )


def captured_total(db: Session, order_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount_xof), 0)).where(
                Payment.order_id == order_id, Payment.status == PaymentStatus.CAPTURED
            )
        )
        or 0
    )
