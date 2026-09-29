from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from caisse.models.base import Base, TimestampMixin, generate_uuid


class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(String(50), nullable=False, index=True)  # e.g. FNE_CERTIFICATION, PRINT_JOB, AUDIT_FORWARD
    aggregate_type = Column(String(50), nullable=False)  # e.g. Order, Payment, FneDocument
    aggregate_id = Column(String(36), nullable=False, index=True)
    
    payload = Column(JSON, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
