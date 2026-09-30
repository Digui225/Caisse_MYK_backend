"""Tests d'intégration sur un vrai PostgreSQL.

- `TEST_DATABASE_URL` défini → base existante (CI, conteneur jetable) ;
- sinon → testcontainers démarre un postgres:16-alpine.
Le schéma est créé par les migrations Alembic : les tests valident donc aussi les migrations.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from caisse.config import get_settings
from caisse.database import get_engine, get_sessionmaker
from caisse.domain.enums import UserRole
from caisse.models import Base, User
from caisse.services import user_service
from caisse.services.audit_service import RequestContext

ROOT = Path(__file__).resolve().parents[2]


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def migrated(database_url: str) -> Iterator[None]:
    os.environ["DATABASE_URL"] = database_url
    _clear_caches()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_tables(migrated: None) -> Iterator[None]:
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    from caisse.main import create_app

    with TestClient(create_app()) as c:
        yield c


CTX = RequestContext(device_id="test")


@pytest.fixture
def make_user(db: Session):  # type: ignore[no-untyped-def]
    def _make(pin: str, role: UserRole = UserRole.CAISSIER, name: str | None = None) -> User:
        return user_service.create_user(
            db, full_name=name or f"User {pin}", role=role, pin=pin, actor_id=None, ctx=CTX
        )

    return _make


def login(client: TestClient, pin: str, device_id: str = "poste-1") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"pin": pin, "device_id": device_id})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
