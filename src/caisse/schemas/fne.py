import uuid
from datetime import date, datetime

from pydantic import ConfigDict, Field

from caisse.domain.enums import FneDocumentType, FneStatus, PaymentMethod
from caisse.domain.fne import FneTemplate
from caisse.schemas.common import ApiWarning, Schema


class FneIssueIn(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"template": "B2C"}, {"template": "B2B", "customer_id": "…"}]
        }
    )

    template: FneTemplate = Field(
        default=FneTemplate.B2C,
        description="B2C particulier · B2B entreprise (NCC obligatoire) · B2G administration · "
        "B2F client à l'international",
    )
    customer_id: uuid.UUID | None = Field(
        default=None, description="Client entreprise (`/customers`) ; obligatoire sauf en B2C"
    )
    payment_method: PaymentMethod | None = Field(
        default=None,
        description="Moyen de paiement déclaré ; défaut : celui du plus gros montant encaissé",
    )


class FneRefundLineIn(Schema):
    order_item_id: uuid.UUID = Field(description="Ligne de la commande à reprendre")
    quantity: int = Field(ge=1, le=999, description="Quantité reprise")


class FneRefundIn(Schema):
    items: list[FneRefundLineIn] = Field(min_length=1, description="Lignes de l'avoir")


class FneResolveIn(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"is_certified": True, "external_number": "1304777N26000000023"},
                {"is_certified": False},
            ]
        }
    )

    is_certified: bool = Field(
        description="Constat dans l'espace FNE : la facture a-t-elle été certifiée (numérotée) ?"
    )
    external_number: str | None = Field(
        default=None, max_length=64, description="N° FNE relevé ; obligatoire si certifiée"
    )
    qr_payload: str | None = Field(
        default=None, description="Lien de vérification relevé dans l'espace FNE (facultatif)"
    )


class FneDocumentOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du document")
    type: FneDocumentType = Field(description="FNE (vente) ou REFUND (avoir)")
    status: FneStatus = Field(
        description="PENDING, SUBMITTING, CERTIFIED, QUEUED, FAILED ou MANUAL"
    )
    is_uncertain: bool = Field(
        description="Issue inconnue (délai dépassé, erreur serveur FNE) : vérifier dans l'espace "
        "FNE puis `POST /fne/documents/{id}/resolve`. Jamais renvoyé automatiquement"
    )
    template: FneTemplate | None = Field(description="Type de client")
    order_id: uuid.UUID | None = Field(description="Commande facturée")
    internal_reference: str | None = Field(
        description="N° de la commande", examples=["2026-09-24-0042"]
    )
    customer_id: uuid.UUID | None = Field(description="Client entreprise")
    parent_document_id: uuid.UUID | None = Field(description="Avoir : FNE d'origine")
    external_number: str | None = Field(
        description="N° FNE attribué par la DGI", examples=["1304777N26000000023"]
    )
    qr_payload: str | None = Field(
        description="Lien de vérification DGI : contenu du QR code, et page A4 imprimable"
    )
    fne_amount_ttc_xof: int | None = Field(description="Total TTC calculé par la FNE")
    certified_at: datetime | None = Field(description="Date de certification")
    attempts: int = Field(description="Nombre d'envois à la FNE")
    last_error: str | None = Field(description="Dernière erreur (diagnostic, non affichable)")
    next_retry_at: datetime | None = Field(description="Prochain renvoi automatique (QUEUED)")
    created_at: datetime = Field(description="Création du document")


class FneDocumentResult(Schema):
    document: FneDocumentOut = Field(description="Document fiscal")
    warnings: list[ApiWarning] = Field(
        default=[],
        description="`FNE_REJECTED` (refus DGI), `FNE_UNCERTAIN`, `FNE_QUEUED`, "
        "`FNE_STICKER_LOW` (stock de stickers bas)",
    )


class FnePendingCountOut(Schema):
    pending: int = Field(description="Documents en attente d'une action")
    uncertain: int = Field(description="Dont : issue inconnue, à vérifier dans l'espace FNE")
    failed: int = Field(description="Dont : refusés par la DGI")


class FiscalGroupLine(Schema):
    group: str = Field(description="Groupe fiscal", examples=["POISSONS"])
    quantity: int = Field(description="Quantité vendue")
    amount_xof: int = Field(description="Montant TTC, en XOF")


class FneDailySummaryOut(Schema):
    business_date: date = Field(description="Journée comptable")
    paid_orders: int = Field(description="Commandes soldées")
    gross_ttc_xof: int = Field(description="Chiffre d'affaires TTC des commandes soldées")
    certified_orders: int = Field(description="Commandes couvertes par une FNE certifiée")
    certified_ttc_xof: int = Field(description="TTC des commandes couvertes par une FNE")
    pending_documents: int = Field(description="FNE de la journée en attente")
    by_fiscal_group: list[FiscalGroupLine] = Field(description="Ventes par groupe fiscal")
