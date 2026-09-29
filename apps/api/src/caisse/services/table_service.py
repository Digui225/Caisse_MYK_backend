from sqlalchemy.orm import Session

from caisse.repositories.tables import TableRepository
from caisse.schemas.tables import TableResponse, TableBoardResponse, TableBoardItem


class TableService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TableRepository(db)

    def list_tables(self) -> list[TableResponse]:
        tables = self.repo.list_active_tables()
        return [
            TableResponse(
                id=t.id,
                label=t.label,
                zone=t.zone,
                seats=t.seats,
                sort_order=t.sort_order,
                is_active=t.is_active,
            )
            for t in tables
        ]

    def get_table_board(self) -> TableBoardResponse:
        board_data = self.repo.get_table_board_data()
        table_items = [TableBoardItem(**item) for item in board_data]
        open_orders_count = sum(1 for item in table_items if item.is_occupied)
        total_in_progress = sum(item.current_total_ttc_xof for item in table_items)

        return TableBoardResponse(
            tables=table_items,
            open_orders_count=open_orders_count,
            total_in_progress_xof=total_in_progress,
        )
