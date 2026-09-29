import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from fastapi import status

from caisse.domain.fiscal import build_fne_payload, generate_fne_number
from caisse.domain.ports import FneProviderPort
from caisse.errors import CaisseException
from caisse.infrastructure.fne.mock_provider import MockFneProvider
from caisse.models.customer import Customer
from caisse.models.fne import FneDocument
from caisse.models.order import Order
from caisse.models.outbox import OutboxEvent
from caisse.repositories.customers import CustomerRepository
from caisse.repositories.fne import FneRepository
from caisse.repositories.orders import OrderRepository
from caisse.repositories.outbox import OutboxRepository
from caisse.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class FneService:
    def __init__(
        self,
        db: Session,
        provider: Optional[FneProviderPort] = None,
    ):
        self.db = db
        self.fne_repo = FneRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.order_repo = OrderRepository(db)
        self.outbox_repo = OutboxRepository(db)
        self.audit = AuditService(db)
        self.provider = provider or MockFneProvider()

    async def create_and_submit_fne_for_order(
        self,
        order_id: str,
        customer_id: Optional[str] = None,
    ) -> FneDocument:
        """Génère le document FNE, tente la certification synchrone bornée (<=4s), et enregistre l'outbox si besoin."""
        existing = self.fne_repo.get_by_order_id(order_id)
        if existing:
            return existing

        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise CaisseException(
                code="ORDER_NOT_FOUND",
                title="Commande introuvable",
                detail=f"Aucune commande trouvée avec l'ID {order_id}.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if order.status != "PAID" and order.due_xof > 0:
            raise CaisseException(
                code="ORDER_NOT_SETTLED",
                title="Commande non soldée",
                detail=f"Impossible d'émettre une facture normalisée pour une commande non soldée (solde dû: {order.due_xof} XOF).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        buyer_info = None
        if customer_id:
            cust = self.customer_repo.get_by_id(customer_id)
            if cust:
                buyer_info = {
                    "name": cust.name,
                    "ncc": cust.ncc,
                    "phone": cust.phone,
                    "email": cust.email,
                }

        seller_info = {
            "name": "RESTAURANT MYK",
            "ncc": "2104598B",
            "rccm": "CI-ABJ-2024-B-12345",
            "tax_regime": "REEL_NORMAL",
            "address": "Abidjan, Côte d'Ivoire",
        }

        items = []
        for it in order.items:
            if it.removed_at is not None:
                continue
            items.append({
                "name": it.product_name_snapshot,
                "quantity": it.quantity,
                "unit_price_xof": it.unit_price_xof,
                "line_total_xof": it.line_total_xof,
                "vat_rate": float(it.vat_rate),
            })

        payments = []
        for p in getattr(order, "payments", []):
            payments.append({
                "method": p.method,
                "amount_xof": p.amount_xof,
                "provider": getattr(p, "provider", None),
                "reference": getattr(p, "reference", None),
            })

        totals = {
            "total_ht_xof": order.total_ht_xof,
            "total_vat_xof": order.total_vat_xof,
            "total_ttc_xof": order.total_ttc_xof,
        }

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seq = self.fne_repo.get_next_sequence_for_date(today_str)
        fne_number = generate_fne_number(today_str, seq, ncc=seller_info["ncc"])

        payload = build_fne_payload(
            seller_info=seller_info,
            order_number=order.order_number,
            items=items,
            payments=payments,
            totals=totals,
            buyer_info=buyer_info,
            document_type="FNE",
        )
        payload["invoice_number"] = fne_number

        fne_doc = FneDocument(
            order_id=order.id,
            customer_id=customer_id,
            document_type="FNE",
            status="QUEUED",
            invoice_number=fne_number,
            payload=payload,
        )
        self.fne_repo.add(fne_doc)

        try:
            res = await self.provider.submit_invoice(payload)
            if res.success:
                fne_doc.status = res.status
                fne_doc.qr_url = res.qr_url
                fne_doc.fne_token = res.token
                fne_doc.response_payload = res.raw_response
                fne_doc.certified_at = datetime.now(timezone.utc)
                fne_doc.submitted_at = datetime.now(timezone.utc)
            else:
                fne_doc.status = "QUEUED" if res.status == "QUEUED" else "FAILED"
                fne_doc.error_message = res.error_message
                fne_doc.response_payload = res.raw_response
                fne_doc.retry_count += 1
                
                outbox_evt = OutboxEvent(
                    event_type="FNE_CERTIFICATION",
                    aggregate_type="FneDocument",
                    aggregate_id=fne_doc.id,
                    payload={"fne_document_id": fne_doc.id, "payload": payload},
                    status="PENDING",
                )
                self.outbox_repo.add(outbox_evt)
        except Exception as exc:
            logger.warning("FNE provider exception: %s. Document will remain QUEUED in outbox.", exc)
            fne_doc.status = "QUEUED"
            fne_doc.error_message = str(exc)
            outbox_evt = OutboxEvent(
                event_type="FNE_CERTIFICATION",
                aggregate_type="FneDocument",
                aggregate_id=fne_doc.id,
                payload={"fne_document_id": fne_doc.id, "payload": payload},
                status="PENDING",
            )
            self.outbox_repo.add(outbox_evt)

        self.db.flush()
        return fne_doc

    async def retry_document(self, fne_id: str) -> FneDocument:
        fne_doc = self.fne_repo.get_by_id(fne_id)
        if not fne_doc:
            raise CaisseException(
                code="FNE_DOCUMENT_NOT_FOUND",
                title="Document FNE introuvable",
                detail=f"Aucun document FNE avec l'ID {fne_id}.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if fne_doc.status == "CERTIFIED":
            return fne_doc

        res = await self.provider.submit_invoice(fne_doc.payload)
        fne_doc.retry_count += 1
        if res.success:
            fne_doc.status = res.status
            fne_doc.qr_url = res.qr_url
            fne_doc.fne_token = res.token
            fne_doc.response_payload = res.raw_response
            fne_doc.certified_at = datetime.now(timezone.utc)
            fne_doc.error_message = None
        else:
            fne_doc.status = "FAILED" if res.status == "FAILED" else "QUEUED"
            fne_doc.error_message = res.error_message
            fne_doc.response_payload = res.raw_response

        self.db.flush()
        return fne_doc

    def export_documents_csv(
        self,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        docs = self.fne_repo.list_documents(
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=5000,
        )

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "ID",
            "Numero_Facture",
            "Date_Emission",
            "Statut",
            "Client_Nom",
            "Client_NCC",
            "Total_HT_XOF",
            "Total_TVA_XOF",
            "Total_TTC_XOF",
            "Token_FNE",
            "QR_URL",
        ])

        for doc in docs:
            payload = doc.payload or {}
            buyer = payload.get("buyer", {})
            totals = payload.get("totals", {})
            writer.writerow([
                doc.id,
                doc.invoice_number or "",
                doc.created_at.isoformat() if doc.created_at else "",
                doc.status,
                buyer.get("name", ""),
                buyer.get("ncc", ""),
                totals.get("total_ht_xof", 0),
                totals.get("total_vat_xof", 0),
                totals.get("total_ttc_xof", 0),
                doc.fne_token or "",
                doc.qr_url or "",
            ])

        return output.getvalue()
