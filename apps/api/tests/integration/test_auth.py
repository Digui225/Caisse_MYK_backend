from fastapi.testclient import TestClient


def test_login_success_caissier(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"pin": "123456", "device_id": "pos-terminal-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["full_name"] == "Awa Caissière"
    assert data["user"]["role"] == "CAISSIER"


def test_login_invalid_pin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"pin": "000000", "device_id": "pos-terminal-01"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "INVALID_CREDENTIALS"


def test_get_current_user_me(client: TestClient) -> None:
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"pin": "123456", "device_id": "pos-terminal-01"},
    )
    token = login_res.json()["access_token"]

    # 2. Call /auth/me
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["full_name"] == "Awa Caissière"


def test_override_authorization(client: TestClient) -> None:
    # 1. Login caissière
    login_res = client.post(
        "/api/v1/auth/login",
        json={"pin": "123456", "device_id": "pos-terminal-01"},
    )
    token = login_res.json()["access_token"]

    # 2. Demande d'override avec le PIN du responsable (654321)
    override_res = client.post(
        "/api/v1/auth/override",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manager_pin": "654321",
            "reason": "Annulation table 2 demandée par client",
            "target_action": "CANCEL_ORDER",
        },
    )
    assert override_res.status_code == 200
    data = override_res.json()
    assert "override_token" in data
    assert "Kouassi Responsable" in data["authorized_by"]
