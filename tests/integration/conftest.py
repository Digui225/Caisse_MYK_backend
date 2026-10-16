"""Tests d'intégration sur un vrai PostgreSQL.

- `TEST_DATABASE_URL` défini → base existante (CI, conteneur jetable) ;
- sinon → testcontainers démarre un postgres:16-alpine.
Le schéma est créé par les migrations Alembic : les tests valident donc aussi les migrations.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from caisse.config import get_settings
from caisse.database import get_engine, get_sessionmaker
from caisse.deps import print_agent
from caisse.domain.enums import UserRole
from caisse.domain.ports import PrinterStatus, PrintResult
from caisse.models import Base, CashRegister, User
from caisse.services import user_service
from caisse.services.audit_service import RequestContext

ROOT = Path(__file__).resolve().parents[2]


class FakePrintAgent:
    """Double de test pour `Printer` (`domain/ports.py`) : jamais de réseau réel.

    `mode` pilote le comportement : `"ok"` (défaut, succès immédiat), `"offline"` (agent
    injoignable), `"paper_out"` (agent en ligne, imprimante en panne)."""

    def __init__(self, *, mode: str = "ok") -> None:
        self.mode = mode
        self.printed: list[str] = []
        self.drawer_opened_count = 0

    def _maybe_raise(self, path: str) -> None:
        if self.mode == "offline":
            raise httpx.ConnectError("agent hors ligne")
        if self.mode == "paper_out":
            request = httpx.Request("POST", f"http://print-agent{path}")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("imprimante en panne", request=request, response=response)

    def status(self) -> PrinterStatus:
        if self.mode == "offline":
            return PrinterStatus(agent_online=False, printer_online=False, paper=None, width=None)
        online = self.mode != "paper_out"
        return PrinterStatus(agent_online=True, printer_online=online, paper="ok", width=48)

    def print(
        self, content: str, *, qr: str | None, open_drawer: bool, cut: bool = True
    ) -> PrintResult:
        self._maybe_raise("/print")
        self.printed.append(content)
        if open_drawer:
            self.drawer_opened_count += 1
        return PrintResult(printed=True, drawer_opened=open_drawer)

    def open_drawer(self) -> None:
        self._maybe_raise("/open-drawer")
        self.drawer_opened_count += 1

    def test_print(self) -> None:
        self._maybe_raise("/test-print")


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
def fake_print_agent() -> FakePrintAgent:
    """Succès immédiat par défaut, pour que les tests qui ne portent pas sur l'impression
    ne dépendent pas d'un agent réel (mirror de `FNE_PROVIDER=manual` pour la FNE)."""
    return FakePrintAgent()


@pytest.fixture
def client(fake_print_agent: FakePrintAgent) -> Iterator[TestClient]:
    from caisse.main import create_app

    app = create_app()
    app.dependency_overrides[print_agent] = lambda: fake_print_agent
    with TestClient(app) as c:
        yield c


CTX = RequestContext(device_id="test")


@pytest.fixture
def make_user(db: Session):  # type: ignore[no-untyped-def]
    def _make(pin: str, role: UserRole = UserRole.CAISSIER, name: str | None = None) -> User:
        return user_service.create_user(
            db, full_name=name or f"User {pin}", role=role, pin=pin, actor_id=None, ctx=CTX
        )

    return _make


@pytest.fixture
def make_cash_register(db: Session):  # type: ignore[no-untyped-def]
    def _make(name: str = "Caisse 1") -> CashRegister:
        register = CashRegister(name=name, printer_config={})
        db.add(register)
        db.commit()
        return register

    return _make


def login(client: TestClient, pin: str, device_id: str = "poste-1") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"pin": pin, "device_id": device_id})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
