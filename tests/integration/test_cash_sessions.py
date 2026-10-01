import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from caisse.domain.enums import OrderStatus, UserRole
from caisse.models import CashRegister, Order

from .conftest import auth, login

pytestmark = pytest.mark.integration


def _open(
    client: TestClient,
    headers: dict[str, str],
    register: CashRegister,
    key: str,
    float_xof: int = 20000,
) -> httpx.Response:
    return client.post(
        "/api/v1/cash-sessions",
        headers={**headers, "Idempotency-Key": key},
        json={"cash_register_id": str(register.id), "opening_float_xof": float_xof},
    )


def test_open_session_then_reject_second_open(
    client: TestClient,
    make_user,
    make_cash_register,  # type: ignore[no-untyped-def]
) -> None:
    make_user("111111", UserRole.CAISSIER)
    register = make_cash_register()
    headers = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]

    resp = _open(client, headers, register, "open-1")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["cash_register_id"] == str(register.id)
    assert body["status"] == "OPEN"

    dup = _open(client, headers, register, "open-2")
    assert dup.status_code == 409
    assert dup.json()["code"] == "SESSION_ALREADY_OPEN"


def test_open_session_idempotent_replay_and_conflict(
    client: TestClient,
    make_user,
    make_cash_register,  # type: ignore[no-untyped-def]
) -> None:
    make_user("111111", UserRole.CAISSIER)
    register = make_cash_register()
    headers = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]

    first = _open(client, headers, register, "same-key")
    assert first.status_code == 201

    replay = _open(client, headers, register, "same-key")
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.json() == first.json()

    conflict = _open(client, headers, register, "same-key", float_xof=99999)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_close_blocked_by_open_order(
    client: TestClient,
    db: Session,
    make_user,
    make_cash_register,  # type: ignore[no-untyped-def]
) -> None:
    cashier = make_user("111111", UserRole.CAISSIER)
    register = make_cash_register()
    headers = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]
    session_id = _open(client, headers, register, "open-1").json()["id"]

    db.add(
        Order(
            order_number="2026-01-01-0001",
            business_date=datetime.now(UTC).date(),
            cash_session_id=uuid.UUID(session_id),
            status=OrderStatus.OPEN,
            opened_by_user_id=cashier.id,
            opened_at=datetime.now(UTC),
        )
    )
    db.commit()

    resp = client.post(
        f"/api/v1/cash-sessions/{session_id}/close",
        headers={**headers, "Idempotency-Key": "close-1"},
        json={"counted_breakdown": {"1000": 20}, "notes": None},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "SESSION_HAS_OPEN_ORDERS"


def test_close_session_computes_expected_cash_and_z_number(
    client: TestClient,
    make_user,
    make_cash_register,  # type: ignore[no-untyped-def]
) -> None:
    make_user("111111", UserRole.CAISSIER)
    register = make_cash_register()
    headers = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]
    session_id = _open(client, headers, register, "open-1", float_xof=20000).json()["id"]

    in_resp = client.post(
        f"/api/v1/cash-sessions/{session_id}/movements",
        headers=headers,
        json={"type": "IN", "amount_xof": 5000, "reason": "appoint"},
    )
    assert in_resp.status_code == 201, in_resp.text
    out_resp = client.post(
        f"/api/v1/cash-sessions/{session_id}/movements",
        headers=headers,
        json={"type": "OUT", "amount_xof": 2000, "reason": "achat glace"},
    )
    assert out_resp.status_code == 201, out_resp.text

    # expected = 20000 + 5000 (IN) - 2000 (OUT) = 23000
    counted = {"10000": 2, "1000": 3}  # 23000
    close = client.post(
        f"/api/v1/cash-sessions/{session_id}/close",
        headers={**headers, "Idempotency-Key": "close-1"},
        json={"counted_breakdown": counted, "notes": "RAS"},
    )
    assert close.status_code == 201, close.text
    z = close.json()
    assert z["expected_cash_xof"] == 23000
    assert z["counted_cash_xof"] == 23000
    assert z["variance_xof"] == 0
    assert z["z_number"] == 1

    z_report = client.get(f"/api/v1/cash-sessions/{session_id}/z-report", headers=headers)
    assert z_report.status_code == 200
    assert z_report.json()["z_number"] == 1


def test_history_reserved_to_responsable(
    client: TestClient,
    make_user,
    make_cash_register,  # type: ignore[no-untyped-def]
) -> None:
    make_user("111111", UserRole.CAISSIER)
    make_user("999999", UserRole.RESPONSABLE)
    make_cash_register()
    cashier_headers = auth(login(client, "111111")["access_token"])  # type: ignore[arg-type]
    resp_headers = auth(login(client, "999999")["access_token"])  # type: ignore[arg-type]

    assert client.get("/api/v1/cash-sessions", headers=cashier_headers).status_code == 403
    assert client.get("/api/v1/cash-sessions", headers=resp_headers).status_code == 200
