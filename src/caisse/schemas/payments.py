import uuid
from datetime import datetime
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from caisse.domain.enums import MobileMoneyProvider, PaymentMethod, PaymentStatus
from caisse.schemas.common import Schema


class PaymentCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"method": "CASH", "amount_xof": 5000, "tendered_xof": 10000},
                {
                    "method": "MOBILE_MONEY",
                    "provider": "WAVE",
                    "amount_xof": 4500,
                    "reference": "TX8812",
                },
            ]
        }
    )

    method: PaymentMethod = Field(description="Moyen de paiement (voir `GET /payment-methods`)")
    amount_xof: int = Field(
        gt=0, le=100_000_000, description="Montant imputé à l'addition, au plus le reste dû"
    )
    tendered_xof: int | None = Field(
        default=None,
        ge=0,
        description="Espèces uniquement : somme remise par le client (rendu = remis - montant)",
    )
    provider: MobileMoneyProvider | None = Field(
        default=None, description="Mobile Money uniquement, obligatoire : opérateur"
    )
    reference: str | None = Field(
        default=None, max_length=64, description="N° de transaction (Mobile Money, carte…)"
    )

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.tendered_xof is not None:
            if self.method != PaymentMethod.CASH:
                raise ValueError("tendered_xof n'est accepté que pour les espèces")
            if self.tendered_xof < self.amount_xof:
                raise ValueError("tendered_xof doit être supérieur ou égal à amount_xof")
        if self.method == PaymentMethod.MOBILE_MONEY and self.provider is None:
            raise ValueError("provider obligatoire pour le Mobile Money")
        if self.method != PaymentMethod.MOBILE_MONEY and self.provider is not None:
            raise ValueError("provider n'est accepté que pour le Mobile Money")
        return self


class PaymentOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du paiement")
    method: PaymentMethod = Field(description="Moyen de paiement")
    provider: str | None = Field(description="Opérateur Mobile Money")
    amount_xof: int = Field(description="Montant imputé à l'addition, en XOF")
    tendered_xof: int | None = Field(description="Espèces remises")
    change_xof: int = Field(description="Monnaie rendue")
    reference: str | None = Field(description="N° de transaction")
    status: PaymentStatus = Field(description="CAPTURED, ou VOIDED si annulé")
    created_at: datetime = Field(description="Heure d'encaissement")
    voided_at: datetime | None = Field(description="Heure d'annulation")
    void_reason: str | None = Field(description="Motif d'annulation")


class PaymentMethodOut(Schema):
    method: PaymentMethod = Field(description="Code à envoyer dans `method`")
    label: str = Field(description="Libellé du bouton", examples=["Espèces"])
    gives_change: bool = Field(description="Saisie de la somme remise et rendu monnaie")
    providers: list[MobileMoneyProvider] = Field(
        description="Opérateurs à proposer (non vide : `provider` obligatoire)"
    )
