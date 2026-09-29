from typing import Literal
from pydantic import BaseModel, Field
from caisse.schemas.common import BaseSchema


class StockItemResponse(BaseSchema):
    id: str
    product_id: str
    product_name: str
    quantity: float
    unit: str = "bouteille"
    alert_threshold: float = 5.0
    is_low_stock: bool = False
    updated_at: str


class StockMovementRequest(BaseModel):
    product_id: str
    type: Literal["PURCHASE_IN", "SALE_OUT", "RETURN_IN", "LOSS_OUT", "ADJUSTMENT", "INVENTORY_COUNT"]
    quantity: float
    unit_cost_xof: int | None = None
    reason: str = Field(..., min_length=3)


class StockMovementResponse(BaseSchema):
    id: str
    product_id: str
    product_name: str
    type: str
    quantity: float
    quantity_after: float
    reason: str
    created_at: str
