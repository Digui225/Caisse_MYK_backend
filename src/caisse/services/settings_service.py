"""Paramètres de l'établissement (03-CONTRAT-API §4.11) et caisses.

Les paramètres restent stockés par clé (table `settings`, 01-BACKEND §4.5) ; l'API les
présente à plat, avec des noms stables pour le front. Une clé jamais créée prend sa valeur
par défaut (`seeds/defaults.py`).
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from caisse.errors import (
    CashRegisterHasOpenSessionError,
    CashRegisterNameExistsError,
    NotFoundError,
)
from caisse.models.cash_session import CashRegister
from caisse.models.settings import AppSetting
from caisse.models.user import User
from caisse.repositories import sessions as sessions_repo
from caisse.repositories import settings as settings_repo
from caisse.schemas.settings import (
    CashRegisterCreate,
    CashRegisterOut,
    CashRegisterUpdate,
    OpenSessionInfo,
    SettingsOut,
    SettingsUpdate,
    WalkInClient,
)
from caisse.seeds.defaults import DEFAULT_SETTINGS
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext

# champ de l'API → (clé `settings`, sous-clé éventuelle)
_HEADER_FIELDS = {
    "restaurant_name": "name",
    "address": "address",
    "phone": "phone",
    "ncc": "ncc",
    "rccm": "rccm",
}
_SCALAR_KEYS = {
    "receipt_footer": "receipt.footer",
    "default_vat_rate": "vat.default_rate",
    "cash_rounding_xof": "cash.rounding_xof",
    "cash_denominations_xof": "cash.denominations_xof",
    "payment_methods": "payments.methods",
    "screen_lock_timeout_seconds": "ui.lock_after_seconds",
    "fne_point_of_sale": "fne.point_of_sale",
    "fne_establishment": "fne.establishment",
    "fne_walk_in_client": "fne.walk_in_client",
}


def _value(db: Session, key: str) -> Any:
    return settings_repo.get_value(db, key, DEFAULT_SETTINGS.get(key))


def get_settings(db: Session) -> SettingsOut:
    header: dict[str, Any] = {
        **DEFAULT_SETTINGS["receipt.header"],
        **(_value(db, "receipt.header") or {}),
    }
    walk_in: dict[str, Any] = _value(db, "fne.walk_in_client") or {}
    return SettingsOut(
        restaurant_name=str(header.get("name") or ""),
        address=str(header.get("address") or ""),
        phone=str(header.get("phone") or ""),
        ncc=str(header.get("ncc") or ""),
        rccm=str(header.get("rccm") or ""),
        receipt_footer=str(_value(db, "receipt.footer") or ""),
        default_vat_rate=float(settings_repo.default_vat_rate(db)),
        cash_rounding_xof=int(_value(db, "cash.rounding_xof")),
        cash_denominations_xof=list(_value(db, "cash.denominations_xof")),
        payment_methods=list(_value(db, "payments.methods")),
        screen_lock_timeout_seconds=int(_value(db, "ui.lock_after_seconds")),
        fne_point_of_sale=str(_value(db, "fne.point_of_sale") or ""),
        fne_establishment=str(_value(db, "fne.establishment") or ""),
        fne_walk_in_client=WalkInClient(
            company_name=str(walk_in.get("company_name") or ""),
            phone=str(walk_in.get("phone") or ""),
            email=str(walk_in.get("email") or ""),
        ),
    )


def _store(db: Session, key: str, value: Any, actor_id: uuid.UUID) -> None:
    setting = db.get(AppSetting, key)
    if setting is None:
        db.add(AppSetting(key=key, value=value, updated_by=actor_id))
    else:
        setting.value = value
        setting.updated_by = actor_id


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, list):
        return [str(v) if not isinstance(v, int) else v for v in value]
    return value


def update_settings(
    db: Session, body: SettingsUpdate, *, actor_id: uuid.UUID, ctx: RequestContext
) -> SettingsOut:
    """Seuls les champs envoyés changent ; une ligne d'audit par appel, avec l'avant/après
    des champs modifiés."""
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    before = get_settings(db).model_dump(mode="json")
    header_changes = {_HEADER_FIELDS[k]: v for k, v in changes.items() if k in _HEADER_FIELDS}
    if header_changes:
        header = {**DEFAULT_SETTINGS["receipt.header"], **(_value(db, "receipt.header") or {})}
        _store(db, "receipt.header", {**header, **header_changes}, actor_id)
    for field, key in _SCALAR_KEYS.items():
        if field in changes:
            _store(db, key, _jsonable(changes[field]), actor_id)
    db.flush()
    after = get_settings(db)
    after_json = after.model_dump(mode="json")
    audit_service.log(
        db,
        "settings.update",
        ctx=ctx,
        user_id=actor_id,
        entity="settings",
        before={k: before[k] for k in changes},
        after={k: after_json[k] for k in changes},
    )
    db.commit()
    return after


# --- Caisses -----------------------------------------------------------------------------


def register_out(db: Session, register: CashRegister) -> CashRegisterOut:
    session = sessions_repo.get_open_for_register(db, register.id)
    open_session = None
    if session is not None:
        opener = db.get(User, session.opened_by_user_id)
        open_session = OpenSessionInfo(
            id=session.id,
            business_date=session.business_date,
            opened_by=opener.full_name if opener is not None else "",
            opened_at=session.opened_at,
        )
    return CashRegisterOut(
        id=register.id, name=register.name, is_active=register.is_active, open_session=open_session
    )


def _name_taken(db: Session, name: str, exclude: uuid.UUID | None = None) -> None:
    for register in sessions_repo.list_registers(db, is_active=None):
        if register.name.lower() == name.lower() and register.id != exclude:
            raise CashRegisterNameExistsError(meta={"cash_register_id": str(register.id)})


def create_register(
    db: Session, body: CashRegisterCreate, *, actor_id: uuid.UUID, ctx: RequestContext
) -> CashRegister:
    _name_taken(db, body.name)
    register = CashRegister(name=body.name, printer_config={}, is_active=True)
    db.add(register)
    db.flush()
    audit_service.log(
        db,
        "cash_register.create",
        ctx=ctx,
        user_id=actor_id,
        entity="cash_register",
        entity_id=register.id,
        after={"name": body.name},
    )
    db.commit()
    return register


def update_register(
    db: Session,
    register_id: uuid.UUID,
    body: CashRegisterUpdate,
    *,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> CashRegister:
    register = db.get(CashRegister, register_id)
    if register is None:
        raise NotFoundError(meta={"cash_register_id": str(register_id)})
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in changes:
        _name_taken(db, changes["name"], exclude=register.id)
    if changes.get("is_active") is False and register.is_active:
        session = sessions_repo.get_open_for_register(db, register.id)
        if session is not None:
            raise CashRegisterHasOpenSessionError(
                meta={"cash_register_id": str(register.id), "session_id": str(session.id)}
            )
    before = {key: getattr(register, key) for key in changes}
    for key, value in changes.items():
        setattr(register, key, value)
    audit_service.log(
        db,
        "cash_register.update",
        ctx=ctx,
        user_id=actor_id,
        entity="cash_register",
        entity_id=register.id,
        before=before,
        after=changes,
    )
    db.commit()
    return register
