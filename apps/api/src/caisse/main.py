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
import caisse.models.table
import caisse.models.user
from caisse.errors import (
    CaisseException,
    caisse_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from caisse.api.v1.router import api_v1_router
from caisse.schemas.common import HealthResponse, HealthReadyResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup : s'assurer que toutes les tables sont créées
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API Backend de Caisse Restaurant (Caisse MYK) - Point de Vente & Facturation Normalisée",
    openapi_url="/openapi.json",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

from fastapi.responses import HTMLResponse
from caisse.docs_html import get_offline_docs_html


@app.get("/docs", include_in_schema=False)
@app.get("/", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    return HTMLResponse(content=get_offline_docs_html(title=f"{settings.APP_NAME} - Documentation Interactive"))

# Middlewares
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


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
