from sqlalchemy.orm import Session, joinedload
from caisse.models.stock import StockItem, StockMovement
from caisse.repositories.base import BaseRepository


class StockRepository(BaseRepository[StockItem]):
    def __init__(self, db: Session):
        super().__init__(db, StockItem)

    def get_by_product_id(self, product_id: str) -> StockItem | None:
        return (
            self.db.query(StockItem)
            .options(joinedload(StockItem.product))
            .filter(StockItem.product_id == product_id)
            .first()
        )

    def get_or_create_for_product(
        self,
        product_id: str,
        default_unit: str = "bouteille",
        alert_threshold: float = 5.0,
    ) -> StockItem:
        item = self.get_by_product_id(product_id)
        if not item:
            item = StockItem(
                product_id=product_id,
                quantity=0.0,
                unit=default_unit,
                alert_threshold=alert_threshold,
            )
            self.db.add(item)
            self.db.flush()
        return item

    def list_items(self) -> list[StockItem]:
        return (
            self.db.query(StockItem)
            .options(joinedload(StockItem.product))
            .join(StockItem.product)
            .order_by(StockItem.quantity.asc())
            .all()
        )

    def add_movement(self, movement: StockMovement) -> StockMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def list_movements(self, product_id: str | None = None, limit: int = 50) -> list[StockMovement]:
        query = self.db.query(StockMovement).options(
            joinedload(StockMovement.product),
            joinedload(StockMovement.user),
        )
        if product_id:
            query = query.filter(StockMovement.product_id == product_id)
        return query.order_by(StockMovement.created_at.desc()).limit(limit).all()
