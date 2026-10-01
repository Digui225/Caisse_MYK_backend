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
    provider: Optional[str] = None
    count: int
    total_amount_xof: int


class HourlySalesItem(BaseModel):
    hour: str
    total_sales_xof: int
    orders_count: int


class DashboardKpiResponse(BaseModel):
    business_date: str
    total_orders: int
    settled_orders: int
    open_orders: int = 0
    active_tables_count: int = 0
    total_tables_count: int = 14
    dine_in_orders_count: int = 0
    takeaway_orders_count: int = 0
    total_sales_ttc_xof: int
    total_sales_ht_xof: int
    total_sales_vat_xof: int
    average_basket_xof: int
    payments_by_method: list[PaymentMethodSplit]
    top_products: list[TopProductReport]
    hourly_sales: list[HourlySalesItem] = Field(default_factory=list)
    active_sessions_count: int
    low_stock_items_count: int
    fne_certified_count: int
    fne_pending_count: int
