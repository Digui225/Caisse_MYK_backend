from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol


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


@dataclass(frozen=True, slots=True)
class FneItemRef:
    """Article tel que certifié par la FNE : son `id` est requis pour un avoir."""

    id: str
    description: str
    quantity: int
    reference: str | None


@dataclass(frozen=True, slots=True)
class FneResult:
    external_number: str  # `reference` FNE, ex. 1304777N26000000023
    qr_payload: str  # `token` : URL de vérification à imprimer en QR
    invoice_id: str | None  # `invoice.id`, requis pour un avoir (absent des réponses d'avoir)
    items: tuple[FneItemRef, ...]
    amount_ttc: int | None
    vat_amount: int | None
    balance_sticker: int | None
    sticker_warning: bool
    raw: dict[str, Any]


class FneError(Exception):
    """Échec d'un appel FNE. Le type dit si un renvoi automatique est sans danger."""

    def __init__(self, message: str, *, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class FneRejectedError(FneError):
    """4xx (hors 401) : données refusées, correction nécessaire. Rien n'a été certifié."""


class FneAuthError(FneError):
    """401 : clé API invalide. Rien n'a été certifié ; renvoi possible une fois la clé corrigée."""


class FneUnavailableError(FneError):
    """La requête n'a pas été traitée (connexion impossible, 502/503) : renvoi sans danger."""


class FneUncertainError(FneError):
    """La requête a pu être traitée (délai dépassé après envoi, 500, 504, réponse illisible) :
    **jamais** de renvoi automatique, l'API n'étant pas idempotente (PLAN-FNE D5)."""


class FneProvider(Protocol):
    def sign(self, payload: dict[str, Any], *, timeout: float) -> FneResult: ...

    def refund(self, invoice_id: str, payload: dict[str, Any], *, timeout: float) -> FneResult: ...

