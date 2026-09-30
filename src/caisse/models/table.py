from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from caisse.models.base import Base, Timestamps, UUIDPk


class RestaurantTable(UUIDPk, Timestamps, Base):
    __tablename__ = "restaurant_tables"
    __table_args__ = (CheckConstraint("seats > 0", name="seats_positive"),)

    label: Mapped[str] = mapped_column(String(20), unique=True)
    zone: Mapped[str] = mapped_column(String(40), default="Salle")
    seats: Mapped[int] = mapped_column(default=4)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
