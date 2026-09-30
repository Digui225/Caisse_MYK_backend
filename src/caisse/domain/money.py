"""Montants en entiers XOF (ADR-04). Le TTC fait foi ; HT et TVA en sont déduits.

Aucun flottant : les taux sont manipulés en `Decimal`, les montants en `int`.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

Xof = int


def _require_int(amount: object, name: str = "amount") -> None:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError(f"{name} doit être un entier XOF, reçu {type(amount).__name__}")


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def line_total(unit_price_xof: Xof, quantity: int) -> Xof:
    _require_int(unit_price_xof, "unit_price_xof")
    _require_int(quantity, "quantity")
    if unit_price_xof < 0:
        raise ValueError("unit_price_xof ne peut pas être négatif")
    if quantity <= 0:
        raise ValueError("quantity doit être strictement positive")
    return unit_price_xof * quantity


@dataclass(frozen=True, slots=True)
class VatBreakdown:
    ttc_xof: Xof
    ht_xof: Xof
    vat_xof: Xof


def split_vat(ttc_xof: Xof, vat_rate_percent: Decimal) -> VatBreakdown:
    """`ht = round(ttc / (1 + taux))`, `tva = ttc - ht` (00-ARCHITECTURE §7.1).

    >>> split_vat(9500, Decimal("18"))
    VatBreakdown(ttc_xof=9500, ht_xof=8051, vat_xof=1449)
    """
    _require_int(ttc_xof, "ttc_xof")
    rate = Decimal(vat_rate_percent)
    if rate < 0:
        raise ValueError("taux de TVA négatif")
    ht = round_half_up(Decimal(ttc_xof) / (Decimal(1) + rate / Decimal(100)))
    return VatBreakdown(ttc_xof=ttc_xof, ht_xof=ht, vat_xof=ttc_xof - ht)


def split_vat_by_rate(lines: list[tuple[Xof, Decimal]]) -> VatBreakdown:
    """Ventilation d'une commande multi-taux : on regroupe le TTC par taux, puis on ventile
    chaque groupe (le TTC total reste exactement la somme des lignes)."""
    by_rate: dict[Decimal, int] = {}
    for amount, rate in lines:
        _require_int(amount)
        key = Decimal(rate)
        by_rate[key] = by_rate.get(key, 0) + amount
    parts = [split_vat(ttc, rate) for rate, ttc in sorted(by_rate.items())]
    return VatBreakdown(
        ttc_xof=sum(p.ttc_xof for p in parts),
        ht_xof=sum(p.ht_xof for p in parts),
        vat_xof=sum(p.vat_xof for p in parts),
    )


def change_due(amount_xof: Xof, tendered_xof: Xof) -> Xof:
    """Rendu monnaie en espèces. `tendered` < `amount` est une erreur de saisie."""
    _require_int(amount_xof, "amount_xof")
    _require_int(tendered_xof, "tendered_xof")
    if tendered_xof < amount_xof:
        raise ValueError("le montant remis est inférieur au montant encaissé")
    return tendered_xof - amount_xof


def format_xof(amount: Xof) -> str:
    """9500 → '9 500' (séparateur de milliers espace, usage ivoirien)."""
    _require_int(amount)
    return f"{amount:,}".replace(",", " ")
