from typing import Any
import math


def calculate_vat_split(total_ttc_xof: int, vat_rate: float | int | Any = 18.0) -> tuple[int, int]:
    """Calcule la ventilation HT et TVA depuis un montant TTC en entier XOF.
    
    Règle métier ADR-04 :
    - Le TTC fait foi.
    - HT = round(TTC / (1 + taux))
    - TVA = TTC - HT
    """
    if total_ttc_xof <= 0:
        return 0, 0
    rate_factor = 1.0 + (float(vat_rate) / 100.0)
    ht_xof = round(total_ttc_xof / rate_factor)
    vat_xof = total_ttc_xof - ht_xof
    return ht_xof, vat_xof


def calculate_change(tendered_xof: int | None, amount_due_xof: int) -> int:
    """Calcule le rendu monnaie en XOF."""
    if tendered_xof is None or tendered_xof <= amount_due_xof:
        return 0
    return tendered_xof - amount_due_xof
