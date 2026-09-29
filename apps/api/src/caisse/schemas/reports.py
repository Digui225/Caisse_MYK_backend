from caisse.schemas.common import BaseSchema


class DashboardKPIs(BaseSchema):
    business_date: str
    total_sales_ttc_xof: int
    orders_count: int
    average_ticket_xof: int
    open_orders_count: int
    sales_by_method: dict[str, int]
    top_products: list[dict[str, str | int]]
    low_stock_alerts_count: int
    fne_queued_count: int
