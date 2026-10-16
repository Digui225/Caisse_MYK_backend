"""Configuration de la salle (03-CONTRAT-API §4.4) : création, modification, désactivation."""

import uuid

from sqlalchemy.orm import Session

from caisse.errors import NotFoundError, TableHasActiveOrdersError, TableLabelExistsError
from caisse.models.table import RestaurantTable
from caisse.repositories import orders as orders_repo
from caisse.repositories import tables as tables_repo
from caisse.schemas.tables import TableCreate, TableUpdate
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext


def create_table(
    db: Session, body: TableCreate, *, actor_id: uuid.UUID, ctx: RequestContext
) -> RestaurantTable:
    existing = tables_repo.get_by_label(db, body.label)
    if existing is not None:
        raise TableLabelExistsError(meta={"table_id": str(existing.id)})
    table = RestaurantTable(
        label=body.label,
        zone=body.zone,
        seats=body.seats,
        sort_order=body.sort_order
        if body.sort_order is not None
        else tables_repo.next_sort_order(db),
        is_active=True,
    )
    db.add(table)
    db.flush()
    audit_service.log(
        db,
        "table.create",
        ctx=ctx,
        user_id=actor_id,
        entity="table",
        entity_id=table.id,
        after=body.model_dump(),
    )
    db.commit()
    return table


def update_table(
    db: Session,
    table_id: uuid.UUID,
    body: TableUpdate,
    *,
    actor_id: uuid.UUID,
    ctx: RequestContext,
) -> RestaurantTable:
    """Mise à jour partielle. Une table qui porte des commandes en cours ne se désactive pas :
    les solder ou les annuler d'abord."""
    table = tables_repo.get_for_update(db, table_id)
    if table is None:
        raise NotFoundError(meta={"table_id": str(table_id)})
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    label = changes.get("label")
    if label is not None and label.lower() != table.label.lower():
        existing = tables_repo.get_by_label(db, label)
        if existing is not None:
            raise TableLabelExistsError(meta={"table_id": str(existing.id)})
    if changes.get("is_active") is False and table.is_active:
        active = orders_repo.active_for_table(db, table.id)
        if active:
            raise TableHasActiveOrdersError(
                meta={"table_id": str(table.id), "order_ids": [str(o.id) for o in active]}
            )
    before = {key: getattr(table, key) for key in changes}
    for key, value in changes.items():
        setattr(table, key, value)
    audit_service.log(
        db,
        "table.update",
        ctx=ctx,
        user_id=actor_id,
        entity="table",
        entity_id=table.id,
        before=before,
        after=changes,
    )
    db.commit()
    return table
