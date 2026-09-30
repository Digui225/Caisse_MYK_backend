import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from caisse.models.audit import AuditLog


@dataclass(frozen=True, slots=True)
class RequestContext:
    device_id: str | None = None
    ip: str | None = None


def log(
    db: Session,
    action: str,
    *,
    ctx: RequestContext,
    user_id: uuid.UUID | None = None,
    acting_as_user_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: uuid.UUID | str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    """Ajoute une entrée d'audit à la transaction en cours (le commit reste au service)."""
    db.add(
        AuditLog(
            user_id=user_id,
            acting_as_user_id=acting_as_user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            reason=reason,
            ip=ctx.ip,
            device_id=ctx.device_id,
        )
    )
