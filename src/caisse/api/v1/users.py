import uuid
from typing import Annotated

from fastapi import APIRouter, Path, status

from caisse.deps import Admin, Ctx, DbSession
from caisse.repositories import users as users_repo
from caisse.schemas.common import Page
from caisse.schemas.users import PinUpdate, UserCreate, UserDetail, UserUpdate
from caisse.services import user_service

router = APIRouter(prefix="/users", tags=["Utilisateurs"])

UserId = Annotated[uuid.UUID, Path(description="Identifiant de l'utilisateur")]


@router.get("", response_model=Page[UserDetail], summary="Lister les utilisateurs")
def list_users(_: Admin, db: DbSession) -> Page[UserDetail]:
    """Tous les utilisateurs, désactivés compris, triés par nom. Réservé à l'ADMIN."""
    return Page(items=[UserDetail.model_validate(u) for u in users_repo.list_all(db)])


@router.post(
    "",
    response_model=UserDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un utilisateur",
)
def create_user(body: UserCreate, admin: Admin, db: DbSession, ctx: Ctx) -> UserDetail:
    """Réservé à l'ADMIN. Le PIN sert d'identifiant à la connexion : il doit être unique.

    Erreurs : `409 PIN_ALREADY_USED`, `422 VALIDATION_ERROR` (PIN pas à 6 chiffres).
    """
    user = user_service.create_user(
        db, full_name=body.full_name, role=body.role, pin=body.pin, actor_id=admin.id, ctx=ctx
    )
    return UserDetail.model_validate(user)


@router.patch("/{user_id}", response_model=UserDetail, summary="Modifier un utilisateur")
def update_user(
    user_id: UserId, body: UserUpdate, admin: Admin, db: DbSession, ctx: Ctx
) -> UserDetail:
    """Mise à jour partielle : seuls les champs envoyés changent. Réservé à l'ADMIN.

    La désactivation coupe immédiatement les jetons de l'utilisateur.

    Erreurs : `404 NOT_FOUND`.
    """
    user = user_service.update_user(
        db,
        user_id,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        actor_id=admin.id,
        ctx=ctx,
    )
    return UserDetail.model_validate(user)


@router.post(
    "/{user_id}/pin",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Réinitialiser le PIN d'un utilisateur",
)
def set_pin(user_id: UserId, body: PinUpdate, admin: Admin, db: DbSession, ctx: Ctx) -> None:
    """Réservé à l'ADMIN. L'ancien PIN cesse aussitôt de fonctionner.

    Erreurs : `404 NOT_FOUND`, `409 PIN_ALREADY_USED`, `422 VALIDATION_ERROR`.
    """
    user_service.set_pin(db, user_id, body.pin, actor_id=admin.id, ctx=ctx)
