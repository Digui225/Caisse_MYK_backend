"""Données minimales de toute installation : caisse n° 1 et paramètres métier par défaut."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.models.cash_session import CashRegister
from caisse.models.settings import AppSetting

# À compléter avec le client (bloquant n° 4 du README : mentions légales, TVA, arrondi).
DEFAULT_SETTINGS: dict[str, Any] = {
    "receipt.header": {
        "name": "[NOM DU RESTAURANT]",
        "address": "[Adresse]",
        "phone": "[Téléphone]",
        "ncc": "",
        "rccm": "",
    },
    "receipt.footer": "Merci de votre visite",
    "vat.default_rate": "18.00",
    "cash.rounding_xof": 5,
    "cash.denominations_xof": [10000, 5000, 2000, 1000, 500, 250, 200, 100, 50, 25, 10, 5],
    "fne.mode": "manual",
    "ui.lock_after_seconds": 120,
}


def ensure_defaults(db: Session, register_name: str = "Caisse 1") -> None:
    if db.scalar(select(CashRegister).limit(1)) is None:
        db.add(CashRegister(name=register_name, printer_config={}))
    existing = set(db.scalars(select(AppSetting.key)))
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.add(AppSetting(key=key, value=value))
