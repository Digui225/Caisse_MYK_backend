import pytest
from fastapi.testclient import TestClient

from caisse.domain.enums import UserRole

from .conftest import auth, login

pytestmark = pytest.mark.integration


def test_cashier_cannot_list_users(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("111111", UserRole.CAISSIER)
    token = login(client, "111111")["access_token"]
    resp = client.get("/api/v1/users", headers=auth(token))  # type: ignore[arg-type]
    assert resp.status_code == 403
    assert resp.json()["code"] == "INSUFFICIENT_PRIVILEGE"


def test_admin_creates_user_and_pin_must_be_unique(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("999999", UserRole.ADMIN)
    headers = auth(login(client, "999999")["access_token"])  # type: ignore[arg-type]
    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "Awa", "role": "CAISSIER", "pin": "123456"},
    )
    assert resp.status_code == 201, resp.text
    dup = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "Koffi", "role": "CAISSIER", "pin": "123456"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "PIN_ALREADY_USED"
    assert len(client.get("/api/v1/users", headers=headers).json()["items"]) == 2


def test_pin_must_have_configured_length(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("999999", UserRole.ADMIN)
    headers = auth(login(client, "999999")["access_token"])  # type: ignore[arg-type]
    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "Awa", "role": "CAISSIER", "pin": "1234"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_deactivated_user_loses_access(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("999999", UserRole.ADMIN)
    cashier = make_user("111111", UserRole.CAISSIER)
    admin_headers = auth(login(client, "999999")["access_token"])  # type: ignore[arg-type]
    cashier_token = login(client, "111111")["access_token"]
    client.patch(f"/api/v1/users/{cashier.id}", headers=admin_headers, json={"is_active": False})
    assert client.get("/api/v1/auth/me", headers=auth(cashier_token)).status_code == 401  # type: ignore[arg-type]
