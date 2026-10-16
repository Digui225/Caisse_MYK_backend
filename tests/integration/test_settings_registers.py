import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from caisse.domain.enums import UserRole
from caisse.models import AuditLog
from caisse.seeds.defaults import ensure_defaults

from .conftest import auth, login

pytestmark = pytest.mark.integration


@pytest.fixture
def users(client: TestClient, db: Session, make_user) -> dict[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    ensure_defaults(db)
    db.commit()
    make_user("111111", UserRole.CAISSIER, name="Awa")
    make_user("333333", UserRole.ADMIN)
    return {
        "cashier": auth(login(client, "111111")["access_token"]),  # type: ignore[arg-type]
        "admin": auth(login(client, "333333")["access_token"]),  # type: ignore[arg-type]
    }


def test_settings(client: TestClient, users: dict[str, dict[str, str]], db: Session) -> None:
    cashier, admin = users["cashier"], users["admin"]
    current = client.get("/api/v1/settings", headers=cashier).json()
    assert current["payment_methods"] == ["CASH", "MOBILE_MONEY", "CARD", "BANK_TRANSFER", "CREDIT"]
    assert (current["default_vat_rate"], current["screen_lock_timeout_seconds"]) == (0.0, 120)

    body = {"restaurant_name": "RESTAURANT CHEZ SYLLA PLUS", "phone": "0700000000"}
    assert client.put("/api/v1/settings", headers=cashier, json=body).status_code == 403
    updated = client.put(
        "/api/v1/settings",
        headers=admin,
        json={
            **body,
            "ncc": "95 06466a",
            "cash_denominations_xof": [500, 10000, 1000],
            "payment_methods": ["CASH", "MOBILE_MONEY"],
            "default_vat_rate": 18,
        },
    )
    assert updated.status_code == 200, updated.text
    out = updated.json()
    assert (out["restaurant_name"], out["ncc"], out["address"]) == (
        "RESTAURANT CHEZ SYLLA PLUS",
        "9506466A",
        "[Adresse]",  # inchangée
    )
    assert out["cash_denominations_xof"] == [10000, 1000, 500]
    assert out["default_vat_rate"] == 18.0
    # le reste de l'application lit les mêmes clés
    assert [m["method"] for m in client.get("/api/v1/payment-methods", headers=cashier).json()] == [
        "CASH",
        "MOBILE_MONEY",
    ]

    for bad in ({"ncc": "123"}, {"payment_methods": ["CASH", "CASH"]}, {"payment_methods": []}):
        assert client.put("/api/v1/settings", headers=admin, json=bad).status_code == 422
    audit = db.query(AuditLog).filter(AuditLog.action == "settings.update").one()
    assert audit.before["phone"] == "[Téléphone]" and audit.after["phone"] == "0700000000"  # type: ignore[index]


def test_cash_registers(client: TestClient, users: dict[str, dict[str, str]]) -> None:
    cashier, admin = users["cashier"], users["admin"]
    registers = client.get("/api/v1/cash-registers", headers=cashier).json()["items"]
    assert [(r["name"], r["open_session"]) for r in registers] == [("Caisse 1", None)]
    main_id = registers[0]["id"]

    bar = client.post("/api/v1/cash-registers", headers=admin, json={"name": "Caisse Bar"})
    assert bar.status_code == 201
    dup = client.post("/api/v1/cash-registers", headers=admin, json={"name": "caisse bar"})
    assert (dup.status_code, dup.json()["code"]) == (409, "CASH_REGISTER_NAME_EXISTS")
    assert (
        client.post("/api/v1/cash-registers", headers=cashier, json={"name": "X"}).status_code
        == 403
    )

    opened = client.post(
        "/api/v1/cash-sessions",
        headers={**cashier, "Idempotency-Key": "open"},
        json={"cash_register_id": main_id, "opening_float_xof": 0},
    ).json()
    main = client.get("/api/v1/cash-registers", headers=cashier).json()["items"][0]
    assert (main["open_session"]["id"], main["open_session"]["opened_by"]) == (opened["id"], "Awa")

    busy = client.patch(
        f"/api/v1/cash-registers/{main_id}", headers=admin, json={"is_active": False}
    )
    assert (busy.status_code, busy.json()["code"]) == (409, "CASH_REGISTER_HAS_OPEN_SESSION")

    bar_url = f"/api/v1/cash-registers/{bar.json()['id']}"
    off = client.patch(bar_url, headers=admin, json={"is_active": False, "name": "Bar"})
    assert (off.json()["is_active"], off.json()["name"]) == (False, "Bar")
    assert [
        r["name"]
        for r in client.get("/api/v1/cash-registers?is_active=false", headers=admin).json()["items"]
    ] == ["Bar"]
    # une caisse hors service (ou inconnue) n'ouvre pas de session
    refused = client.post(
        "/api/v1/cash-sessions",
        headers={**admin, "Idempotency-Key": "open-bar"},
        json={"cash_register_id": bar.json()["id"], "opening_float_xof": 0},
    )
    assert refused.status_code == 404
