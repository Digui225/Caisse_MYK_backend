"""FNE à la demande et clients entreprise, contre la FNE simulée (`MockFneProvider`).

Les paiements (lot L4) n'existent pas encore : les commandes sont soldées directement en base.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.deps import fne_provider
from caisse.domain.enums import OrderStatus, PaymentMethod, UserRole
from caisse.domain.ports import FneRejectedError, FneUnavailableError, FneUncertainError
from caisse.infrastructure.fne import MockFneProvider
from caisse.models import AppSetting, CashRegister, Order, Payment, Product, User
from caisse.security import utcnow
from caisse.seeds.demo import load_demo_menu

from .conftest import auth, login

pytestmark = pytest.mark.integration

FNE_SETTINGS = {
    "fne.point_of_sale": "CAISSE-1",
    "fne.establishment": "RESTAURANT CHEZ SYLLA PLUS",
    "fne.walk_in_client": {
        "company_name": "CLIENT DIVERS",
        "phone": "0748735573",
        "email": "restaurant@example.ci",
    },
}


@pytest.fixture
def mock_fne() -> MockFneProvider:
    return MockFneProvider(ncc="1304777N")


@pytest.fixture
def fne_client(mock_fne: MockFneProvider) -> Iterator[TestClient]:
    from caisse.main import create_app

    app = create_app()
    app.dependency_overrides[fne_provider] = lambda: mock_fne
    with TestClient(app) as c:
        yield c


@pytest.fixture
def setup(fne_client: TestClient, db: Session, make_user, make_cash_register) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    load_demo_menu(db)
    db.add_all(AppSetting(key=k, value=v) for k, v in FNE_SETTINGS.items())
    db.commit()
    make_user("111111", UserRole.CAISSIER, name="Awa Koné")
    make_user("222222", UserRole.RESPONSABLE)
    register: CashRegister = make_cash_register()
    cashier = auth(login(fne_client, "111111")["access_token"])  # type: ignore[arg-type]
    manager = auth(login(fne_client, "222222")["access_token"])  # type: ignore[arg-type]
    opened = fne_client.post(
        "/api/v1/cash-sessions",
        headers={**cashier, "Idempotency-Key": "open"},
        json={"cash_register_id": str(register.id), "opening_float_xof": 20000},
    )
    assert opened.status_code == 201, opened.text
    return {
        "cashier": cashier,
        "manager": manager,
        "products": {p.name: str(p.id) for p in db.scalars(select(Product))},
    }


def _paid_order(
    client: TestClient,
    db: Session,
    setup: dict[str, Any],
    lines: list[tuple[str, int]],
    payments: list[tuple[PaymentMethod, int]] | None = None,
) -> dict[str, Any]:
    """Commande à emporter, lignes ajoutées par l'API, puis soldée en base."""
    cashier = setup["cashier"]
    order = client.post("/api/v1/orders", headers=cashier, json={"table_id": None}).json()["order"]
    for name, qty in lines:
        resp = client.post(
            f"/api/v1/orders/{order['id']}/items",
            headers=cashier,
            json={"product_id": setup["products"][name], "quantity": qty},
        )
        assert resp.status_code == 201, resp.text
        order = resp.json()["order"]
    row = db.get(Order, uuid.UUID(order["id"]))
    assert row is not None
    user = db.scalar(select(User).where(User.full_name == "Awa Koné"))
    assert user is not None
    for i, (method, amount) in enumerate(payments or [(PaymentMethod.CASH, row.total_ttc_xof)]):
        db.add(
            Payment(
                order_id=row.id,
                cash_session_id=row.cash_session_id,
                method=method,
                amount_xof=amount,
                idempotency_key=f"{row.id}-{i}",
                created_by_user_id=user.id,
            )
        )
    row.status, row.paid_xof, row.due_xof, row.paid_at = (
        OrderStatus.PAID,
        row.total_ttc_xof,
        0,
        utcnow(),
    )
    db.commit()
    return order


def _issue(client: TestClient, headers: dict[str, str], order_id: str, **body: Any) -> Any:
    return client.post(f"/api/v1/orders/{order_id}/fne", headers=headers, json=body)


# --- Clients entreprise ------------------------------------------------------------------


def test_customers_create_normalize_search_and_reject_duplicates(
    fne_client: TestClient, setup: dict[str, Any]
) -> None:
    cashier = setup["cashier"]
    created = fne_client.post(
        "/api/v1/customers",
        headers=cashier,
        json={"company_name": "  CGECI ", "ncc": "9506 466a", "email": "c@cgeci.ci"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["ncc"] == "9506466A"
    assert created.json()["company_name"] == "CGECI"

    bad = fne_client.post(
        "/api/v1/customers", headers=cashier, json={"company_name": "X", "ncc": "12345"}
    )
    assert bad.status_code == 422
    assert bad.json()["meta"]["fields"][0]["loc"] == ["body", "ncc"]

    dup = fne_client.post(
        "/api/v1/customers", headers=cashier, json={"company_name": "Autre", "ncc": "9506466A"}
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "CUSTOMER_NCC_EXISTS"
    assert dup.json()["meta"]["customer_id"] == created.json()["id"]

    by_ncc = fne_client.get("/api/v1/customers?ncc=9506", headers=cashier).json()["items"]
    by_name = fne_client.get("/api/v1/customers?search=cgeci", headers=cashier).json()["items"]
    assert [c["id"] for c in by_ncc] == [c["id"] for c in by_name] == [created.json()["id"]]


# --- Émission ----------------------------------------------------------------------------


def test_issue_b2c_certifies_once(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    order = _paid_order(
        fne_client,
        db,
        setup,
        [("Poisson braisé", 2), ("Attiéké", 1)],
        payments=[(PaymentMethod.CASH, 3000), (PaymentMethod.MOBILE_MONEY, 5000)],
    )
    resp = _issue(fne_client, setup["cashier"], order["id"])
    assert resp.status_code == 201, resp.text
    doc = resp.json()["document"]
    assert doc["status"] == "CERTIFIED"
    assert doc["is_uncertain"] is False
    assert doc["external_number"].startswith("1304777N")
    assert doc["qr_payload"]
    assert doc["internal_reference"] == order["order_number"]
    assert doc["fne_amount_ttc_xof"] == order["total_ttc_xof"]
    assert resp.json()["warnings"] == []

    sent = mock_fne.calls[0][1]
    assert sent["template"] == "B2C"
    assert sent["paymentMethod"] == "mobile-money"  # plus gros montant
    assert sent["pointOfSale"] == "CAISSE-1"
    assert sent["clientCompanyName"] == "CLIENT DIVERS"
    assert sent["clientSellerName"] == "Awa Koné"
    assert sent["items"][0]["taxes"] == ["TVAD"]  # régime TEE
    assert sent["items"][0]["amount"] == 3500  # HT = TTC
    assert sent["items"][0]["measurementUnit"] == "U"

    again = _issue(fne_client, setup["cashier"], order["id"])
    assert again.status_code == 200
    assert again.json()["document"]["id"] == doc["id"]
    assert len(mock_fne.calls) == 1  # pas de seconde certification

    got = fne_client.get(f"/api/v1/orders/{order['id']}/fne", headers=setup["cashier"])
    assert got.json()["id"] == doc["id"]
    dup = fne_client.get(f"/api/v1/fne/documents/{doc['id']}/duplicate", headers=setup["cashier"])
    assert dup.status_code == 200
    assert dup.json()["external_number"] == doc["external_number"]


def test_issue_requires_paid_order_and_configuration(
    fne_client: TestClient, db: Session, setup: dict[str, Any]
) -> None:
    cashier = setup["cashier"]
    open_order = fne_client.post("/api/v1/orders", headers=cashier, json={"table_id": None})
    resp = _issue(fne_client, cashier, open_order.json()["order"]["id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "FNE_ORDER_NOT_PAID"

    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    db.get(AppSetting, "fne.point_of_sale").value = ""  # type: ignore[union-attr]
    db.commit()
    resp = _issue(fne_client, cashier, order["id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "FNE_NOT_CONFIGURED"
    assert resp.json()["meta"]["missing_settings"] == ["fne.point_of_sale"]


def test_issue_b2b_requires_customer_with_ncc(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    cashier = setup["cashier"]
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])

    resp = _issue(fne_client, cashier, order["id"], template="B2B")
    assert resp.status_code == 422
    assert resp.json()["code"] == "FNE_CUSTOMER_REQUIRED"

    no_ncc = fne_client.post("/api/v1/customers", headers=cashier, json={"company_name": "SARL"})
    resp = _issue(fne_client, cashier, order["id"], template="B2B", customer_id=no_ncc.json()["id"])
    assert resp.status_code == 422
    assert resp.json()["code"] == "FNE_NCC_REQUIRED"
    assert mock_fne.calls == []

    cgeci = fne_client.post(
        "/api/v1/customers", headers=cashier, json={"company_name": "CGECI", "ncc": "9506466A"}
    )
    resp = _issue(fne_client, cashier, order["id"], template="B2B", customer_id=cgeci.json()["id"])
    assert resp.status_code == 201, resp.text
    assert resp.json()["document"]["customer_id"] == cgeci.json()["id"]
    sent = mock_fne.calls[0][1]
    assert (sent["template"], sent["clientNcc"], sent["clientCompanyName"]) == (
        "B2B",
        "9506466A",
        "CGECI",
    )
    assert sent["clientEmail"] == "restaurant@example.ci"  # repris du client de passage


# --- Échecs, renvois, cas incertains ------------------------------------------------------


def test_unavailable_is_queued_then_retried_by_manager(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    mock_fne.fail_next.append(FneUnavailableError("connexion refusée"))
    resp = _issue(fne_client, setup["cashier"], order["id"])
    assert resp.status_code == 201
    doc = resp.json()["document"]
    assert doc["status"] == "QUEUED"
    assert doc["next_retry_at"] is not None
    assert [w["code"] for w in resp.json()["warnings"]] == ["FNE_QUEUED"]
    count = fne_client.get("/api/v1/fne/pending-count", headers=setup["cashier"]).json()
    assert count == {"pending": 1, "uncertain": 0, "failed": 0}

    url = f"/api/v1/fne/documents/{doc['id']}/retry"
    assert fne_client.post(url, headers=setup["cashier"]).status_code == 403
    retried = fne_client.post(url, headers=setup["manager"])
    assert retried.status_code == 200, retried.text
    assert retried.json()["document"]["status"] == "CERTIFIED"
    assert retried.json()["document"]["attempts"] == 2


def test_uncertain_is_never_resent_without_resolution(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    manager = setup["manager"]
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    mock_fne.fail_next.append(FneUncertainError("FNE 500 : Error signing invoice", status=500))
    doc = _issue(fne_client, setup["cashier"], order["id"]).json()["document"]
    assert (doc["status"], doc["is_uncertain"]) == ("SUBMITTING", True)

    # ni second clic, ni renvoi : pas de nouvel appel
    assert _issue(fne_client, setup["cashier"], order["id"]).status_code == 200
    resp = fne_client.post(f"/api/v1/fne/documents/{doc['id']}/retry", headers=manager)
    assert resp.status_code == 409
    assert resp.json()["meta"]["reason"] == "uncertain"
    assert len(mock_fne.calls) == 1
    count = fne_client.get("/api/v1/fne/pending-count", headers=manager).json()
    assert count["uncertain"] == 1

    # constat dans l'espace FNE : la facture n'y est pas numérotée → renvoi
    resolved = fne_client.post(
        f"/api/v1/fne/documents/{doc['id']}/resolve",
        headers=manager,
        json={"is_certified": False},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["document"]["status"] == "CERTIFIED"
    assert len(mock_fne.calls) == 2


def test_uncertain_resolved_as_certified_from_fne_space(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    manager = setup["manager"]
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    mock_fne.fail_next.append(FneUncertainError("délai dépassé"))
    doc = _issue(fne_client, setup["cashier"], order["id"]).json()["document"]
    url = f"/api/v1/fne/documents/{doc['id']}/resolve"

    missing = fne_client.post(url, headers=manager, json={"is_certified": True})
    assert missing.status_code == 422
    resp = fne_client.post(
        url, headers=manager, json={"is_certified": True, "external_number": "1304777N26000000024"}
    )
    assert resp.status_code == 200
    out = resp.json()["document"]
    assert (out["status"], out["is_uncertain"]) == ("CERTIFIED", False)
    assert out["external_number"] == "1304777N26000000024"
    assert len(mock_fne.calls) == 1
    # certifiée hors API : pas d'identifiants FNE, donc pas d'avoir par API
    refund = fne_client.post(
        f"/api/v1/fne/documents/{doc['id']}/refund",
        headers=manager,
        json={"items": [{"order_item_id": str(uuid.uuid4()), "quantity": 1}]},
    )
    assert refund.status_code == 409
    assert refund.json()["meta"]["reason"] == "not_refundable"


def test_rejected_then_issued_again(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    mock_fne.fail_next.append(
        FneRejectedError("FNE 400 : Point of sale is invalid", status=400, body={"errors": {}})
    )
    resp = _issue(fne_client, setup["cashier"], order["id"])
    doc = resp.json()["document"]
    assert doc["status"] == "FAILED"
    assert [w["code"] for w in resp.json()["warnings"]] == ["FNE_REJECTED"]

    again = _issue(fne_client, setup["cashier"], order["id"])
    assert again.status_code == 201
    assert again.json()["document"]["id"] == doc["id"]
    assert again.json()["document"]["status"] == "CERTIFIED"


# --- Avoirs ------------------------------------------------------------------------------


def test_partial_refunds_up_to_certified_quantity(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    manager = setup["manager"]
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 2), ("Attiéké", 1)])
    doc = _issue(fne_client, setup["cashier"], order["id"]).json()["document"]
    poisson = order["items"][0]["id"]
    url = f"/api/v1/fne/documents/{doc['id']}/refund"

    first = fne_client.post(
        url, headers=manager, json={"items": [{"order_item_id": poisson, "quantity": 1}]}
    )
    assert first.status_code == 201, first.text
    credit = first.json()["document"]
    assert (credit["type"], credit["status"]) == ("REFUND", "CERTIFIED")
    assert credit["parent_document_id"] == doc["id"]
    assert credit["external_number"].startswith("A")
    assert mock_fne.calls[-1][0] == "refund"
    assert mock_fne.calls[-1][1]["items"][0]["quantity"] == 1

    too_much = fne_client.post(
        url, headers=manager, json={"items": [{"order_item_id": poisson, "quantity": 2}]}
    )
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "FNE_REFUND_EXCEEDS"
    assert too_much.json()["meta"]["available"] == 1

    cashier = fne_client.post(
        url, headers=setup["cashier"], json={"items": [{"order_item_id": poisson, "quantity": 1}]}
    )
    assert cashier.status_code == 403


def test_manual_mode_marks_document_manual(
    fne_client: TestClient, db: Session, setup: dict[str, Any]
) -> None:
    fne_client.app.dependency_overrides[fne_provider] = lambda: None  # type: ignore[attr-defined]
    order = _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])
    resp = _issue(fne_client, setup["cashier"], order["id"])
    assert resp.status_code == 201
    assert resp.json()["document"]["status"] == "MANUAL"


# --- Suivi -------------------------------------------------------------------------------


def test_documents_list_and_daily_summary(
    fne_client: TestClient, db: Session, setup: dict[str, Any], mock_fne: MockFneProvider
) -> None:
    manager = setup["manager"]
    certified = _paid_order(fne_client, db, setup, [("Poisson braisé", 2)])
    _issue(fne_client, setup["cashier"], certified["id"])
    queued = _paid_order(fne_client, db, setup, [("Attiéké", 1)])
    mock_fne.fail_next.append(FneUnavailableError("hors ligne"))
    _issue(fne_client, setup["cashier"], queued["id"])
    _paid_order(fne_client, db, setup, [("Poisson braisé", 1)])  # sans FNE

    docs = fne_client.get("/api/v1/fne/documents?status=QUEUED", headers=manager).json()["items"]
    assert [d["order_id"] for d in docs] == [queued["id"]]
    assert fne_client.get("/api/v1/fne/documents", headers=setup["cashier"]).status_code == 403

    summary = fne_client.get("/api/v1/fne/daily-summary", headers=manager).json()
    assert summary["paid_orders"] == 3
    assert summary["certified_orders"] == 1
    assert summary["certified_ttc_xof"] == certified["total_ttc_xof"]
    assert summary["pending_documents"] == 1
    groups = {g["group"]: g["quantity"] for g in summary["by_fiscal_group"]}
    assert groups["POISSONS"] == 3
