from sqlalchemy import Boolean, Column, String
from caisse.models.base import Base, TimestampMixin, generate_uuid


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, index=True)
    ncc = Column(String(50), nullable=True, index=True)  # Numéro de Compte Contribuable DGI
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
