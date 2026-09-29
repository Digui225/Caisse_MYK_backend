from sqlalchemy.orm import Session
from caisse.models.print_job import PrintJob
from caisse.repositories.base import BaseRepository


class PrintJobRepository(BaseRepository[PrintJob]):
    def __init__(self, db: Session):
        super().__init__(db, PrintJob)

    def list_queued(self, limit: int = 10) -> list[PrintJob]:
        return (
            self.db.query(PrintJob)
            .filter(PrintJob.status == "QUEUED")
            .order_by(PrintJob.created_at.asc())
            .limit(limit)
            .all()
        )

    def list_by_order_id(self, order_id: str) -> list[PrintJob]:
        return (
            self.db.query(PrintJob)
            .filter(PrintJob.order_id == order_id)
            .order_by(PrintJob.created_at.desc())
            .all()
        )
