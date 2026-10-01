import uuid
from datetime import date, datetime

from pydantic import ConfigDict, Field

from caisse.domain.enums import OrderStatus
from caisse.schemas.common import ApiWarning, Schema


class OrderCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"table_id": "…", "guests_count": 4}, {"table_id": None}]}
    )

    table_id: uuid.UUID | None = Field(
        default=None, description="Table servie ; null pour une vente à emporter (comptoir)"
    )
    guests_count: int | None = Field(default=None, ge=1, le=99, description="Nombre de couverts")


class ItemAdd(Schema):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"product_id": "…", "quantity": 2, "note": "bien cuit"}]}
    )

    product_id: uuid.UUID = Field(description="Produit du menu ou produit personnalisé")
    quantity: int = Field(default=1, ge=1, le=999, description="Quantité")
    note: str | None = Field(default=None, max_length=255, description="Précision pour la cuisine")


class ItemUpdate(Schema):
    model_config = ConfigDict(json_schema_extra={"examples": [{"quantity": 3}]})

    quantity: int | None = Field(default=None, ge=1, le=999, description="Nouvelle quantité")
    note: str | None = Field(
        default=None, max_length=255, description="Nouvelle note ; null explicite pour l'effacer"
    )


class CancelOrder(Schema):
    reason: str = Field(min_length=1, max_length=255, description="Motif de l'annulation")


class OrderItemOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la ligne")
    product_id: uuid.UUID = Field(description="Produit vendu")
    name: str = Field(description="Libellé figé à l'ajout", examples=["Poisson braisé"])
    unit_price_xof: int = Field(description="Prix unitaire TTC figé à l'ajout, en XOF")
    quantity: int = Field(description="Quantité")
    line_total_xof: int = Field(description="Total TTC de la ligne, en XOF")
    note: str | None = Field(description="Précision pour la cuisine")
    added_at: datetime = Field(description="Heure d'ajout")


class OrderSummaryOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la commande")
    order_number: str = Field(
        description="Numéro lisible de la journée", examples=["2026-09-24-0042"]
    )
    status: OrderStatus = Field(description="OPEN, PARTIALLY_PAID, PAID, CANCELLED ou REFUNDED")
    business_date: date = Field(description="Journée comptable")
    table_id: uuid.UUID | None = Field(description="Table ; null pour une vente à emporter")
    counter_number: int | None = Field(
        description="« Comptoir n° X » d'une vente à emporter ; null pour une table"
    )
    guests_count: int | None = Field(description="Nombre de couverts")
    total_ttc_xof: int = Field(description="Total TTC, en XOF")
    total_ht_xof: int = Field(description="Total HT, en XOF")
    total_vat_xof: int = Field(description="TVA, en XOF")
    paid_xof: int = Field(description="Déjà encaissé, en XOF")
    due_xof: int = Field(description="Reste dû, en XOF")
    opened_at: datetime = Field(description="Heure d'ouverture")
    paid_at: datetime | None = Field(description="Heure du solde ; null tant que non soldée")
    cancelled_at: datetime | None = Field(description="Heure d'annulation")
    cancelled_reason: str | None = Field(description="Motif d'annulation")


class OrderOut(OrderSummaryOut):
    items: list[OrderItemOut] = Field(
        description="Lignes actives (les lignes retirées n'y sont pas)"
    )


class OrderResult(Schema):
    order: OrderOut = Field(description="Commande complète, totaux recalculés")
    warnings: list[ApiWarning] = Field(default=[], description="Avertissements non bloquants")
