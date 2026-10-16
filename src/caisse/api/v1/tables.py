import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from caisse.deps import Admin, Ctx, CurrentUser, DbSession
from caisse.repositories import tables as tables_repo
from caisse.schemas.common import Page
from caisse.schemas.tables import (
    BoardOrder,
    BoardSummary,
    BoardTable,
    TableBoard,
    TableCreate,
    TableOut,
    TableUpdate,
)
from caisse.services import auth_service, table_service

router = APIRouter(prefix="/tables", tags=["Tables"])

TableId = Annotated[uuid.UUID, Path(description="Identifiant de la table")]


@router.get("", response_model=Page[TableOut], summary="Lister les tables")
def list_tables(
    _: CurrentUser,
    db: DbSession,
    is_active: Annotated[
        bool | None, Query(description="true (défaut) : en service ; false : désactivées")
    ] = True,
) -> Page[TableOut]:
    """Tables de la salle, dans l'ordre d'affichage."""
    tables = tables_repo.list_tables(db, is_active=is_active)
    return Page(items=[TableOut.model_validate(t) for t in tables])


@router.get("/board", response_model=TableBoard, summary="Plan de salle (écran d'accueil)")
def table_board(_: CurrentUser, db: DbSession) -> TableBoard:
    """Écran d'accueil en un seul appel : état de chaque table et résumé de la journée.

    Une table partagée porte plusieurs commandes actives (`orders`) ; `order` reste la plus
    ancienne, pour les écrans qui n'en affichent qu'une. Sans session de caisse ouverte,
    `business_date` est null et les compteurs sont à 0.
    """
    session = auth_service.current_open_session(db)
    business_date = session.business_date if session else None
    revenue, orders_count, open_orders = (
        tables_repo.day_summary(db, business_date) if business_date else (0, 0, 0)
    )
    tables = []
    for table, orders in tables_repo.board_rows(db):
        board_orders = [BoardOrder.model_validate(o) for o in orders]
        tables.append(
            BoardTable(
                id=table.id,
                label=table.label,
                zone=table.zone,
                seats=table.seats,
                status="OCCUPIED" if orders else "FREE",
                order=board_orders[0] if board_orders else None,
                orders=board_orders,
                total_ttc_xof=sum(o.total_ttc_xof for o in orders),
            )
        )
    return TableBoard(
        business_date=business_date,
        summary=BoardSummary(
            revenue_today_xof=revenue, orders_count=orders_count, open_orders=open_orders
        ),
        tables=tables,
    )


@router.post(
    "", response_model=TableOut, status_code=status.HTTP_201_CREATED, summary="Créer une table"
)
def create_table(body: TableCreate, admin: Admin, db: DbSession, ctx: Ctx) -> TableOut:
    """Réservé à l'ADMIN. Erreurs : `409 TABLE_LABEL_EXISTS` (`meta.table_id`),
    `422 VALIDATION_ERROR`."""
    return TableOut.model_validate(table_service.create_table(db, body, actor_id=admin.id, ctx=ctx))


@router.patch("/{table_id}", response_model=TableOut, summary="Modifier une table")
def update_table(
    table_id: TableId, body: TableUpdate, admin: Admin, db: DbSession, ctx: Ctx
) -> TableOut:
    """Réservé à l'ADMIN. Seuls les champs envoyés changent ; `is_active: true` remet la
    table en service.

    Erreurs : `404 NOT_FOUND`, `409 TABLE_LABEL_EXISTS`, `409 TABLE_HAS_ACTIVE_ORDERS`
    (désactivation d'une table occupée : `meta.order_ids`).
    """
    table = table_service.update_table(db, table_id, body, actor_id=admin.id, ctx=ctx)
    return TableOut.model_validate(table)


@router.delete("/{table_id}", response_model=TableOut, summary="Désactiver une table")
def delete_table(table_id: TableId, admin: Admin, db: DbSession, ctx: Ctx) -> TableOut:
    """Suppression logique (`is_active: false`) : l'historique des commandes reste lisible.
    Réservé à l'ADMIN. Erreurs : `404 NOT_FOUND`, `409 TABLE_HAS_ACTIVE_ORDERS`."""
    table = table_service.update_table(
        db, table_id, TableUpdate(is_active=False), actor_id=admin.id, ctx=ctx
    )
    return TableOut.model_validate(table)
