from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.domain.enums import UserRole
from caisse.models import CashRegister, Product
from caisse.seeds.demo import load_demo_menu

from .conftest import auth, login

pytestmark = pytest.mark.integration


@pytest.fixture
def setup(client: TestClient, db: Session, make_user) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    load_demo_menu(db)
    register = CashRegister(name="Caisse 1", printer_config={})
    db.add(register)
    db.commit()
    make_user("111111", UserRole.CAISSIER)
    make_user("333333", UserRole.ADMIN)
    cashier = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]
    admin = auth(login(client, "333333")["access_token"])  # type: ignore[arg-type]
    client.post(
        "/api/v1/cash-sessions",
        headers={**cashier, "Idempotency-Key": "open"},
        json={"cash_register_id": str(register.id), "opening_float_xof": 0},
    )
    return {
        "cashier": cashier,
        "admin": admin,
        "alloco": str(db.scalars(select(Product).where(Product.name == "Alloco")).one().id),
    }


def _table(client: TestClient, admin: dict[str, str], **body: Any) -> dict[str, Any]:
    resp = client.post("/api/v1/tables", headers=admin, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


def _open(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    return client.post("/api/v1/orders", headers=headers, json=body)


def test_table_crud(client: TestClient, setup: dict[str, Any]) -> None:
    admin, cashier = setup["admin"], setup["cashier"]
    assert client.post("/api/v1/tables", headers=cashier, json={"label": "1"}).status_code == 403
    one = _table(client, admin, label=" 1 ")
    two = _table(client, admin, label="T2", zone="Terrasse", seats=6)
    assert (one["label"], one["zone"], one["seats"], one["sort_order"]) == ("1", "Salle", 4, 0)
    assert two["sort_order"] == 1
    dup = client.post("/api/v1/tables", headers=admin, json={"label": "t2"})
    assert (dup.status_code, dup.json()["code"]) == (409, "TABLE_LABEL_EXISTS")

    url = f"/api/v1/tables/{two['id']}"
    assert client.patch(url, headers=admin, json={"seats": 8}).json()["seats"] == 8
    assert client.patch(url, headers=admin, json={"label": "1"}).status_code == 409

    # table occupée : désactivation refusée
    order_id = _open(client, cashier, table_id=two["id"]).json()["order"]["id"]
    busy = client.delete(url, headers=admin)
    assert (busy.status_code, busy.json()["code"]) == (409, "TABLE_HAS_ACTIVE_ORDERS")
    assert busy.json()["meta"]["order_ids"] == [order_id]
    client.post(f"/api/v1/orders/{order_id}/cancel", headers=admin, json={"reason": "test"})
    assert client.delete(url, headers=admin).json()["is_active"] is False

    assert [t["label"] for t in client.get("/api/v1/tables", headers=cashier).json()["items"]] == [
        "1"
    ]
    off = client.get("/api/v1/tables?is_active=false", headers=admin).json()["items"]
    assert [t["label"] for t in off] == ["T2"]
    assert _open(client, cashier, table_id=two["id"]).status_code == 404  # hors service


def test_table_sharing(client: TestClient, setup: dict[str, Any]) -> None:
    admin, cashier = setup["admin"], setup["cashier"]
    table = _table(client, admin, label="5")

    first = _open(client, cashier, table_id=table["id"]).json()["order"]
    assert first["note_label"] == "Note 1"
    refused = _open(client, cashier, table_id=table["id"])
    assert (refused.status_code, refused.json()["code"]) == (409, "TABLE_ALREADY_OCCUPIED")
    assert refused.json()["meta"] == {"order_id": first["id"], "active_orders": 1}

    second = _open(client, cashier, table_id=table["id"], allow_multiple=True).json()["order"]
    named = _open(client, cashier, table_id=table["id"], note_label="Groupe Koné").json()["order"]
    assert (second["note_label"], named["note_label"]) == ("Note 2", "Groupe Koné")
    taken = _open(client, cashier, table_id=table["id"], note_label="groupe koné")
    assert (taken.status_code, taken.json()["code"]) == (409, "ORDER_LABEL_TAKEN")

    client.post(
        f"/api/v1/orders/{second['id']}/items",
        headers=cashier,
        json={"product_id": setup["alloco"], "quantity": 2},
    )
    board = client.get("/api/v1/tables/board", headers=cashier).json()
    row = board["tables"][0]
    assert row["status"] == "OCCUPIED"
    assert [o["note_label"] for o in row["orders"]] == ["Note 1", "Note 2", "Groupe Koné"]
    assert row["order"]["id"] == first["id"]  # la plus ancienne
    assert row["total_ttc_xof"] == 2000
    assert board["summary"]["open_orders"] == 3

    # Note 1 annulée : la prochaine commande reprend le premier numéro libre
    client.post(f"/api/v1/orders/{first['id']}/cancel", headers=admin, json={"reason": "test"})
    again = _open(client, cashier, table_id=table["id"], allow_multiple=True).json()["order"]
    assert again["note_label"] == "Note 1"

    takeaway = _open(client, cashier, note_label="Awa").json()["order"]
    assert (takeaway["note_label"], takeaway["counter_number"]) == ("Awa", 1)
