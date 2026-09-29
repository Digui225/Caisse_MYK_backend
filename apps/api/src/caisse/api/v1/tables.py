from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user
from caisse.models.user import User
from caisse.schemas.tables import TableResponse, TableBoardResponse
from caisse.services.table_service import TableService

router = APIRouter(prefix="/tables", tags=["Tables & Salle"])


@router.get("", response_model=list[TableResponse], summary="Lister les tables configurées")
async def list_tables(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TableResponse]:
    service = TableService(db)
    return service.list_tables()


@router.get("/board", response_model=TableBoardResponse, summary="Vue agrégée temps réel de la salle")
async def get_table_board(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TableBoardResponse:
    service = TableService(db)
    return service.get_table_board()
