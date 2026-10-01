from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from caisse.models.settings import AppSetting


def get_value(db: Session, key: str, default: Any = None) -> Any:
    """Paramètre métier (table `settings`), ou `default` s'il n'a jamais été créé : une base
    amorcée avant l'ajout d'une clé continue de fonctionner sans relancer `bootstrap`."""
    setting = db.get(AppSetting, key)
    return default if setting is None else setting.value


# Régime TEE (confirmé le 01/10/2026) : pas de TVA, code FNE TVAD
DEFAULT_VAT_RATE = Decimal("0.00")


def default_vat_rate(db: Session) -> Decimal:
    """Taux de TVA des nouveaux produits (`vat.default_rate`, en %)."""
    try:
        return Decimal(str(get_value(db, "vat.default_rate", DEFAULT_VAT_RATE)))
    except InvalidOperation:
        return DEFAULT_VAT_RATE
