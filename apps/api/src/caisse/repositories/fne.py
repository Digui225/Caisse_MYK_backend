import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caisse.domain.enums import (
    FneDocumentType,
    FneStatus,
    OrderStatus,
    PaymentMethod,
)
from caisse.models.fne import FneDocument
from caisse.models.order import Order, OrderItem
from caisse.models.payment import Payment

# en attente d'une action (certification, renvoi ou vérification)
PENDING_STATUSES = (FneStatus.PENDING, FneStatus.QUEUED, FneStatus.SUBMITTING, FneStatus.FAILED)


def get(db: Session, document_id: str) -> FneDocument | None:
    return db.get(FneDocument, str(document_id))


def get_for_update(db: Session, document_id: str) -> FneDocument | None:
    return db.scalar(select(FneDocument).where(FneDocument.id == str(document_id)).with_for_update())


def sale_for_order(db: Session, order_id: str) -> FneDocument | None:
    return db.scalar(
        select(FneDocument).where(
            FneDocument.order_id == str(order_id), FneDocument.type == FneDocumentType.FNE
        )
    )


def refunds_of(db: Session, parent_id: str) -> list[FneDocument]:
    return list(
        db.scalars(
            select(FneDocument)
            .where(FneDocument.parent_document_id == str(parent_id))
            .order_by(FneDocument.created_at)
        )
    )


def list_documents(
    db: Session, *, status: str | None = None, start_date: datetime | None = None, limit: int = 200
) -> list[FneDocument]:
    stmt = select(FneDocument).order_by(FneDocument.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(FneDocument.status == status)
    if start_date is not None:
        stmt = stmt.where(FneDocument.created_at >= start_date)
    return list(db.scalars(stmt))


def pending_counts(db: Session) -> tuple[int, int, int]:
    """(en attente, dont incertains, dont refusés)."""
    row = db.execute(
        select(
            func.count(),
            func.count().filter(FneDocument.is_uncertain.is_(True)),
            func.count().filter(FneDocument.status == FneStatus.FAILED),
        ).where(FneDocument.status.in_(PENDING_STATUSES))
    ).one()
    return int(row[0]), int(row[1]), int(row[2])


def order_numbers(db: Session, order_ids: set[str]) -> dict[str, str]:
    if not order_ids:
        return {}
    clean_ids = [str(oid) for oid in order_ids]
    rows = db.execute(select(Order.id, Order.order_number).where(Order.id.in_(clean_ids)))
    return {str(order_id): number for order_id, number in rows}


def captured_payments(db: Session, order_id: str) -> list[tuple[PaymentMethod, int]]:
    rows = db.execute(
        select(Payment.method, Payment.amount_xof)
        .where(Payment.order_id == str(order_id), Payment.status == "CAPTURED")
        .order_by(Payment.created_at)
    )
    res = []
    for method_str, amount in rows:
        try:
            m = PaymentMethod(method_str)
        except ValueError:
            m = PaymentMethod.CASH
        res.append((m, int(amount)))
    return res


def paid_orders_totals(db: Session, business_date: date) -> tuple[int, int]:
    row = db.execute(
        select(func.count(), func.coalesce(func.sum(Order.total_ttc_xof), 0)).where(
            func.date(Order.opened_at) == business_date, Order.status == OrderStatus.PAID
        )
    ).one()
    return int(row[0]), int(row[1])


def certified_orders_totals(db: Session, business_date: date) -> tuple[int, int]:
    row = db.execute(
        select(func.count(), func.coalesce(func.sum(Order.total_ttc_xof), 0))
        .join(FneDocument, FneDocument.order_id == Order.id)
        .where(
            func.date(Order.opened_at) == business_date,
            FneDocument.type == FneDocumentType.FNE,
            FneDocument.status == FneStatus.CERTIFIED,
        )
    ).one()
    return int(row[0]), int(row[1])


def pending_for_date(db: Session, business_date: date) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(FneDocument)
            .join(Order, Order.id == FneDocument.order_id)
            .where(func.date(Order.opened_at) == business_date, FneDocument.status.in_(PENDING_STATUSES))
        )
        or 0
    )


def fiscal_group_totals(db: Session, business_date: date) -> list[tuple[str, int, int]]:
    rows = db.execute(
        select(
            OrderItem.category_snapshot,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.line_total_xof),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            func.date(Order.opened_at) == business_date,
            Order.status == OrderStatus.PAID,
            OrderItem.removed_at.is_(None),
        )
        .group_by(OrderItem.category_snapshot)
        .order_by(OrderItem.category_snapshot)
    )
    return [(group or "DIVERS", int(qty), int(amount)) for group, qty, amount in rows]


class FneRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, fne_id: str) -> Optional[FneDocument]:
        return get(self.db, fne_id)

    def get_by_order_id(self, order_id: str) -> Optional[FneDocument]:
        return sale_for_order(self.db, order_id)

    def list_documents(
        self,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FneDocument]:
        q = self.db.query(FneDocument)
        if status:
            q = q.filter(FneDocument.status == status)
        if start_date:
            q = q.filter(FneDocument.created_at >= start_date)
        if end_date:
            q = q.filter(FneDocument.created_at <= end_date)
        return q.order_by(FneDocument.created_at.desc()).limit(limit).offset(offset).all()

    def add(self, doc: FneDocument) -> FneDocument:
        self.db.add(doc)
        self.db.flush()
        return doc
