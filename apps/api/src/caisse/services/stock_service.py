from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import status

from caisse.domain.enums import StockMovementType
from caisse.domain.stock_rules import (
    validate_movement_quantity,
    calculate_quantity_after,
    is_stock_low,
)
from caisse.errors import CaisseException
from caisse.models.catalog import Product
from caisse.models.order import Order
from caisse.models.stock import StockItem, StockMovement
from caisse.repositories.stock import StockRepository
from caisse.schemas.stock import StockItemResponse, StockMovementRequest, StockMovementResponse
from caisse.services.audit_service import AuditService


class StockService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StockRepository(db)
        self.audit = AuditService(db)

    def record_movement(
        self,
        payload: StockMovementRequest,
        user_id: str,
        order_id: str | None = None,
        device_id: str | None = None,
    ) -> StockMovementResponse:
        product = self.db.query(Product).filter(Product.id == payload.product_id).first()
        if not product:
            raise CaisseException(
                code="PRODUCT_NOT_FOUND",
                title="Produit introuvable",
                detail=f"Aucun produit trouvé avec l'ID {payload.product_id}.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        validate_movement_quantity(payload.quantity, payload.type)

        stock_item = self.repo.get_or_create_for_product(payload.product_id)
        current_qty = stock_item.quantity
        new_qty = calculate_quantity_after(current_qty, payload.type, payload.quantity)

        stock_item.quantity = new_qty
        stock_item.updated_at = datetime.now(timezone.utc)

        movement = StockMovement(
            stock_item_id=stock_item.id,
            product_id=product.id,
            user_id=user_id,
            type=payload.type,
            quantity=payload.quantity,
            quantity_after=new_qty,
            unit_cost_xof=payload.unit_cost_xof,
            reason=payload.reason,
            order_id=order_id,
        )
        self.repo.add_movement(movement)

        self.audit.log(
            action="STOCK_MOVEMENT",
            entity="STOCK",
            entity_id=stock_item.id,
            user_id=user_id,
            after={
                "product": product.name,
                "type": payload.type,
                "quantity": payload.quantity,
                "quantity_after": new_qty,
                "reason": payload.reason,
            },
            device_id=device_id,
        )
        self.db.commit()

        return StockMovementResponse(
            id=movement.id,
            product_id=product.id,
            product_name=product.name,
            type=movement.type,
            quantity=movement.quantity,
            quantity_after=movement.quantity_after,
            reason=movement.reason,
            created_at=movement.created_at.isoformat() if movement.created_at else datetime.now(timezone.utc).isoformat(),
        )

    def record_sale_out_for_order(self, order: Order, user_id: str) -> None:
        """Décrémente automatiquement le stock lors du règlement d'une commande."""
        for item in order.items:
            if item.removed_at is not None or not item.product_id:
                continue

            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            if product and product.track_stock:
                stock_item = self.repo.get_or_create_for_product(product.id)
                current_qty = stock_item.quantity
                new_qty = calculate_quantity_after(current_qty, StockMovementType.SALE_OUT, float(item.quantity))

                stock_item.quantity = new_qty
                stock_item.updated_at = datetime.now(timezone.utc)

                movement = StockMovement(
                    stock_item_id=stock_item.id,
                    product_id=product.id,
                    user_id=user_id,
                    type=StockMovementType.SALE_OUT,
                    quantity=float(item.quantity),
                    quantity_after=new_qty,
                    reason=f"Encaissement commande {order.order_number}",
                    order_id=order.id,
                )
                self.repo.add_movement(movement)

    def record_inventory_count(
        self,
        product_id: str,
        counted_quantity: float,
        user_id: str,
        reason: str,
        device_id: str | None = None,
    ) -> StockMovementResponse:
        req = StockMovementRequest(
            product_id=product_id,
            type="INVENTORY_COUNT",
            quantity=counted_quantity,
            reason=reason,
        )
        return self.record_movement(req, user_id=user_id, device_id=device_id)

    def list_stock_items(self) -> list[StockItemResponse]:
        items = self.repo.list_items()
        result = []
        for it in items:
            result.append(
                StockItemResponse(
                    id=it.id,
                    product_id=it.product_id,
                    product_name=it.product.name if it.product else "Article",
                    quantity=it.quantity,
                    unit=it.unit,
                    alert_threshold=it.alert_threshold,
                    is_low_stock=is_stock_low(it.quantity, it.alert_threshold),
                    updated_at=it.updated_at.isoformat() if it.updated_at else datetime.now(timezone.utc).isoformat(),
                )
            )
        return result

    def list_movements(self, product_id: str | None = None, limit: int = 50) -> list[StockMovementResponse]:
        movements = self.repo.list_movements(product_id=product_id, limit=limit)
        return [
            StockMovementResponse(
                id=m.id,
                product_id=m.product_id,
                product_name=m.product.name if m.product else "Article",
                type=m.type,
                quantity=m.quantity,
                quantity_after=m.quantity_after,
                reason=m.reason,
                created_at=m.created_at.isoformat() if m.created_at else datetime.now(timezone.utc).isoformat(),
            )
            for m in movements
        ]
