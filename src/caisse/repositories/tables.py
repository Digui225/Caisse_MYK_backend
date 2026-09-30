from datetime import date

from sqlalchemy import Row, and_, func, select
from sqlalchemy.orm import Session

from caisse.domain.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from caisse.models.order import Order
from caisse.models.table import RestaurantTable


def list_tables(db: Session, *, include_inactive: bool = False) -> list[RestaurantTable]:
    stmt = select(RestaurantTable).order_by(RestaurantTable.sort_order, RestaurantTable.label)
    if not include_inactive:
        stmt = stmt.where(RestaurantTable.is_active.is_(True))
    return list(db.scalars(stmt))


def board_rows(db: Session) -> list[Row[tuple[RestaurantTable, Order | None]]]:
    """Tables actives + commande active éventuelle, en une seule requête (pas de N+1)."""
    stmt = (
        select(RestaurantTable, Order)
        .outerjoin(
            Order,
            and_(Order.table_id == RestaurantTable.id, Order.status.in_(ACTIVE_ORDER_STATUSES)),
        )
        .where(RestaurantTable.is_active.is_(True))
        .order_by(RestaurantTable.sort_order, RestaurantTable.label)
    )
    return list(db.execute(stmt).all())  # type: ignore[arg-type]


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
