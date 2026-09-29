from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from caisse.models.base import Base, TimestampMixin, generate_uuid


class FneDocument(Base, TimestampMixin):
    __tablename__ = "fne_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True, index=True)

    document_type = Column(String(20), default="FNE", nullable=False)  # FNE, AVOIR
    status = Column(String(20), default="QUEUED", nullable=False, index=True)  # QUEUED, SUBMITTED, CERTIFIED, FAILED, MANUAL_EXPORTED
    
    invoice_number = Column(String(100), nullable=True, unique=True, index=True)  # FNE-2104598B-20260928-00042
    qr_url = Column(String(500), nullable=True)
    fne_token = Column(String(64), nullable=True)  # Hash SHA-256 signature
    
    # Payload DGI strictly frozen JSON
    payload = Column(JSON, nullable=False)
    response_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    retry_count = Column(Integer, default=0, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    certified_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", backref="fne_document")
    customer = relationship("Customer", backref="fne_documents")
