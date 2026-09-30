"""Dépendances FastAPI communes : utilisateur courant, RBAC, contexte de requête."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.domain.enums import UserRole, role_at_least
from caisse.errors import InsufficientPrivilegeError, TokenExpiredError
from caisse.models.user import User
from caisse.services import auth_service
from caisse.services.audit_service import RequestContext

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def request_context(
    request: Request,
    x_device_id: Annotated[
        str | None,
        Header(max_length=64, description="Identifiant du poste (blocage des PIN, audit)"),
    ] = None,
) -> RequestContext:
    return RequestContext(device_id=x_device_id, ip=request.client.host if request.client else None)


Ctx = Annotated[RequestContext, Depends(request_context)]


def current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise TokenExpiredError("Authentification requise")
    return auth_service.authenticate_access(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(minimum: UserRole) -> Callable[[User], User]:
    """Rôle minimal requis (CAISSIER < RESPONSABLE < ADMIN)."""

    def _check(user: CurrentUser) -> User:
        if not role_at_least(user.role, minimum):
            raise InsufficientPrivilegeError(meta={"required_role": minimum})
        return user

    return _check


Responsable = Annotated[User, Depends(require_role(UserRole.RESPONSABLE))]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
