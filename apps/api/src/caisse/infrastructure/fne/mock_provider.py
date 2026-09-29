import json
from datetime import datetime, timezone
from typing import Any

from caisse.domain.fiscal import generate_fne_token, generate_qr_url
from caisse.domain.ports import FiscalCertificationResult, FneProviderPort


class MockFneProvider(FneProviderPort):
    """Fournisseur Mock FNE : simule une certification instantanée réussie pour les tests et dev."""

    def __init__(self, should_fail: bool = False, latency_s: float = 0.0):
        self.should_fail = should_fail
        self.latency_s = latency_s

    async def submit_invoice(self, payload: dict[str, Any]) -> FiscalCertificationResult:
        import asyncio
        if self.latency_s > 0:
            await asyncio.sleep(self.latency_s)

        if self.should_fail:
            return FiscalCertificationResult(
                success=False,
                status="FAILED",
                invoice_number=payload.get("invoice_number", "FNE-FAILED"),
                qr_url=None,
                token=None,
                raw_response={"error": "DGI server unreachable"},
                error_message="Simulated DGI server failure",
            )

        invoice_number = payload.get("invoice_number") or f"FNE-2104598B-{datetime.now(timezone.utc).strftime('%Y%m%d')}-MOCK"
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        token = generate_fne_token(payload_bytes)
        qr_url = generate_qr_url(invoice_number, token)

        return FiscalCertificationResult(
            success=True,
            status="CERTIFIED",
            invoice_number=invoice_number,
            qr_url=qr_url,
            token=token,
            raw_response={
                "status": "APPROVED",
                "certified_at": datetime.now(timezone.utc).isoformat(),
                "fne_number": invoice_number,
                "token": token,
                "qr_url": qr_url,
            },
            error_message=None,
        )
