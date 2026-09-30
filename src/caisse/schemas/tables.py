import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

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
        description="FREE : libre ; OCCUPIED : commande active"
    )
    order: BoardOrder | None = Field(description="Commande active de la table, null si libre")


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
