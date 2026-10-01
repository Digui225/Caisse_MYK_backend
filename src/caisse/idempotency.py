"""`Idempotency-Key` générique (03-CONTRAT-API.md §3) : clé + hachage du corps + réponse rejouée.

Utilisé par les routes qui n'ont pas d'entité porteuse naturelle de la clé (ouverture/clôture
de session). Les paiements portent leur propre `idempotency_key` UNIQUE directement en colonne.
"""

import hashlib
import uuid
from typing import Annotated, Any

from fastapi import Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.errors import IdempotencyConflictError
from caisse.models.settings import IdempotencyRecord

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", max_length=64, description="Clé unique générée par le front"),
]


def hash_request(body: BaseModel) -> str:
    canonical = body.model_dump_json(exclude_none=False, by_alias=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def find_replay(
    db: Session, key: str, *, method: str, path: str, request_hash: str
) -> dict[str, Any] | None:
    """`None` si la clé est neuve. Sinon la réponse d'origine à rejouer telle quelle.

    Lève `IdempotencyConflictError` si la même clé porte un corps différent.
    """
    record = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key))
    if record is None:
        return None
    if record.method != method or record.path != path or record.request_hash != request_hash:
        raise IdempotencyConflictError(meta={"key": key})
    return record.response_body


def save(
    db: Session,
    key: str,
    *,
    method: str,
    path: str,
    request_hash: str,
    status: int,
    body: dict[str, Any],
    user_id: uuid.UUID | None,
) -> None:
    db.add(
        IdempotencyRecord(
            key=key,
            user_id=user_id,
            method=method,
            path=path,
            request_hash=request_hash,
            response_status=status,
            response_body=body,
        )
    )
