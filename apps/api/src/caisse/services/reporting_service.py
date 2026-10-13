from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from caisse.models.cash_session import CashSession
from caisse.models.fne import FneDocument
from caisse.models.order import Order, OrderItem
from caisse.models.payment import Payment
from caisse.models.stock import StockItem
from caisse.schemas.report import (
    CashierSalesResponse,
    DashboardKpiResponse,
    HourlySalesItem,
    PaymentMethodSplit,
    TopProductReport,
)


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

        open_orders_list = [o for o in daily_orders if o.status in ("OPEN", "PARTIALLY_PAID")]
        open_orders = len(open_orders_list)

        active_tables_set = {o.table_id for o in open_orders_list if o.table_id is not None}
        active_tables_count = len(active_tables_set)

        from caisse.models.table import RestaurantTable
        total_tables_count = (
            self.db.query(func.count(RestaurantTable.id))
            .filter(RestaurantTable.is_active == True)
            .scalar()
            or 14
        )

        open_dine_in_count = sum(1 for o in open_orders_list if o.table_id is not None)
        open_takeaway_count = sum(1 for o in open_orders_list if o.table_id is None)

        dine_in_orders_count = open_dine_in_count if open_orders > 0 else sum(1 for o in daily_orders if o.table_id is not None and o.status != "CANCELLED")
        takeaway_orders_count = open_takeaway_count if open_orders > 0 else sum(1 for o in daily_orders if o.table_id is None and o.status != "CANCELLED")

        total_sales_ttc = sum(o.total_ttc_xof for o in settled_orders_list)
        total_sales_ht = sum(o.total_ht_xof for o in settled_orders_list)
        total_sales_vat = sum(o.total_vat_xof for o in settled_orders_list)
        avg_basket = (total_sales_ttc // settled_orders) if settled_orders > 0 else 0

        # Ventes horaires réelles
        hourly_map: dict[str, dict[str, int]] = {}
        for o in settled_orders_list:
            dt = o.paid_at or o.opened_at or o.created_at
            if dt:
                h_str = dt.strftime("%H") + "h"
                if h_str not in hourly_map:
                    hourly_map[h_str] = {"total_sales_xof": 0, "orders_count": 0}
                hourly_map[h_str]["total_sales_xof"] += o.total_ttc_xof
                hourly_map[h_str]["orders_count"] += 1

        hourly_sales = [
            HourlySalesItem(
                hour=h,
                total_sales_xof=data["total_sales_xof"],
                orders_count=data["orders_count"],
            )
            for h, data in sorted(hourly_map.items())
        ]

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

        # 6. FNE KPIs (filtrés sur la journée sélectionnée)
        daily_order_ids_set = {o.id for o in daily_orders}
        all_fne_docs = self.db.query(FneDocument).all()
        daily_fne_docs = [
            d
            for d in all_fne_docs
            if (d.created_at and d.created_at.strftime("%Y-%m-%d") == business_date_str)
            or (d.certified_at and d.certified_at.strftime("%Y-%m-%d") == business_date_str)
            or (d.order_id and d.order_id in daily_order_ids_set)
        ]

        fne_certified_count = sum(
            1 for d in daily_fne_docs if d.status in ("CERTIFIED", "MANUAL_EXPORTED")
        )

        fne_pending_count = sum(
            1 for d in daily_fne_docs if d.status in ("QUEUED", "PENDING", "FAILED")
        )

        # 7. Statut réel de clôture de caisse
        from caisse.models.user import User
        from caisse.schemas.report import ClosingStatusResponse

        open_session = (
            self.db.query(CashSession)
            .filter(CashSession.status == "OPEN")
            .first()
        )

        latest_closed_session = (
            self.db.query(CashSession)
            .filter(CashSession.status == "CLOSED")
            .order_by(CashSession.closed_at.desc())
            .first()
        )

        closing_status: ClosingStatusResponse
        if open_session:
            closing_status = ClosingStatusResponse(
                is_closed=False,
                session_id=open_session.id,
            )
        elif latest_closed_session:
            closed_by_name = None
            if latest_closed_session.closed_by_user_id:
                u = self.db.query(User).filter(User.id == latest_closed_session.closed_by_user_id).first()
                if u:
                    closed_by_name = u.full_name
            closing_status = ClosingStatusResponse(
                is_closed=True,
                closed_at=latest_closed_session.closed_at.isoformat() if latest_closed_session.closed_at else None,
                closed_by_name=closed_by_name,
                session_id=latest_closed_session.id,
                z_number=latest_closed_session.z_number,
            )
        else:
            closing_status = ClosingStatusResponse(
                is_closed=True,
                closed_at=None,
                closed_by_name=None,
            )

        # 8. Ventes par caissier
        cashier_map: dict[str, dict[str, Any]] = {}
        for o in settled_orders_list:
            user_obj = o.closed_by or o.opened_by
            cashier_name = user_obj.full_name if user_obj else None
            if not cashier_name and o.closed_by_user_id:
                u = self.db.query(User).filter(User.id == o.closed_by_user_id).first()
                if u:
                    cashier_name = u.full_name
            if not cashier_name and o.opened_by_user_id:
                u = self.db.query(User).filter(User.id == o.opened_by_user_id).first()
                if u:
                    cashier_name = u.full_name
            if not cashier_name and open_session:
                sess_user = open_session.opened_by or (
                    self.db.query(User).filter(User.id == open_session.opened_by_user_id).first()
                    if open_session.opened_by_user_id else None
                )
                if sess_user:
                    cashier_name = sess_user.full_name

            cashier_name = cashier_name or "Caissier"
            if cashier_name not in cashier_map:
                cashier_map[cashier_name] = {
                    "cashier_name": cashier_name,
                    "orders_count": 0,
                    "total_sales_ttc_xof": 0,
                }
            cashier_map[cashier_name]["orders_count"] += 1
            cashier_map[cashier_name]["total_sales_ttc_xof"] += o.total_ttc_xof

        # Si aucune commande réglée mais qu'une session est ouverte, afficher le caissier de la session
        if not cashier_map and open_session:
            sess_user = open_session.opened_by or (
                self.db.query(User).filter(User.id == open_session.opened_by_user_id).first()
                if open_session.opened_by_user_id else None
            )
            name = sess_user.full_name if sess_user else "Caissier en service"
            cashier_map[name] = {
                "cashier_name": name,
                "orders_count": 0,
                "total_sales_ttc_xof": 0,
            }

        sales_by_cashier = [
            CashierSalesResponse(
                cashier_name=data["cashier_name"],
                orders_count=data["orders_count"],
                total_sales_ttc_xof=data["total_sales_ttc_xof"],
            )
            for data in sorted(cashier_map.values(), key=lambda x: x["total_sales_ttc_xof"], reverse=True)
        ]

        return DashboardKpiResponse(
            business_date=business_date_str,
            total_orders=total_orders,
            settled_orders=settled_orders,
            open_orders=open_orders,
            active_tables_count=active_tables_count,
            total_tables_count=total_tables_count,
            dine_in_orders_count=dine_in_orders_count,
            takeaway_orders_count=takeaway_orders_count,
            total_sales_ttc_xof=total_sales_ttc,
            total_sales_ht_xof=total_sales_ht,
            total_sales_vat_xof=total_sales_vat,
            average_basket_xof=avg_basket,
            payments_by_method=payments_by_method,
            top_products=top_products,
            hourly_sales=hourly_sales,
            active_sessions_count=active_sessions_count,
            low_stock_items_count=low_stock_items_count,
            fne_certified_count=fne_certified_count,
            fne_pending_count=fne_pending_count,
            closing_status=closing_status,
            sales_by_cashier=sales_by_cashier,
        )

