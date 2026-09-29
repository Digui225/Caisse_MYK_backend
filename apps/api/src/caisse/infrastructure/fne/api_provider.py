import json
import logging
from typing import Any
import httpx

from caisse.domain.ports import FiscalCertificationResult, FneProviderPort

logger = logging.getLogger(__name__)


class ApiFneProvider(FneProviderPort):
    """Fournisseur REST API FNE direct (DGI Côte d'Ivoire) avec timeout strict de 4 secondes."""

    def __init__(self, endpoint_url: str, api_key: str, timeout_seconds: float = 4.0):
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def submit_invoice(self, payload: dict[str, Any]) -> FiscalCertificationResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(self.endpoint_url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return FiscalCertificationResult(
                        success=True,
                        status="CERTIFIED",
                        invoice_number=data.get("fne_number", payload.get("invoice_number", "")),
                        qr_url=data.get("qr_url"),
                        token=data.get("token"),
                        raw_response=data,
                        error_message=None,
                    )
                else:
                    return FiscalCertificationResult(
                        success=False,
                        status="FAILED",
                        invoice_number=payload.get("invoice_number", ""),
                        qr_url=None,
                        token=None,
                        raw_response=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text},
                        error_message=f"HTTP {resp.status_code}: {resp.text}",
                    )
        except httpx.TimeoutException:
            logger.warning("FNE DGI direct API timed out after %s seconds -> repli outbox", self.timeout_seconds)
            return FiscalCertificationResult(
                success=False,
                status="QUEUED",
                invoice_number=payload.get("invoice_number", ""),
                qr_url=None,
                token=None,
                raw_response=None,
                error_message=f"Timeout after {self.timeout_seconds}s",
            )
        except Exception as exc:
            logger.error("FNE DGI direct API communication error: %s", exc)
            return FiscalCertificationResult(
                success=False,
                status="FAILED",
                invoice_number=payload.get("invoice_number", ""),
                qr_url=None,
                token=None,
                raw_response=None,
                error_message=str(exc),
            )
