import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any
import httpx
from sqlalchemy.orm import Session

from caisse.domain.payment_rules import (
    format_receipt_text,
    build_esc_pos_bytes,
    ESC_INIT,
    ESC_DRAWER_KICK,
    ESC_CUT_PAPER,
)
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
        from caisse.models.settings import EstablishmentSetting
        setting = self.db.query(EstablishmentSetting).first()

        restaurant_info = {
            "name": (setting.restaurant_name if setting and setting.restaurant_name else "RESTAURANT MYK").upper(),
            "address": setting.address if setting and setting.address else "Cocody Riviera Palmeraie · Abidjan",
            "phone": setting.phone if setting and setting.phone else "+225 07 58 00 00 00",
            "ncc": setting.ncc if setting and setting.ncc else "2104598B",
            "rccm": setting.rccm if setting and setting.rccm else "CI-ABJ-2024-B-12345",
            "footer": setting.receipt_footer if setting and setting.receipt_footer else "Merci de votre visite · A tres bientot !",
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
        total_tendered = 0
        for p in payments:
            payment_entries.append({
                "method": p.method,
                "provider": p.provider,
                "amount_xof": p.amount_xof,
            })
            if p.change_xof:
                total_change += p.change_xof
            if p.tendered_xof:
                total_tendered += p.tendered_xof

        width = 32
        if setting and setting.print_width in [32, 42]:
            width = setting.print_width

        totals = {
            "total_ttc_xof": order.total_ttc_xof,
            "total_vat_xof": order.total_vat_xof,
            "vat_rate": int(setting.default_vat_rate) if setting and setting.default_vat_rate else 18,
            "change_xof": total_change,
            "tendered_xof": total_tendered if total_tendered > 0 else None,
        }

        return format_receipt_text(
            restaurant_info=restaurant_info,
            order_info=order_info,
            items=items,
            payments=payment_entries,
            totals=totals,
            is_duplicate=is_duplicate,
            width=width,
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

    def _send_raw_esc_pos(self, raw_bytes: bytes) -> bool:
        """Envoie des octets bruts ESC/POS directement à l'imprimante thermique."""
        # 1. Sur Linux : priorité absolue à CUPS raw (Xprinter_58) ou port USB direct
        if shutil.which("lpr"):
            for printer_target in ["Xprinter_58", None]:
                cmd = ["lpr", "-o", "raw"] if printer_target is None else ["lpr", "-P", printer_target, "-o", "raw"]
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.communicate(input=raw_bytes, timeout=3.0)
                    if proc.returncode == 0:
                        return True
                except Exception:
                    pass

        try:
            with open("/dev/usb/lp0", "wb") as f:
                f.write(raw_bytes)
                f.flush()
                return True
        except Exception:
            pass

        # 2. Sur Windows ou si CUPS échoue : agent d'impression local port 8090
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.post(
                    f"{self.agent_url}/print",
                    json={"content": raw_bytes.decode("cp850", errors="replace"), "open_drawer": False, "cut": False},
                )
                if res.status_code in [200, 201]:
                    return True
        except Exception:
            pass

        return False

    def manual_open_drawer(self, user_id: str, device_id: str | None = None) -> bool:
        pulse_bytes = ESC_INIT + ESC_DRAWER_KICK
        success = self._send_raw_esc_pos(pulse_bytes)

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

    def print_test_ticket(
        self,
        user_id: str,
        device_id: str | None = None,
        custom_header: str | None = None,
        custom_footer: str | None = None,
        width: int = 32,
    ) -> dict[str, Any]:
        from caisse.models.settings import EstablishmentSetting

        setting = self.db.query(EstablishmentSetting).first()
        restaurant_name = (setting.restaurant_name if setting and setting.restaurant_name else "RESTAURANT MYK").upper()
        address = setting.address if setting and setting.address else "Cocody Riviera Palmeraie · Abidjan"
        phone = setting.phone if setting and setting.phone else "+225 07 58 00 00 00"
        ncc = setting.ncc if setting and setting.ncc else "2104598B"
        rccm = setting.rccm if setting and setting.rccm else "CI-ABJ-2024-B-12345"
        footer = custom_footer or (setting.receipt_footer if setting and setting.receipt_footer else "Merci de votre visite · A tres bientot !")
        welcome = custom_header if custom_header is not None else "Bienvenue au Restaurant MYK"

        restaurant_info = {
            "name": restaurant_name,
            "address": address,
            "phone": phone,
            "ncc": ncc,
            "rccm": rccm,
            "footer": footer,
            "welcome_message": welcome,
        }

        order_info = {
            "order_number": "CMD-0042",
            "table_label": "12",
            "cashier_name": "Marc",
            "date_str": f"{datetime.now().strftime('%d/%m/%Y')} 13:45",
            "fne_number": "FNE-2026-10-01-MYK-0042",
            "fne_qr_url": "https://dgi.gouv.ci/fne/verify/FNE-2026-10-01-MYK-0042",
        }

        items = [
            {"name": "Poulet Braise Entier", "quantity": 1, "line_total_xof": 6500},
            {"name": "Alloco Portion", "quantity": 2, "line_total_xof": 2000},
            {"name": "Jus Bissap Maison", "quantity": 2, "line_total_xof": 2000},
        ]

        payments = [
            {"method": "CASH", "amount_xof": 10500},
        ]

        totals = {
            "subtotal_ht_xof": 8898,
            "total_vat_xof": 1602,
            "vat_rate": 18,
            "total_ttc_xof": 10500,
            "tendered_xof": 15000,
            "change_xof": 4500,
        }

        test_content = format_receipt_text(
            restaurant_info=restaurant_info,
            order_info=order_info,
            items=items,
            payments=payments,
            totals=totals,
            is_duplicate=False,
            width=width,
            welcome_message=welcome,
        )

        raw_bytes = build_esc_pos_bytes(test_content, open_drawer=False, cut=True)
        success = self._send_raw_esc_pos(raw_bytes)

        self.audit.log(
            action="TEST_TICKET_PRINTED",
            entity="PRINTER",
            entity_id="Xprinter_58",
            user_id=user_id,
            after={"success": success, "width": width},
            device_id=device_id,
        )
        self.db.commit()
        return {"status": "PRINTED" if success else "FAILED", "success": success}

    def get_status(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=0.8) as client:
                res = client.get(f"{self.agent_url}/status")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass

        # Détection CUPS ou USB Linux
        if shutil.which("lpstat"):
            try:
                res = subprocess.run(["lpstat", "-p", "Xprinter_58"], capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0:
                    return {
                        "online": True,
                        "paper": "ok",
                        "model": "Xprinter XP-58IIH (USB Direct / CUPS)",
                        "width": 32,
                    }
            except Exception:
                pass

        if os.path.exists("/dev/usb/lp0"):
            return {
                "online": True,
                "paper": "ok",
                "model": "Xprinter XP-58IIH (USB Direct /dev/usb/lp0)",
                "width": 32,
            }

        return {
            "online": False,
            "paper": "unknown",
            "model": "POS-58 ESC/POS (Déconnecté / Mode Outbox)",
            "width": 32,
        }

    def _dispatch_job_to_agent(self, job: PrintJob) -> None:
        raw_bytes = build_esc_pos_bytes(
            content=job.content,
            open_drawer=job.open_drawer,
            cut=job.cut,
        )
        success = self._send_raw_esc_pos(raw_bytes)
        if success:
            job.status = "DONE"
            job.printed_at = datetime.now(timezone.utc)
        else:
            job.error_message = "Agent d'impression ou port USB injoignable"
