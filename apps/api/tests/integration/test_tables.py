from fastapi.testclient import TestClient


def test_tables_and_board(client: TestClient) -> None:
    # 1. Login caissière
    login_res = client.post(
        "/api/v1/auth/login",
        json={"pin": "123456", "device_id": "pos-terminal-01"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Consulter la liste des tables
    tables_res = client.get("/api/v1/tables", headers=headers)
    assert tables_res.status_code == 200
    tables = tables_res.json()
    assert isinstance(tables, list)

    # 3. Consulter le tableau de bord de salle
    board_res = client.get("/api/v1/tables/board", headers=headers)
    assert board_res.status_code == 200
    board_data = board_res.json()
    assert "tables" in board_data
    assert "open_orders_count" in board_data
    assert "total_in_progress_xof" in board_data
