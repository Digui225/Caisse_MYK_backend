import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from caisse.deps import Admin, Ctx, CurrentUser, DbSession
from caisse.repositories import sessions as sessions_repo
from caisse.schemas.common import Page
from caisse.schemas.settings import (
    CashRegisterCreate,
    CashRegisterOut,
    CashRegisterUpdate,
    SettingsOut,
    SettingsUpdate,
)
from caisse.services import settings_service

router = APIRouter(tags=["Administration"])

RegisterId = Annotated[uuid.UUID, Path(description="Identifiant de la caisse")]


@router.get("/settings", response_model=SettingsOut, summary="Paramètres de l'établissement")
def get_settings(_: CurrentUser, db: DbSession) -> SettingsOut:
    """Lisibles par tout utilisateur connecté (le front lit par exemple le délai de
    verrouillage de l'écran et les moyens de paiement)."""
    return settings_service.get_settings(db)


@router.put("/settings", response_model=SettingsOut, summary="Modifier les paramètres")
def update_settings(body: SettingsUpdate, admin: Admin, db: DbSession, ctx: Ctx) -> SettingsOut:
    """Réservé à l'ADMIN. Seuls les champs envoyés changent ; réponse : tous les paramètres.

    `default_vat_rate` ne vaut que pour les produits créés ensuite (pour tous les produits :
    `python -m caisse.cli set-vat-rate <taux> --all-products`). Un moyen de paiement `OTHER`
    n'a pas de code FNE : une FNE payée ainsi sera refusée.

    Erreurs : `422 VALIDATION_ERROR` (NCC mal formé, coupures en double…).
    """
    return settings_service.update_settings(db, body, actor_id=admin.id, ctx=ctx)


@router.get("/cash-registers", response_model=Page[CashRegisterOut], summary="Lister les caisses")
def list_registers(
    _: CurrentUser,
    db: DbSession,
    is_active: Annotated[
        bool | None, Query(description="true (défaut) : en service ; false : désactivées")
    ] = True,
) -> Page[CashRegisterOut]:
    """Caisses avec leur session en cours (`open_session`). L'`id` d'une caisse sert à
    ouvrir une session (`POST /cash-sessions`)."""
    registers = sessions_repo.list_registers(db, is_active=is_active)
    return Page(items=[settings_service.register_out(db, r) for r in registers])


@router.post(
    "/cash-registers",
    response_model=CashRegisterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une caisse",
)
def create_register(
    body: CashRegisterCreate, admin: Admin, db: DbSession, ctx: Ctx
) -> CashRegisterOut:
    """Réservé à l'ADMIN. Erreurs : `409 CASH_REGISTER_NAME_EXISTS` (`meta.cash_register_id`)."""
    register = settings_service.create_register(db, body, actor_id=admin.id, ctx=ctx)
    return settings_service.register_out(db, register)


@router.patch(
    "/cash-registers/{register_id}", response_model=CashRegisterOut, summary="Modifier une caisse"
)
def update_register(
    register_id: RegisterId, body: CashRegisterUpdate, admin: Admin, db: DbSession, ctx: Ctx
) -> CashRegisterOut:
    """Réservé à l'ADMIN. `is_active: false` retire la caisse du service (suppression
    logique) ; refusé tant qu'une session y est ouverte.

    Erreurs : `404 NOT_FOUND`, `409 CASH_REGISTER_NAME_EXISTS`,
    `409 CASH_REGISTER_HAS_OPEN_SESSION` (`meta.session_id`).
    """
    register = settings_service.update_register(db, register_id, body, actor_id=admin.id, ctx=ctx)
    return settings_service.register_out(db, register)
