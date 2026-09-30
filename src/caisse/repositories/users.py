import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.models.user import User
from caisse.security import verify_pin


def get(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_all(db: Session, *, active_only: bool = False) -> list[User]:
    stmt = select(User).order_by(User.full_name)
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return list(db.scalars(stmt))


def find_by_pin(db: Session, pin: str, *, exclude_id: uuid.UUID | None = None) -> User | None:
    """Connexion par PIN seul : les hachés Argon2 sont salés, on vérifie donc chaque compte
    actif (quelques dizaines au plus). L'unicité du PIN est imposée à la création."""
    for user in list_all(db, active_only=True):
        if user.id != exclude_id and verify_pin(user.pin_hash, pin):
            return user
    return None


def find_by_name(db: Session, full_name: str) -> list[User]:
    return list(db.scalars(select(User).where(User.full_name.ilike(full_name))))
