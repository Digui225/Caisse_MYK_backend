import re
import uuid

from sqlalchemy.orm import Session

from caisse.config import get_settings
from caisse.domain.enums import UserRole
from caisse.errors import NotFoundError, PinAlreadyUsedError, ValidationError
from caisse.models.user import User
from caisse.repositories import users as users_repo
from caisse.security import hash_pin
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext


def validate_pin(pin: str) -> None:
    length = get_settings().pin_length
    if not re.fullmatch(rf"\d{{{length}}}", pin):
        raise ValidationError(
            f"Le PIN doit comporter exactement {length} chiffres",
            meta={"fields": [{"loc": ["body", "pin"], "type": "pin_format"}]},
        )


def _ensure_pin_unique(db: Session, pin: str, exclude_id: uuid.UUID | None = None) -> None:
    if users_repo.find_by_pin(db, pin, exclude_id=exclude_id) is not None:
        raise PinAlreadyUsedError()


def create_user(
    db: Session,
    *,
    full_name: str,
    role: UserRole,
    pin: str,
    actor_id: uuid.UUID | None,
    ctx: RequestContext,
) -> User:
    validate_pin(pin)
    _ensure_pin_unique(db, pin)
    user = User(full_name=full_name.strip(), role=role, pin_hash=hash_pin(pin))
    db.add(user)
    db.flush()
    audit_service.log(
        db,
        "user.create",
        ctx=ctx,
        user_id=actor_id,
        entity="user",
        entity_id=user.id,
        after={"full_name": user.full_name, "role": role},
    )
    db.commit()
    return user


def update_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    full_name: str | None,
    role: UserRole | None,
    is_active: bool | None,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> User:
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError(meta={"user_id": str(user_id)})
    before = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active}
    if full_name is not None:
        user.full_name = full_name.strip()
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    after = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active}
    audit_service.log(
        db,
        "user.update",
        ctx=ctx,
        user_id=actor_id,
        entity="user",
        entity_id=user.id,
        before=before,
        after=after,
    )
    db.commit()
    return user


def set_pin(
    db: Session, user_id: uuid.UUID, pin: str, *, actor_id: uuid.UUID | None, ctx: RequestContext
) -> User:
    validate_pin(pin)
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError(meta={"user_id": str(user_id)})
    _ensure_pin_unique(db, pin, exclude_id=user.id)
    user.pin_hash = hash_pin(pin)
    user.failed_attempts = 0
    user.locked_until = None
    audit_service.log(
        db, "user.pin_reset", ctx=ctx, user_id=actor_id, entity="user", entity_id=user.id
    )
    db.commit()
    return user
