"""Impression : ticket au paiement et à la clôture (voir test_payments.py / test_cash_sessions.py
pour ces deux cas), ré-impression, file d'impression et actions directes."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.domain.enums import UserRole
from caisse.models import CashRegister, Product, RestaurantTable
from caisse.seeds.demo import load_demo_menu

from .conftest import FakePrintAgent, auth, login

pytestmark = pytest.mark.integration


@pytest.fixture
def setup(client: TestClient, db: Session, make_user, make_cash_register) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    load_demo_menu(db)
    db.add(RestaurantTable(label="1", sort_order=0))
    db.commit()
    make_user("111111", UserRole.CAISSIER)
    make_user("222222", UserRole.RESPONSABLE)
    make_user("333333", UserRole.ADMIN)
    register: CashRegister = make_cash_register()
    cashier = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]
    manager = auth(login(client, "222222")["access_token"])  # type: ignore[arg-type]
    admin = auth(login(client, "333333")["access_token"])  # type: ignore[arg-type]
    opened = client.post(
        "/api/v1/cash-sessions",
        headers={**cashier, "Idempotency-Key": "open"},
        json={"cash_register_id": str(register.id), "opening_float_xof": 20000},
    )
    assert opened.status_code == 201, opened.text
    return {
        "cashier": cashier,
        "manager": manager,
        "admin": admin,
        "products": {p.name: str(p.id) for p in db.scalars(select(Product))},
        "table_id": str(db.scalars(select(RestaurantTable)).one().id),
    }


def _paid_order(client: TestClient, setup: dict[str, Any]) -> str:
    headers, p = setup["cashier"], setup["products"]
    order_id: str = client.post(
        "/api/v1/orders", headers=headers, json={"table_id": setup["table_id"]}
    ).json()["order"]["id"]
    added = client.post(
        f"/api/v1/orders/{order_id}/items",
        headers=headers,
        json={"product_id": p["Poisson braisé"], "quantity": 1},
    )
    assert added.status_code == 201, added.text
    pay = client.post(
        f"/api/v1/orders/{order_id}/payments",
        headers={**headers, "Idempotency-Key": f"pay-{order_id}"},
        json={"method": "CASH", "amount_xof": 3500, "tendered_xof": 3500},
    )
    assert pay.status_code == 201, pay.text
    return order_id


def test_status(client: TestClient, setup: dict[str, Any]) -> None:
    resp = client.get("/api/v1/printing/status", headers=setup["cashier"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_online"] is True
    assert body["queued_jobs"] == 0
    assert body["failed_jobs"] == 0


def test_reprint_then_retry(
    client: TestClient, setup: dict[str, Any], fake_print_agent: FakePrintAgent
) -> None:
    order_id = _paid_order(client, setup)

    jobs = client.get("/api/v1/printing/jobs", headers=setup["cashier"]).json()["items"]
    assert any(j["order_id"] == order_id and j["status"] == "DONE" for j in jobs)

    fake_print_agent.mode = "offline"
    reprint = client.post(f"/api/v1/orders/{order_id}/reprint", headers=setup["cashier"])
    assert reprint.status_code == 200, reprint.text

    failed = client.get(
        "/api/v1/printing/jobs", headers=setup["cashier"], params={"status": "FAILED"}
    ).json()["items"]
    assert len(failed) == 1
    job_id = failed[0]["id"]
    assert failed[0]["is_reprint"] is True

    fake_print_agent.mode = "ok"
    retried = client.post(f"/api/v1/printing/jobs/{job_id}/retry", headers=setup["cashier"])
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "DONE"

    again = client.post(f"/api/v1/printing/jobs/{job_id}/retry", headers=setup["cashier"])
    assert again.status_code == 409
    assert again.json()["code"] == "PRINT_JOB_NOT_RETRYABLE"


def test_reprint_without_prior_receipt(client: TestClient, setup: dict[str, Any]) -> None:
    headers = setup["cashier"]
    order_id = client.post(
        "/api/v1/orders", headers=headers, json={"table_id": setup["table_id"]}
    ).json()["order"]["id"]
    resp = client.post(f"/api/v1/orders/{order_id}/reprint", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "NO_RECEIPT_TO_REPRINT"


def test_open_drawer(
    client: TestClient, setup: dict[str, Any], fake_print_agent: FakePrintAgent
) -> None:
    denied = client.post("/api/v1/printing/open-drawer", headers=setup["cashier"])
    assert denied.status_code == 403

    resp = client.post("/api/v1/printing/open-drawer", headers=setup["manager"])
    assert resp.status_code == 200
    assert resp.json()["drawer_opened"] is True

    fake_print_agent.mode = "offline"
    offline = client.post("/api/v1/printing/open-drawer", headers=setup["manager"])
    assert offline.status_code == 503
    assert offline.json()["code"] == "PRINT_AGENT_UNAVAILABLE"

    fake_print_agent.mode = "paper_out"
    broken = client.post("/api/v1/printing/open-drawer", headers=setup["manager"])
    assert broken.status_code == 503
    assert broken.json()["code"] == "PRINTER_UNAVAILABLE"


def test_test_print(
    client: TestClient, setup: dict[str, Any], fake_print_agent: FakePrintAgent
) -> None:
    denied = client.post("/api/v1/printing/test", headers=setup["manager"])
    assert denied.status_code == 403

    resp = client.post("/api/v1/printing/test", headers=setup["admin"])
    assert resp.status_code == 200
    assert resp.json()["printed"] is True

    fake_print_agent.mode = "offline"
    offline = client.post("/api/v1/printing/test", headers=setup["admin"])
    assert offline.status_code == 503
    assert offline.json()["code"] == "PRINT_AGENT_UNAVAILABLE"
