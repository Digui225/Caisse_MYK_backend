from decimal import Decimal

import pytest

from caisse.domain import fne
from caisse.domain.enums import PaymentMethod

ISSUER = fne.FneIssuer(point_of_sale="Caisse 1", establishment="RESTAURANT CHEZ SYLLA PLUS")
WALK_IN = fne.FneClient(company_name="CLIENT DIVERS", phone="0700000000", email="c@myk.ci")


def _line(ttc: int = 3500, qty: int = 2, rate: str = "18") -> fne.FneLine:
    return fne.FneLine(
        description="Poisson braisé", quantity=qty, unit_price_ttc_xof=ttc, vat_rate=Decimal(rate)
    )


@pytest.mark.parametrize(
    ("ttc", "rate", "decimals", "expected"),
    [
        (1000, "18", 4, Decimal("847.4576")),
        (1000, "18", 0, Decimal("847")),
        (3500, "18.00", 2, Decimal("2966.10")),
        (1090, "9", 0, Decimal("1000")),
        (1000, "0", 4, Decimal("1000.0000")),
    ],
)
def test_unit_price_ht(ttc: int, rate: str, decimals: int, expected: Decimal) -> None:
    assert fne.unit_price_ht(ttc, Decimal(rate), decimals) == expected


def test_vat_codes_including_tvad_for_zero_rate() -> None:
    assert fne.vat_code(Decimal("18.00")) == "TVA"
    assert fne.vat_code(Decimal("9")) == "TVAB"
    assert fne.vat_code(Decimal("0.00")) == "TVAD"
    with pytest.raises(fne.FneMappingError) as exc:
        fne.vat_code(Decimal("10"))
    assert exc.value.code == "FNE_VAT_RATE_UNMAPPED"


def test_payment_methods() -> None:
    assert fne.payment_method_code(PaymentMethod.MOBILE_MONEY) == "mobile-money"
    assert fne.payment_method_code(PaymentMethod.CREDIT) == "deferred"
    with pytest.raises(fne.FneMappingError):
        fne.payment_method_code(PaymentMethod.OTHER)
    assert fne.payment_method_code(PaymentMethod.OTHER, {PaymentMethod.OTHER: "check"}) == "check"


def test_dominant_payment_method_sums_per_method_and_keeps_first_on_tie() -> None:
    cash, momo = PaymentMethod.CASH, PaymentMethod.MOBILE_MONEY
    assert fne.dominant_payment_method([(cash, 3000), (momo, 4000), (cash, 2000)]) == cash
    assert fne.dominant_payment_method([(momo, 5000), (cash, 5000)]) == momo
    with pytest.raises(fne.FneMappingError):
        fne.dominant_payment_method([])


def test_build_sale_request_b2c() -> None:
    body = fne.build_sale_request(
        lines=[_line(), _line(ttc=1000, qty=1, rate="0")],
        client=WALK_IN,
        template=fne.FneTemplate.B2C,
        payment_method="cash",
        issuer=ISSUER,
    )
    assert body["invoiceType"] == "sale"
    assert body["template"] == "B2C"
    assert body["establishment"] == "RESTAURANT CHEZ SYLLA PLUS"
    assert isinstance(body["clientPhone"], str)
    assert "clientNcc" not in body
    assert body["items"] == [
        {
            "taxes": ["TVA"],
            "description": "Poisson braisé",
            "quantity": 2,
            "amount": Decimal("2966.1017"),
        },
        {
            "taxes": ["TVAD"],
            "description": "Poisson braisé",
            "quantity": 1,
            "amount": Decimal("1000.0000"),
        },
    ]


def test_build_sale_request_b2b_requires_ncc() -> None:
    kwargs: dict[str, object] = dict(
        lines=[_line()], template=fne.FneTemplate.B2B, payment_method="card", issuer=ISSUER
    )
    with pytest.raises(fne.FneMappingError) as exc:
        fne.build_sale_request(client=WALK_IN, **kwargs)  # type: ignore[arg-type]
    assert exc.value.code == "FNE_NCC_REQUIRED"
    client = fne.FneClient(company_name="KPMG", phone="0709080765", email="i@k.ci", ncc="9502363N")
    body = fne.build_sale_request(client=client, **kwargs)  # type: ignore[arg-type]
    assert body["clientNcc"] == "9502363N"


@pytest.mark.parametrize(
    "change",
    [
        {"lines": []},
        {"lines": [_line(qty=0)]},
        {"issuer": fne.FneIssuer(point_of_sale=" ", establishment="X")},
        {"client": fne.FneClient(company_name="X", phone="", email="e@x.ci")},
    ],
)
def test_build_sale_request_rejects_incomplete_data(change: dict[str, object]) -> None:
    kwargs: dict[str, object] = dict(
        lines=[_line()],
        client=WALK_IN,
        template=fne.FneTemplate.B2C,
        payment_method="cash",
        issuer=ISSUER,
    )
    kwargs.update(change)
    with pytest.raises(fne.FneMappingError):
        fne.build_sale_request(**kwargs)  # type: ignore[arg-type]


def test_build_refund_request() -> None:
    assert fne.build_refund_request([("a", 2), ("b", 1)]) == {
        "items": [{"id": "a", "quantity": 2}, {"id": "b", "quantity": 1}]
    }
    with pytest.raises(fne.FneMappingError):
        fne.build_refund_request([("a", 0)])
