import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from caisse.domain.enums import UserRole
from caisse.models.base import Base, CreatedAt, Timestamps, UUIDPk, enum_column


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(120))
    pin_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"))
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceLoginThrottle(Base):
    """Temporisation des essais de PIN, par poste.

    La connexion se fait par PIN seul (pas d'identifiant) : un échec ne peut pas être imputé
    à un utilisateur, on bloque donc le poste qui saisit.
    """

    __tablename__ = "device_login_throttles"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefreshToken(CreatedAt, Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    device_id: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[uuid.UUID | None]


class OverrideGrant(CreatedAt, Base):
    """Élévation ponctuelle (PIN responsable) : jeton à usage unique, 60 s."""

    __tablename__ = "override_grants"

    jti: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
