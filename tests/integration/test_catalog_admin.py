from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from caisse.domain.enums import UserRole
from caisse.models import CashRegister

from .conftest import auth, login

pytestmark = pytest.mark.integration


@pytest.fixture
def users(client: TestClient, make_user) -> dict[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    make_user("111111", UserRole.CAISSIER)
    make_user("222222", UserRole.RESPONSABLE)
    return {
        "cashier": auth(login(client, "111111")["access_token"]),  # type: ignore[arg-type]
        "manager": auth(login(client, "222222")["access_token"]),  # type: ignore[arg-type]
    }


def _category(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    resp = client.post("/api/v1/categories", headers=headers, json={"kind": "FOOD", **body})
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


def _product(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    resp = client.post("/api/v1/products", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


def test_roles(client: TestClient, users: dict[str, dict[str, str]]) -> None:
    body = {"name": "Viandes", "kind": "FOOD"}
    assert client.post("/api/v1/categories", headers=users["cashier"], json=body).status_code == 403
    assert client.post("/api/v1/categories", headers=users["manager"], json=body).status_code == 201


def test_categories(client: TestClient, users: dict[str, dict[str, str]]) -> None:
    manager = users["manager"]
    meat = _category(client, manager, name="Viandes", fiscal_group="viandes")
    fish = _category(client, manager, name="Poissons", color="#B45309")
    assert (meat["sort_order"], fish["sort_order"]) == (0, 1)  # à la suite
    assert meat["fiscal_group"] == "VIANDES"

    dup = client.post(
        "/api/v1/categories", headers=manager, json={"name": "viandes", "kind": "FOOD"}
    )
    assert dup.status_code == 409
    assert (dup.json()["code"], dup.json()["meta"]["category_id"]) == (
        "CATEGORY_NAME_EXISTS",
        meat["id"],
    )

    url = f"/api/v1/categories/{fish['id']}"
    patched = client.patch(url, headers=manager, json={"color": None, "sort_order": 5})
    assert (patched.json()["color"], patched.json()["sort_order"]) == (None, 5)
    renamed = client.patch(url, headers=manager, json={"name": "Viandes"})
    assert renamed.status_code == 409

    # catégorie non vide : refus, puis désactivation une fois le produit retiré du menu
    plate = _product(client, manager, category_id=fish["id"], name="Sosso 3000", price_xof=3000)
    refused = client.delete(url, headers=manager)
    assert refused.status_code == 409
    assert refused.json()["meta"]["active_products"] == 1
    client.patch(f"/api/v1/products/{plate['id']}", headers=manager, json={"is_active": False})
    deleted = client.delete(url, headers=manager)
    assert deleted.status_code == 200 and deleted.json()["is_active"] is False

    listed = client.get("/api/v1/categories", headers=users["cashier"]).json()["items"]
    assert [c["name"] for c in listed] == ["Viandes"]
    inactive = client.get("/api/v1/categories?is_active=false", headers=manager).json()["items"]
    assert [c["name"] for c in inactive] == ["Poissons"]
    # une catégorie désactivée n'accepte plus de produit
    closed = client.post(
        "/api/v1/products",
        headers=manager,
        json={"category_id": fish["id"], "name": "Loss", "price_xof": 3000},
    )
    assert closed.status_code == 404
    assert client.patch(url, headers=manager, json={"is_active": True}).json()["is_active"]


def test_products(client: TestClient, users: dict[str, dict[str, str]]) -> None:
    manager = users["manager"]
    meat = _category(client, manager, name="Viandes")
    drinks = _category(client, manager, name="Boissons", kind="DRINK")
    plate = _product(
        client, manager, category_id=meat["id"], name="Foufou/foutou faux brochet", price_xof=3500
    )
    assert plate["short_name"] == "Foufou/foutou faux b"  # 20 caractères
    assert (plate["vat_rate"], plate["sort_order"], plate["track_stock"]) == (0.0, 0, False)
    second = _product(
        client,
        manager,
        category_id=meat["id"],
        name="Plat bœuf",
        short_name="Boeuf",
        price_xof=3000,
        sku="PB-01",
    )
    assert second["sort_order"] == 1

    dup = client.post(
        "/api/v1/products",
        headers=manager,
        json={"category_id": meat["id"], "name": "PLAT BŒUF", "price_xof": 1},
    )
    assert (dup.status_code, dup.json()["code"]) == (409, "PRODUCT_NAME_EXISTS")
    sku = client.post(
        "/api/v1/products",
        headers=manager,
        json={"category_id": meat["id"], "name": "Autre", "price_xof": 1, "sku": "PB-01"},
    )
    assert (sku.status_code, sku.json()["code"]) == (409, "PRODUCT_SKU_EXISTS")

    url = f"/api/v1/products/{second['id']}"
    moved = client.patch(
        url, headers=manager, json={"category_id": drinks["id"], "sku": None, "price_xof": 1}
    )
    body = moved.json()
    assert (body["category_id"], body["price_xof"]) == (drinks["id"], 3000)  # prix ignoré ici
    assert client.get(url, headers=users["cashier"]).json()["category_id"] == drinks["id"]
    renamed = client.patch(url, headers=manager, json={"name": plate["name"]})
    assert renamed.status_code == 409
    assert client.patch(url, headers=users["cashier"], json={"name": "x"}).status_code == 403
    assert client.get("/api/v1/products/" + meat["id"], headers=manager).status_code == 404


def test_price_change_keeps_open_orders(
    client: TestClient, users: dict[str, dict[str, str]], db: Session
) -> None:
    manager, cashier = users["manager"], users["cashier"]
    meat = _category(client, manager, name="Viandes")
    plate = _product(client, manager, category_id=meat["id"], name="Plat poulet", price_xof=3000)
    register = CashRegister(name="Caisse 1", printer_config={})
    db.add(register)
    db.commit()
    client.post(
        "/api/v1/cash-sessions",
        headers={**cashier, "Idempotency-Key": "open"},
        json={"cash_register_id": str(register.id), "opening_float_xof": 0},
    )
    order_id = client.post("/api/v1/orders", headers=cashier, json={}).json()["order"]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/items",
        headers=cashier,
        json={"product_id": plate["id"], "quantity": 2},
    )

    url = f"/api/v1/products/{plate['id']}/price"
    assert client.patch(url, headers=manager, json={"price_xof": 3500}).status_code == 422
    changed = client.patch(url, headers=manager, json={"price_xof": 3500, "reason": "hausse"})
    assert changed.json()["price_xof"] == 3500
    same = client.patch(url, headers=manager, json={"price_xof": 3500, "reason": "rien"})
    assert same.status_code == 200
    history = client.get(f"/api/v1/products/{plate['id']}/price-history", headers=manager).json()[
        "items"
    ]
    assert [(h["old_price_xof"], h["new_price_xof"], h["reason"]) for h in history] == [
        (3000, 3500, "hausse")
    ]

    # la commande en cours garde l'ancien prix ; une nouvelle ligne prend le nouveau
    order = client.get(f"/api/v1/orders/{order_id}", headers=cashier).json()
    assert order["total_ttc_xof"] == 6000
    client.post(
        f"/api/v1/orders/{order_id}/items",
        headers=cashier,
        json={"product_id": plate["id"], "quantity": 1},
    )
    assert client.get(f"/api/v1/orders/{order_id}", headers=cashier).json()["total_ttc_xof"] == 9500
