from pydantic import BaseModel
from caisse.schemas.common import BaseSchema


class TableResponse(BaseSchema):
    id: str
    label: str
    zone: str = "Salle"
    seats: int = 4
    sort_order: int = 0
    is_active: bool = True


class TableBoardItem(BaseSchema):
    id: str
    label: str
    zone: str
    seats: int
    is_occupied: bool
    current_order_id: str | None = None
    current_order_number: str | None = None
    current_total_ttc_xof: int = 0
    guests_count: int | None = None
    opened_at: str | None = None
    server_name: str | None = None
    items_count: int | None = None
    service_step: str | None = None


class TableBoardResponse(BaseSchema):
    tables: list[TableBoardItem]
    open_orders_count: int
    total_in_progress_xof: int
