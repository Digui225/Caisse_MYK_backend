from datetime import datetime, timezone
from typing import Any
import httpx
from sqlalchemy.orm import Session

from caisse.domain.payment_rules import format_receipt_text
from caisse.models.order import Order
from caisse.models.payment import Payment
from caisse.models.print_job import PrintJob
from caisse.repositories.print_jobs import PrintJobRepository
from caisse.services.audit_service import AuditService


class PrintingService:
    def __init__(self, db: Session, agent_url: str = "http://127.0.0.1:8090"):
        self.db = db
        self.agent_url = agent_url
        self.repo = PrintJobRepository(db)
        self.audit = AuditService(db)

    def generate_receipt_content(
        self,
        order: Order,
        payments: list[Payment],
        cashier_name: str,
        is_duplicate: bool = False,
    ) -> str:
        restaurant_info = {
            "name": "RESTAURANT MYK",
            "address": "Cocody Riviera Palmeraie · Abidjan",
            "phone": "+225 07 58 00 00 00",
            "ncc": "2104598B",
            "rccm": "CI-ABJ-2024-B-12345",
            "footer": "Merci pour votre confiance ! À très bientôt.",
        }

        order_info = {
            "order_number": order.order_number,
            "table_label": order.table.label if order.table else "Comptoir",
            "guests_count": order.guests_count,
            "cashier_name": cashier_name,
            "date_str": (order.paid_at or datetime.now(timezone.utc)).strftime("%d/%m/%Y %H:%M"),
        }

        items = []
        for it in order.items:
            if it.removed_at is None:
                items.append({
                    "name": it.product_name_snapshot,
                    "quantity": it.quantity,
                    "line_total_xof": it.line_total_xof,
                })

        payment_entries = []
        total_change = 0
        for p in payments:
            payment_entries.append({
                "method": p.method,
                "provider": p.provider,
                "amount_xof": p.amount_xof,
            })
            if p.change_xof:
                total_change += p.change_xof

        totals = {
            "total_ttc_xof": order.total_ttc_xof,
            "total_vat_xof": order.total_vat_xof,
            "vat_rate": 18,
            "change_xof": total_change,
        }

        return format_receipt_text(
            restaurant_info=restaurant_info,
            order_info=order_info,
            items=items,
            payments=payment_entries,
            totals=totals,
            is_duplicate=is_duplicate,
        )

    def create_receipt_job(
        self,
        order: Order,
        payments: list[Payment],
        cashier_name: str,
        open_drawer: bool = False,
        is_duplicate: bool = False,
    ) -> PrintJob:
        content = self.generate_receipt_content(
            order=order,
            payments=payments,
            cashier_name=cashier_name,
            is_duplicate=is_duplicate,
        )

        job = PrintJob(
            order_id=order.id,
            job_type="DUPLICATE" if is_duplicate else "RECEIPT",
            content=content,
            open_drawer=open_drawer,
            cut=True,
            is_duplicate=is_duplicate,
            status="QUEUED",
        )
        self.repo.add(job)
        self.db.flush()

        # Tentative d'envoi synchrone à l'agent d'impression local (mode dégradé transparent)
        self._dispatch_job_to_agent(job)

        return job

    def reprint_ticket(
        self,
        order: Order,
        cashier_name: str,
        user_id: str,
        device_id: str | None = None,
    ) -> PrintJob:
        payments = order.payments or []
        job = self.create_receipt_job(
            order=order,
            payments=payments,
            cashier_name=cashier_name,
            open_drawer=False,  # Strict : jamais d'ouverture tiroir sur duplicata
            is_duplicate=True,
        )

        self.audit.log(
            action="TICKET_REPRINTED",
            entity="ORDER",
            entity_id=order.id,
            user_id=user_id,
            after={"print_job_id": job.id, "is_duplicate": True},
            device_id=device_id,
        )
        self.db.commit()
        return job

    def manual_open_drawer(self, user_id: str, device_id: str | None = None) -> bool:
        success = False
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.post(f"{self.agent_url}/open-drawer")
                if res.status_code == 200:
                    success = True
        except Exception:
            success = False

        self.audit.log(
            action="MANUAL_DRAWER_OPENED",
            entity="CASH_DRAWER",
            entity_id="drawer-01",
            user_id=user_id,
            after={"dispatched": success},
            device_id=device_id,
        )
        self.db.commit()
        return success

    def get_status(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.agent_url}/status")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass

        return {
            "online": False,
            "paper": "unknown",
            "model": "POS-80 Windows Spooler (Déconnecté / Mode file d'attente)",
            "width": 42,
        }

    def _dispatch_job_to_agent(self, job: PrintJob) -> None:
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.post(
                    f"{self.agent_url}/print",
                    json={
                        "content": job.content,
                        "open_drawer": job.open_drawer,
                        "cut": job.cut,
                    },
                )
                if res.status_code in [200, 201]:
                    job.status = "DONE"
                    job.printed_at = datetime.now(timezone.utc)
        except Exception as exc:
            # Mode dégradé : l'agent est injoignable, le job reste QUEUED
            job.error_message = str(exc)
