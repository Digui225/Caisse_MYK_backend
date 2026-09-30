from fastapi import APIRouter

from caisse.deps import CurrentUser, DbSession
from caisse.repositories import tables as tables_repo
from caisse.schemas.common import Page
from caisse.schemas.tables import BoardOrder, BoardSummary, BoardTable, TableBoard, TableOut
from caisse.services import auth_service

router = APIRouter(prefix="/tables", tags=["Tables"])


@router.get("", response_model=Page[TableOut], summary="Lister les tables")
def list_tables(_: CurrentUser, db: DbSession) -> Page[TableOut]:
    """Tables actives de la salle, dans l'ordre d'affichage."""
    return Page(items=[TableOut.model_validate(t) for t in tables_repo.list_tables(db)])


@router.get("/board", response_model=TableBoard, summary="Plan de salle (écran d'accueil)")
def table_board(_: CurrentUser, db: DbSession) -> TableBoard:
    """Écran d'accueil en un seul appel : état de chaque table et résumé de la journée.

    Sans session de caisse ouverte, `business_date` est null et les compteurs sont à 0.
    """
    session = auth_service.current_open_session(db)
    business_date = session.business_date if session else None
    revenue, orders_count, open_orders = (
        tables_repo.day_summary(db, business_date) if business_date else (0, 0, 0)
    )
    tables = [
        BoardTable(
            id=table.id,
            label=table.label,
            zone=table.zone,
            seats=table.seats,
            status="OCCUPIED" if order else "FREE",
            order=BoardOrder.model_validate(order) if order else None,
        )
        for table, order in tables_repo.board_rows(db)
    ]
    return TableBoard(
        business_date=business_date,
        summary=BoardSummary(
            revenue_today_xof=revenue, orders_count=orders_count, open_orders=open_orders
        ),
        tables=tables,
    )
