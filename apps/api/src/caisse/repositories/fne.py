from datetime import datetime
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from caisse.models.fne import FneDocument


class FneRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, fne_id: str) -> Optional[FneDocument]:
        return self.db.query(FneDocument).filter(FneDocument.id == fne_id).first()

    def get_by_order_id(self, order_id: str) -> Optional[FneDocument]:
        return self.db.query(FneDocument).filter(FneDocument.order_id == order_id).first()

    def get_next_sequence_for_date(self, date_str: str) -> int:
        pattern = f"%{date_str.replace('-', '')}%"
        count = (
            self.db.query(func.count(FneDocument.id))
            .filter(FneDocument.invoice_number.ilike(pattern))
            .scalar()
            or 0
        )
        return count + 1

    def list_documents(
        self,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FneDocument]:
        q = self.db.query(FneDocument)
        if status:
            q = q.filter(FneDocument.status == status)
        if start_date:
            q = q.filter(FneDocument.created_at >= start_date)
        if end_date:
            q = q.filter(FneDocument.created_at <= end_date)
        return q.order_by(FneDocument.created_at.desc()).limit(limit).offset(offset).all()

    def add(self, doc: FneDocument) -> FneDocument:
        self.db.add(doc)
        self.db.flush()
        return doc
