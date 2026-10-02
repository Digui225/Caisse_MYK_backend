from datetime import date
from sqlalchemy.orm import Session, joinedload
from caisse.models.order import Order, OrderItem
from caisse.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: Session):
        super().__init__(db, Order)

    def get_by_id_with_items(self, order_id: str) -> Order | None:
        return (
            self.db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.id == str(order_id))
            .first()
        )

    def get_active_order_by_table_id(self, table_id: str) -> Order | None:
        return (
            self.db.query(Order)
            .filter(
                Order.table_id == str(table_id),
                Order.status.in_(["OPEN", "PARTIALLY_PAID"]),
            )
            .first()
        )

    def get_next_daily_sequence(self, business_date_str: str) -> int:
        count = (
            self.db.query(Order)
            .filter(Order.order_number.like(f"{business_date_str}-%"))
            .count()
        )
        return count + 1

    def add_item(self, item: OrderItem) -> OrderItem:
        self.db.add(item)
        self.db.flush()
        return item

    def get_item_by_id(self, item_id: str) -> OrderItem | None:
        return self.db.query(OrderItem).filter(OrderItem.id == str(item_id)).first()

    def list_orders(
        self,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Order]:
        query = self.db.query(Order).options(joinedload(Order.items))
        if session_id:
            query = query.filter(Order.cash_session_id == str(session_id))
        if status:
            query = query.filter(Order.status == status)
        return query.order_by(Order.opened_at.desc()).limit(limit).all()


def get(db: Session, order_id: str) -> Order | None:
    return db.get(Order, str(order_id))


def get_for_update(db: Session, order_id: str) -> Order | None:
    return db.query(Order).filter(Order.id == str(order_id)).with_for_update().first()


def active_items(db: Session, order_id: str) -> list[OrderItem]:
    return (
        db.query(OrderItem)
        .filter(OrderItem.order_id == str(order_id), OrderItem.removed_at.is_(None))
        .all()
    )
