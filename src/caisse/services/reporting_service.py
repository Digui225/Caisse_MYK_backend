"""Tableaux de bord de l'administrateur (01-BACKEND §5.8) : ventes et stock sur une période.

Lecture seule. Le coût matière vient des mouvements de vente (fiches techniques, au coût
moyen du moment de la vente) ; la consommation des articles suivis par inventaire et les
écarts viennent des inventaires et des pertes de la période.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from caisse.domain import stock_rules
from caisse.domain.enums import StockMovementType, StockOutMode
from caisse.errors import ValidationError
from caisse.repositories import reports as reports_repo
from caisse.repositories import stock as stock_repo
from caisse.schemas.reports import (
    SalesCashSession,
    SalesCategory,
    SalesDay,
    SalesPaymentMethod,
    SalesProduct,
    SalesReportOut,
    SalesTotals,
    StockReportArticle,
    StockReportOut,
    StockTotals,
)

MAX_DAYS = 366
_ZERO = Decimal(0)


def _xof(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def check_period(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise ValidationError(
            "La date de début est postérieure à la date de fin.",
            meta={"date_from": str(date_from), "date_to": str(date_to)},
        )
    if (date_to - date_from).days >= MAX_DAYS:
        raise ValidationError(f"Période limitée à {MAX_DAYS} jours.", meta={"max_days": MAX_DAYS})


def sales_report(db: Session, date_from: date, date_to: date) -> SalesReportOut:
    check_period(date_from, date_to)
    days = reports_repo.sales_by_day(db, date_from, date_to)
    cost_by_day = reports_repo.recipe_cost_by_day(db, date_from, date_to)
    products = reports_repo.sales_by_product(db, date_from, date_to)
    cost_by_product = reports_repo.recipe_cost_by_product(db, date_from, date_to)
    recipes = stock_repo.components_by_product(db, [pid for pid, *_ in products])
    non_sale = reports_repo.non_sale_out_by_mode(db, date_from, date_to)

    by_product: list[SalesProduct] = []
    categories: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # qté, CA, coût
    for pid, name, category, quantity, revenue in products:
        cost = _xof(cost_by_product.get(pid, _ZERO))
        by_product.append(
            SalesProduct(
                product_id=pid,
                name=name,
                category=category,
                quantity=quantity,
                revenue_xof=revenue,
                has_recipe=pid in recipes,
                recipe_cost_xof=cost,
                recipe_margin_xof=revenue - cost,
            )
        )
        bucket = categories[category]
        bucket[0] += quantity
        bucket[1] += revenue
        bucket[2] += cost
    by_product.sort(key=lambda p: (-p.revenue_xof, p.name))

    revenue = sum(total for _, _, total in days)
    orders = sum(n for _, n, _ in days)
    recipe_cost = sum(p.recipe_cost_xof for p in by_product)
    consumption = _xof(non_sale.get(StockOutMode.INVENTORY, _ZERO))
    variance = _xof(non_sale.get(StockOutMode.RECIPE, _ZERO))
    totals = SalesTotals(
        revenue_xof=revenue,
        orders_count=orders,
        average_ticket_xof=round(revenue / orders) if orders else 0,
        recipe_cost_xof=recipe_cost,
        recipe_margin_xof=revenue - recipe_cost,
        uncosted_revenue_xof=sum(p.revenue_xof for p in by_product if not p.has_recipe),
        inventory_consumption_xof=consumption,
        stock_variance_xof=variance,
        gross_margin_xof=revenue - recipe_cost - consumption - variance,
    )
    return SalesReportOut(
        date_from=date_from,
        date_to=date_to,
        totals=totals,
        by_day=[
            SalesDay(
                business_date=d,
                orders_count=n,
                revenue_xof=total,
                recipe_cost_xof=_xof(cost_by_day.get(d, _ZERO)),
                recipe_margin_xof=total - _xof(cost_by_day.get(d, _ZERO)),
            )
            for d, n, total in days
        ],
        by_product=by_product,
        by_category=sorted(
            (
                SalesCategory(
                    category=name,
                    quantity=q,
                    revenue_xof=r,
                    recipe_cost_xof=c,
                    recipe_margin_xof=r - c,
                )
                for name, (q, r, c) in categories.items()
            ),
            key=lambda c: (-c.revenue_xof, c.category),
        ),
        by_payment_method=[
            SalesPaymentMethod(method=method, count=n, amount_xof=amount)
            for method, n, amount in reports_repo.payments_by_method(db, date_from, date_to)
        ],
        cash_sessions=[
            SalesCashSession(
                id=s.id,
                business_date=s.business_date,
                status=s.status,
                z_number=s.z_number,
                expected_cash_xof=s.expected_cash_xof,
                counted_cash_xof=s.counted_cash_xof,
                variance_xof=s.variance_xof,
            )
            for s in reports_repo.cash_sessions(db, date_from, date_to)
        ],
    )


def stock_report(db: Session, date_from: date, date_to: date) -> StockReportOut:
    check_period(date_from, date_to)
    period = reports_repo.movements_by_article_type(db, date_from, date_to)
    after = reports_repo.quantity_after(db, date_to)
    counts = reports_repo.last_count_dates(db, date_to)
    moved: set[uuid.UUID] = {aid for aid, _ in period}
    articles = [
        a for a in stock_repo.list_articles(db, is_active=None) if a.is_active or a.id in moved
    ]

    def qty(aid: uuid.UUID, *types: StockMovementType) -> Decimal:
        return sum((period.get((aid, t), (_ZERO, _ZERO))[0] for t in types), _ZERO)

    def value(aid: uuid.UUID, *types: StockMovementType) -> Decimal:
        return sum((period.get((aid, t), (_ZERO, _ZERO))[1] for t in types), _ZERO)

    sale_types = (StockMovementType.SALE_OUT, StockMovementType.RETURN_IN)
    count_types = (StockMovementType.INVENTORY_COUNT, StockMovementType.ADJUSTMENT)
    out_types = (*sale_types, StockMovementType.LOSS_OUT, *count_types)

    rows: list[StockReportArticle] = []
    totals: defaultdict[str, Decimal] = defaultdict(lambda: _ZERO)
    for a in articles:
        closing = a.quantity - after.get(a.id, _ZERO)
        # le stock de départ saisi pendant la période compte dans le début de période
        in_period = sum(
            (
                q
                for (aid, t), (q, _) in period.items()
                if aid == a.id and t != StockMovementType.OPENING
            ),
            _ZERO,
        )
        opening = closing - in_period
        purchased = qty(a.id, StockMovementType.PURCHASE_IN)
        purchases = value(a.id, StockMovementType.PURCHASE_IN)
        consumption_value = -value(a.id, *out_types)
        current_value = stock_rules.value_xof(max(a.quantity, _ZERO), a.avg_cost_xof)
        is_low = stock_rules.is_below_threshold(a.quantity, a.alert_threshold)
        non_sale = -value(a.id, StockMovementType.LOSS_OUT, *count_types)

        totals["stock_value"] += current_value
        totals["purchases"] += purchases
        totals["sales_cost"] += -value(a.id, *sale_types)
        totals["consumption" if a.out_mode == StockOutMode.INVENTORY else "variance"] += non_sale
        totals["low"] += 1 if is_low and a.is_active else 0
        rows.append(
            StockReportArticle(
                article_id=a.id,
                name=a.name,
                category=a.category,
                unit=a.unit,
                out_mode=a.out_mode,
                opening_quantity=float(opening),
                purchased_quantity=float(purchased),
                purchases_xof=_xof(purchases),
                sold_quantity=float(-qty(a.id, *sale_types)),
                loss_quantity=float(-qty(a.id, StockMovementType.LOSS_OUT)),
                count_adjustment_quantity=float(qty(a.id, *count_types)),
                closing_quantity=float(closing),
                consumption_quantity=float(opening + purchased - closing),
                consumption_xof=_xof(consumption_value),
                quantity=float(a.quantity),
                avg_cost_xof=float(a.avg_cost_xof),
                value_xof=current_value,
                alert_threshold=float(a.alert_threshold) if a.alert_threshold is not None else None,
                is_low=is_low,
                last_count_date=counts.get(a.id),
            )
        )
    return StockReportOut(
        date_from=date_from,
        date_to=date_to,
        totals=StockTotals(
            stock_value_xof=_xof(totals["stock_value"]),
            purchases_xof=_xof(totals["purchases"]),
            sales_cost_xof=_xof(totals["sales_cost"]),
            inventory_consumption_xof=_xof(totals["consumption"]),
            stock_variance_xof=_xof(totals["variance"]),
            low_count=int(totals["low"]),
        ),
        articles=rows,
    )
