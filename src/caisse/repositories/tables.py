import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caisse.domain.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from caisse.models.order import Order
from caisse.models.table import RestaurantTable


def list_tables(db: Session, *, is_active: bool | None = True) -> list[RestaurantTable]:
    stmt = select(RestaurantTable).order_by(RestaurantTable.sort_order, RestaurantTable.label)
    if is_active is not None:
        stmt = stmt.where(RestaurantTable.is_active.is_(is_active))
    return list(db.scalars(stmt))


def get(db: Session, table_id: uuid.UUID) -> RestaurantTable | None:
    return db.get(RestaurantTable, table_id)


def get_for_update(db: Session, table_id: uuid.UUID) -> RestaurantTable | None:
    """Verrou de ligne : sérialise l'ouverture de commandes sur une même table."""
    return db.scalar(
        select(RestaurantTable).where(RestaurantTable.id == table_id).with_for_update()
    )


def get_by_label(db: Session, label: str) -> RestaurantTable | None:
    return db.scalar(
        select(RestaurantTable).where(func.lower(RestaurantTable.label) == label.lower())
    )


def next_sort_order(db: Session) -> int:
    return int(db.scalar(select(func.coalesce(func.max(RestaurantTable.sort_order) + 1, 0))) or 0)


def board_rows(db: Session) -> list[tuple[RestaurantTable, list[Order]]]:
    """Tables actives et leurs commandes actives (plusieurs si la table est partagée), de la
    plus ancienne à la plus récente. Deux requêtes, quel que soit le nombre de tables."""
    tables = list_tables(db)
    by_table: dict[uuid.UUID, list[Order]] = defaultdict(list)
    for order in db.scalars(
        select(Order)
        .where(
            Order.table_id.in_([t.id for t in tables]),
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .order_by(Order.opened_at, Order.id)
    ):
        if order.table_id is not None:
            by_table[order.table_id].append(order)
    return [(table, by_table.get(table.id, [])) for table in tables]


def day_summary(db: Session, business_date: date) -> tuple[int, int, int]:
    """(CA encaissé, nb de commandes soldées, nb de commandes ouvertes) pour la journée."""
    paid = Order.status == OrderStatus.PAID
    active = Order.status.in_(ACTIVE_ORDER_STATUSES)
    row = db.execute(
        select(
            func.coalesce(func.sum(Order.total_ttc_xof).filter(paid), 0),
            func.count().filter(paid),
            func.count().filter(active),
        ).where(Order.business_date == business_date)
    ).one()
    return int(row[0]), int(row[1]), int(row[2])
