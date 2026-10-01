import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.domain.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from caisse.models.order import Order, OrderItem


def get(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.get(Order, order_id)


def get_for_update(db: Session, order_id: uuid.UUID) -> Order | None:
    """Verrou de ligne : deux postes qui modifient la même commande se sérialisent."""
    return db.scalar(select(Order).where(Order.id == order_id).with_for_update())


def active_for_table(db: Session, table_id: uuid.UUID) -> Order | None:
    return db.scalar(
        select(Order).where(Order.table_id == table_id, Order.status.in_(ACTIVE_ORDER_STATUSES))
    )


def list_orders(
    db: Session, *, business_date: date, status: OrderStatus | None = None
) -> list[Order]:
    stmt = (
        select(Order).where(Order.business_date == business_date).order_by(Order.opened_at.desc())
    )
    if status is not None:
        stmt = stmt.where(Order.status == status)
    return list(db.scalars(stmt))


def active_items(db: Session, order_id: uuid.UUID) -> list[OrderItem]:
    return list(
        db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order_id, OrderItem.removed_at.is_(None))
            .order_by(OrderItem.added_at, OrderItem.id)
        )
    )


def get_active_item(db: Session, order_id: uuid.UUID, item_id: uuid.UUID) -> OrderItem | None:
    return db.scalar(
        select(OrderItem).where(
            OrderItem.id == item_id,
            OrderItem.order_id == order_id,
            OrderItem.removed_at.is_(None),
        )
    )
