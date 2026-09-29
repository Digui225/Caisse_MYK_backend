from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class TopProductReport(BaseModel):
    product_id: str
    product_name: str
    category_name: Optional[str] = None
    quantity_sold: float
    total_revenue_xof: int


class PaymentMethodSplit(BaseModel):
    method: str
    count: int
    total_amount_xof: int


class DashboardKpiResponse(BaseModel):
    business_date: str
    total_orders: int
    settled_orders: int
    total_sales_ttc_xof: int
    total_sales_ht_xof: int
    total_sales_vat_xof: int
    average_basket_xof: int
    payments_by_method: list[PaymentMethodSplit]
    top_products: list[TopProductReport]
    active_sessions_count: int
    low_stock_items_count: int
    fne_certified_count: int
    fne_pending_count: int
