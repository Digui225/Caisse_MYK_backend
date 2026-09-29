from fastapi.testclient import TestClient


def test_stock_lifecycle_and_automatic_sales_decrement(client: TestClient) -> None:
    # 1. Login responsable
    resp_token = client.post(
        "/api/v1/auth/login",
        json={"pin": "654321", "device_id": "pos-terminal-01"},
    ).json()["access_token"]
    resp_headers = {"Authorization": f"Bearer {resp_token}", "X-Device-Id": "pos-terminal-01"}

    # Créer catégorie et produit avec suivi de stock activé
    cat_id = client.post(
        "/api/v1/catalog/categories",
        headers=resp_headers,
        json={"name": "Boissons Fraîches", "kind": "DRINK"},
    ).json()["id"]

    prod_res = client.post(
        "/api/v1/catalog/products",
        headers=resp_headers,
        json={
            "category_id": cat_id,
            "name": "Bière Heineken 33cl",
            "short_name": "HEINEKEN 33",
            "price_xof": 1500,
            "track_stock": True,
        },
    )
    prod_id = prod_res.json()["id"]

    # 2. Entrée initiale en stock (+50 bouteilles)
    in_res = client.post(
        "/api/v1/stock/movements",
        headers=resp_headers,
        json={
            "product_id": prod_id,
            "type": "PURCHASE_IN",
            "quantity": 50.0,
            "unit_cost_xof": 1000,
            "reason": "Réception livraison fournisseur Brasserie",
        },
    )
    assert in_res.status_code == 201
    assert in_res.json()["quantity_after"] == 50.0

    # 3. Vérifier le stock
    stock_list = client.get("/api/v1/stock", headers=resp_headers).json()
    item = [s for s in stock_list if s["product_id"] == prod_id][0]
    assert item["quantity"] == 50.0
    assert item["is_low_stock"] is False

    # 4. Login caissière, ouverture de session et vente de 3 bières
    caissier_token = client.post(
        "/api/v1/auth/login",
        json={"pin": "123456", "device_id": "pos-terminal-01"},
    ).json()["access_token"]
    caissier_headers = {"Authorization": f"Bearer {caissier_token}", "X-Device-Id": "pos-terminal-01"}

    client.post(
        "/api/v1/cash-sessions",
        headers={**caissier_headers, "Idempotency-Key": "sess-stock-01"},
        json={"cash_register_id": "reg-01", "opening_float_xof": 10000, "business_date": "2026-09-28"},
    )

    order_id = client.post(
        "/api/v1/orders",
        headers=caissier_headers,
        json={"table_id": None, "guests_count": 1},
    ).json()["id"]

    client.post(
        f"/api/v1/orders/{order_id}/items",
        headers=caissier_headers,
        json={"product_id": prod_id, "quantity": 3},
    )

    # 5. Encaissement de la commande -> déclenche la sortie de stock automatique
    pay_res = client.post(
        f"/api/v1/orders/{order_id}/payments",
        headers={**caissier_headers, "Idempotency-Key": "pay-stock-01"},
        json={"method": "CASH", "amount_xof": 4500, "tendered_xof": 5000},
    )
    assert pay_res.status_code == 201

    # 6. Vérifier le niveau de stock après vente (50 - 3 = 47)
    stock_after_sale = client.get("/api/v1/stock", headers=resp_headers).json()
    item_after = [s for s in stock_after_sale if s["product_id"] == prod_id][0]
    assert item_after["quantity"] == 47.0

    # 7. Sortie de stock pour perte / casse (-2 bouteilles)
    loss_res = client.post(
        "/api/v1/stock/movements",
        headers=resp_headers,
        json={
            "product_id": prod_id,
            "type": "LOSS_OUT",
            "quantity": 2.0,
            "reason": "Casse d'une bouteille au bar",
        },
    )
    assert loss_res.status_code == 201
    assert loss_res.json()["quantity_after"] == 45.0

    # 8. Ajustement par inventaire physique (constaté 4 bouteilles -> seuil d'alerte activé)
    inv_res = client.post(
        "/api/v1/stock/inventory",
        headers=resp_headers,
        json={
            "product_id": prod_id,
            "counted_quantity": 4.0,
            "reason": "Inventaire contradictoire du soir",
        },
    )
    assert inv_res.status_code == 201
    assert inv_res.json()["quantity_after"] == 4.0

    # 9. Vérifier l'alerte de stock bas (4 <= 5.0)
    stock_inv = client.get("/api/v1/stock", headers=resp_headers).json()
    item_inv = [s for s in stock_inv if s["product_id"] == prod_id][0]
    assert item_inv["quantity"] == 4.0
    assert item_inv["is_low_stock"] is True

    # 10. Consulter l'historique des mouvements
    movs = client.get(f"/api/v1/stock/movements?product_id={prod_id}", headers=resp_headers).json()
    assert len(movs) >= 4
