"""Exceptions métier → application/problem+json (RFC 9457). Voir 03-CONTRAT-API.md §2."""

import re
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()

PROBLEM_JSON = "application/problem+json"
ERROR_TYPE_BASE = "https://caisse.local/errors/"


class DomainError(Exception):
    """Erreur métier → 4xx avec un `code` contractuel stable."""

    status: int = 400
    code: str = "DOMAIN_ERROR"
    title: str = "Erreur métier"

    def __init__(self, detail: str | None = None, meta: dict[str, Any] | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.meta = meta or {}


class InfrastructureError(Exception):
    """Panne technique → 5xx, message générique, log complet."""

    status: int = 503
    code: str = "INFRASTRUCTURE_ERROR"


def _error(name: str, status: int, title: str, code: str | None = None) -> type[DomainError]:
    attrs = {"status": status, "code": code or _snake_upper(name), "title": title}
    return type(name, (DomainError,), attrs)


def _snake_upper(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name.removesuffix("Error")).upper()


# Catalogue MVP (03-CONTRAT-API.md §2)
InvalidCredentialsError = _error("InvalidCredentialsError", 401, "Code PIN invalide")
AccountLockedError = _error("AccountLockedError", 423, "Trop d'essais, poste temporairement bloqué")
TokenExpiredError = _error("TokenExpiredError", 401, "Jeton expiré ou invalide")
InsufficientPrivilegeError = _error("InsufficientPrivilegeError", 403, "Rôle insuffisant")
OverrideRequiredError = _error("OverrideRequiredError", 403, "Autorisation responsable requise")
NoOpenSessionError = _error("NoOpenSessionError", 409, "Aucune session de caisse ouverte")
SessionAlreadyOpenError = _error("SessionAlreadyOpenError", 409, "Une session est déjà ouverte")
SessionAlreadyClosedError = _error("SessionAlreadyClosedError", 409, "Session déjà clôturée")
SessionNotClosedError = _error(
    "SessionNotClosedError", 409, "Rapport Z indisponible avant la clôture"
)
SessionHasOpenOrdersError = _error("SessionHasOpenOrdersError", 409, "Commandes non soldées")
BusinessDateMismatchError = _error(
    "BusinessDateMismatchError", 409, "Journée comptable à confirmer"
)
TableAlreadyOccupiedError = _error("TableAlreadyOccupiedError", 409, "Table déjà occupée")
OrderNotEditableError = _error("OrderNotEditableError", 409, "Commande non modifiable")
PaymentExceedsDueError = _error("PaymentExceedsDueError", 422, "Montant supérieur au reste dû")
IdempotencyConflictError = _error("IdempotencyConflictError", 409, "Clé d'idempotence réutilisée")
NotFoundError = _error("NotFoundError", 404, "Ressource introuvable")
PinAlreadyUsedError = _error("PinAlreadyUsedError", 409, "Ce code PIN est déjà attribué")
ValidationError = _error("ValidationError", 422, "Données invalides", "VALIDATION_ERROR")


def _problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    body = {
        "type": ERROR_TYPE_BASE + code.lower().replace("_", "-"),
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
        "meta": meta or {},
        "request_id": getattr(request.state, "request_id", None),
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            request,
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            meta=exc.meta,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return _problem(
            request,
            status=422,
            code="VALIDATION_ERROR",
            title="Données invalides",
            detail="Requête invalide",
            meta={"fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        return _problem(
            request,
            status=exc.status_code,
            code=code,
            title=str(exc.detail),
            detail=str(exc.detail),
        )

    @app.exception_handler(InfrastructureError)
    async def _infra(request: Request, exc: InfrastructureError) -> JSONResponse:
        log.error("infrastructure_error", code=exc.code, error=str(exc))
        return _problem(
            request,
            status=exc.status,
            code=exc.code,
            title="Service momentanément indisponible",
            detail="Réessayez",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Aucune stack trace ne sort de l'API : elle va dans les logs uniquement.
        log.exception("unhandled_error")
        return _problem(
            request,
            status=500,
            code="INTERNAL_ERROR",
            title="Erreur interne",
            detail="Erreur interne",
        )
