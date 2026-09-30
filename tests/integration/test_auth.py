import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from caisse.domain.enums import UserRole
from caisse.errors import OverrideRequiredError
from caisse.services import auth_service

from .conftest import auth, login

pytestmark = pytest.mark.integration


def test_login_returns_tokens_and_user(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913", UserRole.CAISSIER, "Awa Koné")
    body = login(client, "482913")
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["full_name"] == "Awa Koné"  # type: ignore[index]
    assert body["user"]["role"] == "CAISSIER"  # type: ignore[index]
    assert body["open_session"] is None


def test_wrong_pin_is_problem_json_with_remaining_attempts(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913")
    resp = client.post("/api/v1/auth/login", json={"pin": "000000", "device_id": "p1"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "INVALID_CREDENTIALS"
    assert body["meta"]["remaining_attempts"] == 4
    assert body["request_id"] == resp.headers["x-request-id"]


def test_device_locked_after_max_attempts(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913")
    codes = [
        client.post("/api/v1/auth/login", json={"pin": "000000", "device_id": "p1"}).json()["code"]
        for _ in range(5)
    ]
    assert codes == ["INVALID_CREDENTIALS"] * 4 + ["ACCOUNT_LOCKED"]
    # même le bon PIN est refusé pendant le blocage…
    resp = client.post("/api/v1/auth/login", json={"pin": "482913", "device_id": "p1"})
    assert resp.status_code == 423
    assert resp.json()["meta"]["locked_until"]
    # …mais un autre poste n'est pas affecté
    assert (
        client.post("/api/v1/auth/login", json={"pin": "482913", "device_id": "p2"}).status_code
        == 200
    )


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "TOKEN_EXPIRED"


def test_me(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913", UserRole.RESPONSABLE)
    token = login(client, "482913")["access_token"]
    resp = client.get("/api/v1/auth/me", headers=auth(token))  # type: ignore[arg-type]
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "RESPONSABLE"


def test_refresh_rotates_and_old_token_is_revoked(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913")
    first = login(client, "482913")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != first["refresh_token"]
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["code"] == "TOKEN_EXPIRED"


def test_logout_revokes_refresh(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("482913")
    tokens = login(client, "482913")
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth(tokens["access_token"]),
    )  # type: ignore[arg-type]
    assert resp.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_override_is_single_use(client: TestClient, db: Session, make_user) -> None:  # type: ignore[no-untyped-def]
    cashier = make_user("111111", UserRole.CAISSIER)
    manager = make_user("222222", UserRole.RESPONSABLE)
    token = login(client, "111111")["access_token"]

    resp = client.post(
        "/api/v1/auth/override",
        headers=auth(token),  # type: ignore[arg-type]
        json={"pin": "222222", "action": "order.remove_item"},
    )
    assert resp.status_code == 200, resp.text
    override = resp.json()["override_token"]
    assert resp.json()["granted_by"]["id"] == str(manager.id)

    granter = auth_service.consume_override(
        db,
        override,
        requested_by=cashier,
        action="order.remove_item",
        required_role=UserRole.RESPONSABLE,
    )
    db.commit()
    assert granter.id == manager.id
    with pytest.raises(OverrideRequiredError):
        auth_service.consume_override(
            db,
            override,
            requested_by=cashier,
            action="order.remove_item",
            required_role=UserRole.RESPONSABLE,
        )


def test_override_with_cashier_pin_is_refused(client: TestClient, make_user) -> None:  # type: ignore[no-untyped-def]
    make_user("111111", UserRole.CAISSIER)
    make_user("333333", UserRole.CAISSIER)
    token = login(client, "111111")["access_token"]
    resp = client.post(
        "/api/v1/auth/override",
        headers=auth(token),  # type: ignore[arg-type]
        json={"pin": "333333", "action": "order.cancel"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "OVERRIDE_REQUIRED"
