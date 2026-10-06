from sqlalchemy.orm import Session, joinedload
from caisse.models.table import RestaurantTable
from caisse.models.order import Order
from caisse.repositories.base import BaseRepository


class TableRepository(BaseRepository[RestaurantTable]):
    def __init__(self, db: Session):
        super().__init__(db, RestaurantTable)

    def list_active_tables(self) -> list[RestaurantTable]:
        return (
            self.db.query(RestaurantTable)
            .filter(RestaurantTable.is_active.is_(True))
            .order_by(RestaurantTable.sort_order.asc(), RestaurantTable.label.asc())
            .all()
        )

    def get_by_label(self, label: str) -> RestaurantTable | None:
        return self.db.query(RestaurantTable).filter(RestaurantTable.label == label).first()

    def get_table_board_data(self) -> list[dict]:
        tables = self.list_active_tables()
        table_ids = [t.id for t in tables]

        # Récupération en une seule requête de toutes les commandes actives
        active_orders = (
            self.db.query(Order)
            .options(joinedload(Order.opened_by), joinedload(Order.items))
            .filter(
                Order.table_id.in_(table_ids),
                Order.status.in_(["OPEN", "PARTIALLY_PAID"]),
            )
            .all()
        )
        orders_by_table_id = {o.table_id: o for o in active_orders}

        board_items = []
        for t in tables:
            active_order = orders_by_table_id.get(t.id)
            if active_order:
                active_items = [it for it in active_order.items if not it.removed_at]
                items_count = sum(it.quantity for it in active_items)
                last_cat = active_items[-1].category_snapshot if active_items else None
                service_step = f"{last_cat} / En cours" if last_cat else "En cours"

                items_summary = [
                    {
                        "name": it.product_name_snapshot,
                        "quantity": it.quantity,
                        "line_total_xof": it.line_total_xof,
                        "unit_price_xof": it.unit_price_xof,
                        "note": it.note,
                    }
                    for it in active_items
                ]

                board_items.append(
                    {
                        "id": t.id,
                        "label": t.label,
                        "zone": t.zone,
                        "seats": t.seats,
                        "is_occupied": True,
                        "current_order_id": active_order.id,
                        "current_order_number": active_order.order_number,
                        "current_total_ttc_xof": active_order.total_ttc_xof,
                        "guests_count": active_order.guests_count,
                        "opened_at": active_order.opened_at.isoformat() if active_order.opened_at else None,
                        "server_name": active_order.opened_by.full_name if active_order.opened_by else "Serveur",
                        "items_count": items_count,
                        "service_step": service_step,
                        "items_summary": items_summary,
                    }
                )
            else:
                board_items.append(
                    {
                        "id": t.id,
                        "label": t.label,
                        "zone": t.zone,
                        "seats": t.seats,
                        "is_occupied": False,
                        "current_order_id": None,
                        "current_order_number": None,
                        "current_total_ttc_xof": 0,
                        "guests_count": None,
                        "opened_at": None,
                        "server_name": None,
                        "items_count": None,
                        "service_step": None,
                        "items_summary": [],
                    }
                )
        return board_items
