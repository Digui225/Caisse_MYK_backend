import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from caisse.domain.enums import OrderStatus
from caisse.schemas.common import Schema


class TableOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la table")
    label: str = Field(description="Libellé affiché", examples=["12"])
    zone: str = Field(description="Zone de la salle", examples=["Terrasse"])
    seats: int = Field(description="Nombre de couverts")
    sort_order: int = Field(description="Ordre d'affichage sur le plan")
    is_active: bool = Field(description="Table en service")


class BoardOrder(Schema):
    id: uuid.UUID = Field(description="Identifiant de la commande")
    order_number: str = Field(description="Numéro lisible de la journée")
    note_label: str | None = Field(description="Étiquette sur la table (« Note 1 »…)")
    total_ttc_xof: int = Field(description="Total TTC, en francs CFA", examples=[9000])
    paid_xof: int = Field(description="Montant déjà encaissé, en francs CFA", examples=[0])
    guests_count: int | None = Field(description="Nombre de couverts saisi")
    opened_at: datetime = Field(description="Heure d'ouverture de la commande")
    status: OrderStatus = Field(description="OPEN ou PARTIALLY_PAID (commande active)")


class BoardTable(Schema):
    id: uuid.UUID = Field(description="Identifiant de la table")
    label: str = Field(description="Libellé affiché")
    zone: str = Field(description="Zone de la salle")
    seats: int = Field(description="Nombre de couverts")
    status: Literal["FREE", "OCCUPIED"] = Field(
        description="FREE : libre ; OCCUPIED : au moins une commande active"
    )
    order: BoardOrder | None = Field(
        description="La plus ancienne commande active, null si libre (voir `orders`)"
    )
    orders: list[BoardOrder] = Field(
        description="Toutes les commandes actives de la table (partage), de la plus ancienne "
        "à la plus récente"
    )
    total_ttc_xof: int = Field(description="Total TTC des commandes actives de la table")


class BoardSummary(Schema):
    revenue_today_xof: int = Field(description="Chiffre d'affaires encaissé de la journée, en XOF")
    orders_count: int = Field(description="Nombre de commandes soldées de la journée")
    open_orders: int = Field(description="Nombre de commandes encore ouvertes")


class TableBoard(Schema):
    business_date: date | None = Field(
        description="Journée comptable de la session ouverte ; null si aucune session"
    )
    summary: BoardSummary = Field(description="Résumé de la journée")
    tables: list[BoardTable] = Field(description="Tables actives et leur état")


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class TableCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"label": "12", "zone": "Terrasse", "seats": 4}]}
    )

    label: str = Field(min_length=1, max_length=20, description="Libellé unique (sans la casse)")
    zone: str = Field(default="Salle", min_length=1, max_length=40, description="Zone")
    seats: int = Field(default=4, ge=1, le=50, description="Nombre de couverts")
    sort_order: int | None = Field(
        default=None, ge=0, description="Ordre sur le plan ; défaut : en dernier"
    )

    _strip_text = field_validator("label", "zone", mode="before")(_strip)


class TableUpdate(Schema):
    """Seuls les champs envoyés changent."""

    label: str | None = Field(default=None, min_length=1, max_length=20)
    zone: str | None = Field(default=None, min_length=1, max_length=40)
    seats: int | None = Field(default=None, ge=1, le=50)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(
        default=None, description="false : refusé tant que la table a des commandes en cours"
    )

    _strip_text = field_validator("label", "zone", mode="before")(_strip)
