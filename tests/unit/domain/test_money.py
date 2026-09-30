from decimal import Decimal

import pytest

from caisse.domain.money import change_due, format_xof, line_total, split_vat, split_vat_by_rate


def test_split_vat_example_from_contract() -> None:
    # 03-CONTRAT-API §4.5 : 9 500 TTC → 8 051 HT + 1 449 TVA
    v = split_vat(9500, Decimal("18"))
    assert (v.ttc_xof, v.ht_xof, v.vat_xof) == (9500, 8051, 1449)


@pytest.mark.parametrize("ttc", [0, 1, 5, 99, 500, 1180, 3500, 412000, 10**9])
def test_split_vat_ttc_is_always_preserved(ttc: int) -> None:
    v = split_vat(ttc, Decimal("18"))
    assert v.ht_xof + v.vat_xof == ttc
    assert 0 <= v.vat_xof <= ttc


def test_split_vat_zero_rate() -> None:
    assert split_vat(1000, Decimal(0)).vat_xof == 0


def test_split_vat_half_up_rounding() -> None:
    # 59 / 1.18 = 50.0 ; 1 / 1.18 = 0.847 → 1
    assert split_vat(59, Decimal("18")).ht_xof == 50
    assert split_vat(1, Decimal("18")).ht_xof == 1


def test_split_vat_rejects_float_amount() -> None:
    with pytest.raises(TypeError):
        split_vat(9500.0, Decimal("18"))  # type: ignore[arg-type]


def test_split_vat_by_rate_groups_lines() -> None:
    v = split_vat_by_rate([(7000, Decimal("18")), (1000, Decimal("18")), (1500, Decimal("0"))])
    assert v.ttc_xof == 9500
    assert v.vat_xof == split_vat(8000, Decimal("18")).vat_xof
    assert v.ht_xof + v.vat_xof == 9500


def test_line_total() -> None:
    assert line_total(3500, 2) == 7000


@pytest.mark.parametrize(("price", "qty"), [(-1, 1), (100, 0), (100, -2)])
def test_line_total_rejects_invalid(price: int, qty: int) -> None:
    with pytest.raises(ValueError):
        line_total(price, qty)


def test_line_total_rejects_bool() -> None:
    with pytest.raises(TypeError):
        line_total(100, True)


def test_change_due() -> None:
    assert change_due(4500, 5000) == 500
    assert change_due(4500, 4500) == 0
    with pytest.raises(ValueError):
        change_due(4500, 4000)


def test_format_xof() -> None:
    assert format_xof(9500) == "9 500"
    assert format_xof(412000) == "412 000"
    assert format_xof(0) == "0"
