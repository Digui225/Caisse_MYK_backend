from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from caisse.deps import Admin, DbSession
from caisse.schemas.reports import SalesReportOut, StockReportOut
from caisse.services import reporting_service, stock_service

router = APIRouter(prefix="/reports", tags=["Rapports"])

DateFrom = Annotated[
    date | None, Query(description="Première journée incluse ; défaut : la date de fin")
]
DateTo = Annotated[
    date | None, Query(description="Dernière journée incluse ; défaut : journée en cours")
]


def _period(db: DbSession, date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or stock_service.business_day(db)
    return date_from or end, end


@router.get("/sales", response_model=SalesReportOut, summary="Tableau des ventes")
def sales(
    _: Admin, db: DbSession, date_from: DateFrom = None, date_to: DateTo = None
) -> SalesReportOut:
    """Commandes soldées de la période (journée comptable) : chiffre d'affaires, coût matière
    des fiches techniques, marges, détail par jour, produit, catégorie et moyen de paiement,
    écarts de caisse des sessions.

    `gross_margin_xof` retire aussi la consommation des articles suivis par inventaire et les
    écarts constatés : elle n'est juste qu'avec des inventaires réguliers.

    Erreurs : `403 INSUFFICIENT_PRIVILEGE` (ADMIN), `422 VALIDATION_ERROR` (début après la
    fin, période de plus de 366 jours).
    """
    start, end = _period(db, date_from, date_to)
    return reporting_service.sales_report(db, start, end)


@router.get("/stock", response_model=StockReportOut, summary="Tableau du stock")
def stock(
    _: Admin, db: DbSession, date_from: DateFrom = None, date_to: DateTo = None
) -> StockReportOut:
    """Par article : stock de début et de fin de période, entrées, ventes, pertes, écart
    d'inventaire, consommation, valeur et alerte. Pour un article à fiche, l'écart
    d'inventaire compare le stock théorique (après les ventes) au stock compté.

    Erreurs : `403 INSUFFICIENT_PRIVILEGE` (ADMIN), `422 VALIDATION_ERROR`.
    """
    start, end = _period(db, date_from, date_to)
    return reporting_service.stock_report(db, start, end)
