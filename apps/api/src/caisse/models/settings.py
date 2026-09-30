from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from caisse.database import Base
from caisse.models.base import TimestampMixin, generate_uuid


class EstablishmentSetting(Base, TimestampMixin):
    __tablename__ = "establishment_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_name: Mapped[str] = mapped_column(String(100), default="Restaurant MYK", nullable=False)
    ncc: Mapped[str] = mapped_column(String(50), default="1234567A", nullable=False)
    rccm: Mapped[str] = mapped_column(String(50), default="CI-ABJ-2026-B-0000", nullable=False)
    address: Mapped[str] = mapped_column(String(255), default="Abidjan, Côte d'Ivoire", nullable=False)
    phone: Mapped[str] = mapped_column(String(50), default="+225 0102030405", nullable=False)
    default_vat_rate: Mapped[float] = mapped_column(Float, default=18.0, nullable=False)
    receipt_footer: Mapped[str] = mapped_column(String(255), default="Merci de votre visite et à très bientôt !", nullable=False)
    print_width: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    screen_lock_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
