from abc import ABC, abstractmethod
from typing import Any, NamedTuple


class FiscalCertificationResult(NamedTuple):
    success: bool
    status: str  # "CERTIFIED", "FAILED", "QUEUED"
    invoice_number: str
    qr_url: str | None
    token: str | None
    raw_response: dict[str, Any] | None
    error_message: str | None = None


class FneProviderPort(ABC):
    """Port d'abstraction pour l'émission et certification de Factures Normalisées (DGI CI)."""

    @abstractmethod
    async def submit_invoice(self, payload: dict[str, Any]) -> FiscalCertificationResult:
        """Soumet un payload de facture normalisée pour certification."""
        pass
