import uuid
from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class CaisseException(Exception):
    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        meta: dict[str, Any] | None = None,
    ):
        self.code = code
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.meta = meta or {}
        super().__init__(detail)


def problem_json_response(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    request_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    type_slug = code.lower().replace("_", "-")
    content = {
        "type": f"https://caisse.local/errors/{type_slug}",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "meta": meta or {},
        "request_id": request_id or str(uuid.uuid4()),
    }
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


async def caisse_exception_handler(request: Request, exc: CaisseException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return problem_json_response(
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        request_id=request_id,
        meta=exc.meta,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    fields_errors = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", []))
        fields_errors.append(
            {
                "field": loc,
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
        )

    return problem_json_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        title="Données de requête invalides",
        detail="Une ou plusieurs erreurs de validation ont été détectées.",
        request_id=request_id,
        meta={"fields": fields_errors},
    )
