"""Agrégats des tableaux de bord : une requête groupée par axe, jamais de boucle par ligne."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from caisse.domain.enums import (
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    StockMovementType,
    StockOutMode,
)
from caisse.models.cash_session import CashSession
from caisse.models.order import Order, OrderItem
from caisse.models.payment import Payment
from caisse.models.stock import StockArticle, StockMovement
from caisse.repositories.stock import SALE_TYPES

# sorties hors ventes : ce qui disparaît du stock sans passer par la caisse
NON_SALE_OUT_TYPES = (
    StockMovementType.LOSS_OUT,
    StockMovementType.INVENTORY_COUNT,
    StockMovementType.ADJUSTMENT,
)

_ZERO = Decimal(0)


def _paid_in(date_from: date, date_to: date) -> ColumnElement[bool]:
    return (
        (Order.status == OrderStatus.PAID)
        & (Order.business_date >= date_from)
        & (Order.business_date <= date_to)
    )


def _value() -> ColumnElement[Decimal]:
    return func.coalesce(func.sum(StockMovement.quantity * StockMovement.unit_cost_xof), _ZERO)


# --- Ventes ------------------------------------------------------------------------------


def sales_by_day(db: Session, date_from: date, date_to: date) -> list[tuple[date, int, int]]:
    """(journée, commandes, chiffre d'affaires)."""
    rows = db.execute(
        select(Order.business_date, func.count(Order.id), func.sum(Order.total_ttc_xof))
        .where(_paid_in(date_from, date_to))
        .group_by(Order.business_date)
        .order_by(Order.business_date)
    )
    return [(d, int(n), int(total or 0)) for d, n, total in rows]


def recipe_cost_by_day(db: Session, date_from: date, date_to: date) -> dict[date, Decimal]:
    """Coût matière net des ventes (sorties - remises en stock), positif."""
    rows = db.execute(
        select(Order.business_date, -_value())
        .select_from(StockMovement)
        .join(Order, Order.id == StockMovement.reference_order_id)
        .where(StockMovement.type.in_(SALE_TYPES), _paid_in(date_from, date_to))
        .group_by(Order.business_date)
    )
    return {d: Decimal(cost) for d, cost in rows}


def sales_by_product(
    db: Session, date_from: date, date_to: date
) -> list[tuple[uuid.UUID, str, str, int, int]]:
    """(produit, nom, catégorie, quantité, chiffre d'affaires) ; libellés figés à la vente."""
    rows = db.execute(
        select(
            OrderItem.product_id,
            func.max(OrderItem.product_name_snapshot),
            func.max(OrderItem.category_snapshot),
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.line_total_xof),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(_paid_in(date_from, date_to), OrderItem.removed_at.is_(None))
        .group_by(OrderItem.product_id)
    )
    return [(pid, name, cat, int(qty), int(total)) for pid, name, cat, qty, total in rows]


def recipe_cost_by_product(db: Session, date_from: date, date_to: date) -> dict[uuid.UUID, Decimal]:
    rows = db.execute(
        select(OrderItem.product_id, -_value())
        .select_from(StockMovement)
        .join(OrderItem, OrderItem.id == StockMovement.reference_order_item_id)
        .join(Order, Order.id == StockMovement.reference_order_id)
        .where(StockMovement.type.in_(SALE_TYPES), _paid_in(date_from, date_to))
        .group_by(OrderItem.product_id)
    )
    return {pid: Decimal(cost) for pid, cost in rows}


def payments_by_method(
    db: Session, date_from: date, date_to: date
) -> list[tuple[PaymentMethod, int, int]]:
    rows = db.execute(
        select(Payment.method, func.count(Payment.id), func.sum(Payment.amount_xof))
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.status == PaymentStatus.CAPTURED, _paid_in(date_from, date_to))
        .group_by(Payment.method)
        .order_by(func.sum(Payment.amount_xof).desc())
    )
    return [(method, int(n), int(total or 0)) for method, n, total in rows]


def cash_sessions(db: Session, date_from: date, date_to: date) -> list[CashSession]:
    return list(
        db.scalars(
            select(CashSession)
            .where(CashSession.business_date >= date_from, CashSession.business_date <= date_to)
            .order_by(CashSession.business_date, CashSession.opened_at)
        )
    )


def non_sale_out_by_mode(
    db: Session, date_from: date, date_to: date
) -> dict[StockOutMode, Decimal]:
    """Valeur sortie hors ventes (pertes, écarts d'inventaire), positive, par mode de suivi."""
    rows = db.execute(
        select(StockArticle.out_mode, -_value())
        .select_from(StockMovement)
        .join(StockArticle, StockArticle.id == StockMovement.article_id)
        .where(
            StockMovement.type.in_(NON_SALE_OUT_TYPES),
            StockMovement.business_date >= date_from,
            StockMovement.business_date <= date_to,
        )
        .group_by(StockArticle.out_mode)
    )
    return {mode: Decimal(value) for mode, value in rows}


# --- Stock -------------------------------------------------------------------------------


def movements_by_article_type(
    db: Session, date_from: date, date_to: date
) -> dict[tuple[uuid.UUID, StockMovementType], tuple[Decimal, Decimal]]:
    """(article, type) → (quantité signée, valeur signée) sur la période."""
    rows = db.execute(
        select(
            StockMovement.article_id,
            StockMovement.type,
            func.sum(StockMovement.quantity),
            _value(),
        )
        .where(StockMovement.business_date >= date_from, StockMovement.business_date <= date_to)
        .group_by(StockMovement.article_id, StockMovement.type)
    )
    return {(aid, t): (Decimal(qty), Decimal(value)) for aid, t, qty, value in rows}


def quantity_after(db: Session, day: date) -> dict[uuid.UUID, Decimal]:
    """Quantité signée des mouvements postérieurs à `day`, par article."""
    rows = db.execute(
        select(StockMovement.article_id, func.sum(StockMovement.quantity))
        .where(StockMovement.business_date > day)
        .group_by(StockMovement.article_id)
    )
    return {aid: Decimal(qty) for aid, qty in rows}


def last_count_dates(db: Session, day: date) -> dict[uuid.UUID, date]:
    rows = db.execute(
        select(StockMovement.article_id, func.max(StockMovement.business_date))
        .where(
            StockMovement.type.in_((StockMovementType.INVENTORY_COUNT, StockMovementType.OPENING)),
            StockMovement.business_date <= day,
        )
        .group_by(StockMovement.article_id)
    )
    return {aid: d for aid, d in rows}
