import pytest
from caisse.domain.enums import PaymentMethod
from caisse.domain.payment_rules import (
    validate_payment_amount,
    calculate_change,
    should_open_drawer,
    build_esc_pos_bytes,
    format_receipt_text,
    ESC_DRAWER_KICK,
    ESC_CUT_PAPER,
)
from caisse.errors import CaisseException


def test_validate_payment_amount_valid():
    validate_payment_amount(5000, 10000)
    validate_payment_amount(10000, 10000)


def test_validate_payment_amount_invalid_negative_or_zero():
    with pytest.raises(CaisseException) as exc:
        validate_payment_amount(0, 5000)
    assert exc.value.code == "INVALID_PAYMENT_AMOUNT"

    with pytest.raises(CaisseException) as exc:
        validate_payment_amount(-1000, 5000)
    assert exc.value.code == "INVALID_PAYMENT_AMOUNT"


def test_validate_payment_amount_overpayment():
    with pytest.raises(CaisseException) as exc:
        validate_payment_amount(15000, 10000)
    assert exc.value.code == "OVERPAYMENT_NOT_ALLOWED"


def test_calculate_change_cash_valid():
    # Remis 10 000 pour 7 500 à payer = 2 500 de rendu
    change = calculate_change(tendered_xof=10000, amount_xof=7500, method=PaymentMethod.CASH)
    assert change == 2500

    # Remis exact
    change_exact = calculate_change(tendered_xof=5000, amount_xof=5000, method=PaymentMethod.CASH)
    assert change_exact == 0


def test_calculate_change_cash_insufficient():
    with pytest.raises(CaisseException) as exc:
        calculate_change(tendered_xof=4000, amount_xof=5000, method=PaymentMethod.CASH)
    assert exc.value.code == "INSUFFICIENT_TENDERED_AMOUNT"


def test_calculate_change_non_cash():
    change = calculate_change(tendered_xof=10000, amount_xof=5000, method=PaymentMethod.MOBILE_MONEY)
    assert change == 0


def test_should_open_drawer_rules():
    assert should_open_drawer(PaymentMethod.CASH) is True
    assert should_open_drawer(PaymentMethod.MOBILE_MONEY) is False
    assert should_open_drawer(PaymentMethod.CARD) is False

    # Duplicata : jamais d'ouverture de tiroir
    assert should_open_drawer(PaymentMethod.CASH, is_reprint=True) is False

    # Action manuelle responsable : ouverture forcée
    assert should_open_drawer(PaymentMethod.MOBILE_MONEY, is_manual_override=True) is True


def test_build_esc_pos_bytes():
    raw_cash = build_esc_pos_bytes("Test ticket", open_drawer=True, cut=True)
    assert ESC_DRAWER_KICK in raw_cash
    assert ESC_CUT_PAPER in raw_cash
    assert b"Test ticket" in raw_cash

    raw_momo = build_esc_pos_bytes("Test ticket momo", open_drawer=False, cut=True)
    assert ESC_DRAWER_KICK not in raw_momo
    assert ESC_CUT_PAPER in raw_momo


def test_format_receipt_text_rendering():
    text = format_receipt_text(
        restaurant_info={"name": "MYK TEST RESTO", "address": "Riviera", "phone": "07000000"},
        order_info={"order_number": "2026-09-28-0001", "table_label": "Table 1", "guests_count": 2, "cashier_name": "Awa", "date_str": "28/09/2026 12:00"},
        items=[
            {"name": "Poisson Braisé", "quantity": 1, "line_total_xof": 6000},
            {"name": "Attiéké", "quantity": 2, "line_total_xof": 1000},
        ],
        payments=[{"method": "CASH", "amount_xof": 7000}],
        totals={"total_ttc_xof": 7000, "total_vat_xof": 1068, "vat_rate": 18, "change_xof": 0},
        is_duplicate=False,
    )
    assert "MYK TEST RESTO" in text
    assert "2026-09-28-0001" in text
    assert "Poisson Braisé" in text
    assert "7 000 F" in text
    assert "DUPLICATA" not in text

    dup_text = format_receipt_text(
        restaurant_info={"name": "MYK TEST RESTO"},
        order_info={"order_number": "2026-09-28-0001"},
        items=[],
        payments=[],
        totals={"total_ttc_xof": 0, "total_vat_xof": 0},
        is_duplicate=True,
    )
    assert "DUPLICATA" in dup_text
