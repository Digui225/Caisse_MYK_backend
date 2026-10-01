from typing import Any

from sqlalchemy.orm import Session

from caisse.models.settings import AppSetting


def get_value(db: Session, key: str, default: Any = None) -> Any:
    """Paramètre métier (table `settings`), ou `default` s'il n'a jamais été créé : une base
    amorcée avant l'ajout d'une clé continue de fonctionner sans relancer `bootstrap`."""
    setting = db.get(AppSetting, key)
    return default if setting is None else setting.value
