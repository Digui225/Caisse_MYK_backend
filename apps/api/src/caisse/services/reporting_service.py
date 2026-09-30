from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from caisse.models.cash_session import CashSession
from caisse.models.fne import FneDocument
from caisse.models.order import Order, OrderItem
from caisse.models.payment import Payment
from caisse.models.stock import StockItem
from caisse.schemas.report import DashboardKpiResponse, PaymentMethodSplit, TopProductReport


class ReportingService:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_kpis(self, business_date_str: Optional[str] = None) -> DashboardKpiResponse:
        """Calcule les indicateurs clés de performance (KPIs) pour le tableau de bord direction."""
        if not business_date_str:
            business_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Commandes du jour
        all_orders = self.db.query(Order).all()

        daily_orders = []
        for o in all_orders:
            match = False
            if o.created_at and o.created_at.strftime("%Y-%m-%d") == business_date_str:
                match = True
            elif o.cash_session and str(o.cash_session.business_date) == business_date_str:
                match = True
            if match:
                daily_orders.append(o)

        total_orders = len(daily_orders)
        settled_orders_list = [o for o in daily_orders if o.status == "PAID" or o.due_xof == 0]
        settled_orders = len(settled_orders_list)

        total_sales_ttc = sum(o.total_ttc_xof for o in settled_orders_list)
        total_sales_ht = sum(o.total_ht_xof for o in settled_orders_list)
        total_sales_vat = sum(o.total_vat_xof for o in settled_orders_list)
        avg_basket = (total_sales_ttc // settled_orders) if settled_orders > 0 else 0

        # 2. Ventilation des paiements
        all_payments = self.db.query(Payment).all()
        settled_order_ids_set = {o.id for o in settled_orders_list}
        daily_payments = [
            p for p in all_payments
            if (p.created_at and p.created_at.strftime("%Y-%m-%d") == business_date_str)
            or (p.order_id in settled_order_ids_set)
        ]

        pay_map: dict[tuple[str, str | None], dict[str, int]] = {}
        for p in daily_payments:
            key = (p.method, p.provider)
            if key not in pay_map:
                pay_map[key] = {"count": 0, "total": 0}
            pay_map[key]["count"] += 1
            pay_map[key]["total"] += p.amount_xof

        payments_by_method = [
            PaymentMethodSplit(
                method=m,
                provider=prov,
                count=data["count"],
                total_amount_xof=data["total"],
            )
            for (m, prov), data in pay_map.items()
        ]

        # 3. Top Produits vendus (sur les commandes réglées)
        settled_order_ids = [o.id for o in settled_orders_list]
        top_products: list[TopProductReport] = []
        if settled_order_ids:
            daily_items = (
                self.db.query(OrderItem)
                .filter(
                    OrderItem.order_id.in_(settled_order_ids),
                    OrderItem.removed_at.is_(None),
                )
                .all()
            )

            prod_map: dict[str, dict[str, Any]] = {}
            for item in daily_items:
                pid = item.product_id or "UNKNOWN"
                if pid not in prod_map:
                    prod_map[pid] = {
                        "name": item.product_name_snapshot,
                        "category": item.category_snapshot,
                        "qty": 0.0,
                        "revenue": 0,
                    }
                prod_map[pid]["qty"] += float(item.quantity)
                prod_map[pid]["revenue"] += item.line_total_xof

            sorted_prods = sorted(prod_map.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]
            top_products = [
                TopProductReport(
                    product_id=pid,
                    product_name=data["name"],
                    category_name=data.get("category"),
                    quantity_sold=data["qty"],
                    total_revenue_xof=data["revenue"],
                )
                for pid, data in sorted_prods
            ]

        # 4. Sessions actives
        active_sessions_count = (
            self.db.query(func.count(CashSession.id))
            .filter(CashSession.status == "OPEN")
            .scalar()
            or 0
        )

        # 5. Articles en alerte stock
        low_stock_items_count = (
            self.db.query(func.count(StockItem.id))
            .filter(StockItem.quantity <= StockItem.alert_threshold)
            .scalar()
            or 0
        )

        # 6. FNE KPIs
        fne_certified_count = (
            self.db.query(func.count(FneDocument.id))
            .filter(FneDocument.status.in_(["CERTIFIED", "MANUAL_EXPORTED"]))
            .scalar()
            or 0
        )

        fne_pending_count = (
            self.db.query(func.count(FneDocument.id))
            .filter(FneDocument.status.in_(["QUEUED", "PENDING", "FAILED"]))
            .scalar()
            or 0
        )

        return DashboardKpiResponse(
            business_date=business_date_str,
            total_orders=total_orders,
            settled_orders=settled_orders,
            total_sales_ttc_xof=total_sales_ttc,
            total_sales_ht_xof=total_sales_ht,
            total_sales_vat_xof=total_sales_vat,
            average_basket_xof=avg_basket,
            payments_by_method=payments_by_method,
            top_products=top_products,
            active_sessions_count=active_sessions_count,
            low_stock_items_count=low_stock_items_count,
            fne_certified_count=fne_certified_count,
            fne_pending_count=fne_pending_count,
        )
