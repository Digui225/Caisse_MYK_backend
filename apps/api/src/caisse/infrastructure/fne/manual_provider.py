import json
from datetime import datetime, timezone
from typing import Any

from caisse.domain.fiscal import generate_fne_token, generate_qr_url
from caisse.domain.ports import FiscalCertificationResult, FneProviderPort


class ManualFneProvider(FneProviderPort):
    """Fournisseur FNE Mode Manuel : génère les numéros et empreintes locales pour export CSV/JSON."""

    async def submit_invoice(self, payload: dict[str, Any]) -> FiscalCertificationResult:
        invoice_number = payload.get("invoice_number", "FNE-MANUAL")
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        token = generate_fne_token(payload_bytes)
        qr_url = generate_qr_url(invoice_number, token)

        return FiscalCertificationResult(
            success=True,
            status="MANUAL_EXPORTED",
            invoice_number=invoice_number,
            qr_url=qr_url,
            token=token,
            raw_response={
                "mode": "MANUAL",
                "invoice_number": invoice_number,
                "token": token,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            error_message=None,
        )
