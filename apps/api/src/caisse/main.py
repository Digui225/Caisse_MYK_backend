import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from caisse.config import get_settings
from caisse.database import Base, engine
import caisse.models.audit
import caisse.models.cash_session
import caisse.models.catalog
import caisse.models.customer
import caisse.models.fne
import caisse.models.idempotency
import caisse.models.order
import caisse.models.outbox
import caisse.models.payment
import caisse.models.stock
import caisse.models.settings
import caisse.models.table
import caisse.models.user
from caisse.errors import (
    CaisseException,
    caisse_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
    problem_json_response,
)
from caisse.api.v1.router import api_v1_router
from caisse.schemas.common import HealthResponse, HealthReadyResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup : s'assurer que toutes les tables sont créées
    if settings.APP_ENV != "test":
        Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from caisse.docs_html import get_offline_docs_html

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API Backend de Caisse Restaurant (Caisse MYK) - Point de Vente & Facturation Normalisée",
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
@app.get("/", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    if not settings.docs_enabled:
        raise CaisseException(
            code="DOCS_DISABLED",
            title="Documentation désactivée",
            detail="La documentation interactive est désactivée en environnement de production.",
            status_code=404,
        )
    return HTMLResponse(content=get_offline_docs_html(title=f"{settings.APP_NAME} - Documentation Interactive"))


# Middlewares
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):  # type: ignore
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):  # type: ignore
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
            if length > settings.MAX_REQUEST_BODY_SIZE:
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return problem_json_response(
                    status_code=413,
                    code="PAYLOAD_TOO_LARGE",
                    title="Corps de requête trop volumineux",
                    detail=f"La taille de la requête ({length} octets) dépasse la limite autorisée de {settings.MAX_REQUEST_BODY_SIZE} octets.",
                    request_id=request_id,
                    meta={"max_bytes": settings.MAX_REQUEST_BODY_SIZE, "received_bytes": length},
                )
        except ValueError:
            pass
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# TrustedHostMiddleware (vérifie que l'en-tête Host correspond aux domaines autorisés)
if settings.ALLOWED_HOSTS and "*" not in settings.ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

# CORSMiddleware ajouté en dernier pour être le wrapper le plus externe (capture toutes les réponses y compris erreurs 500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Enregistrement des gestionnaires d'erreurs RFC 7807 (problem+json)
app.add_exception_handler(CaisseException, caisse_exception_handler)  # type: ignore
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore

# Routes système / Health
@app.get("/health", response_model=HealthResponse, tags=["Système"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
    )


@app.get("/health/ready", response_model=HealthReadyResponse, tags=["Système"])
async def health_ready() -> HealthReadyResponse:
    return HealthReadyResponse(
        status="ok",
        database=True,
        print_agent=True,
        fne_queue_length=0,
    )


# Inclusion de l'API v1
app.include_router(api_v1_router)
