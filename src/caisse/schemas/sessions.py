import uuid
from datetime import date, datetime

from pydantic import Field

from caisse.domain.enums import CashMovementType, CashSessionStatus, PaymentMethod
from caisse.schemas.common import Schema


class OpenSessionIn(Schema):
    cash_register_id: uuid.UUID = Field(description="Caisse à ouvrir")
    opening_float_xof: int = Field(ge=0, description="Fonds de caisse initial, en XOF")
    business_date: date | None = Field(
        default=None, description="Journée comptable ; défaut : date du jour"
    )
    confirm_business_date: bool = Field(
        default=False,
        description="Confirme l'ouverture malgré une session déjà clôturée ce jour-là",
    )


class MovementIn(Schema):
    type: CashMovementType = Field(description="IN (entrée) ou OUT (sortie)")
    amount_xof: int = Field(gt=0, description="Montant du mouvement, en XOF")
    reason: str = Field(min_length=1, max_length=255, description="Motif du mouvement")


class CloseSessionIn(Schema):
    counted_breakdown: dict[str, int] = Field(
        description='Comptage par dénomination, ex. {"1000": 14, "500": 20}'
    )
    notes: str | None = Field(default=None, max_length=500, description="Remarques de clôture")


class MovementOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du mouvement")
    type: CashMovementType = Field(description="IN (entrée) ou OUT (sortie)")
    amount_xof: int = Field(description="Montant du mouvement, en XOF")
    reason: str = Field(description="Motif du mouvement")
    created_at: datetime = Field(description="Heure du mouvement")


class CashSessionOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la session")
    cash_register_id: uuid.UUID = Field(description="Caisse concernée")
    status: CashSessionStatus = Field(description="OPEN, CLOSING ou CLOSED")
    business_date: date = Field(description="Journée comptable de la session")
    opening_float_xof: int = Field(description="Fonds de caisse initial, en XOF")
    opened_at: datetime = Field(description="Heure d'ouverture")
    closed_at: datetime | None = Field(description="Heure de clôture ; null si encore ouverte")
    z_number: int | None = Field(description="Numéro de Z ; null tant que non clôturée")
    counted_cash_xof: int | None = Field(description="Espèces comptées à la clôture")
    expected_cash_xof: int | None = Field(description="Espèces théoriques à la clôture")
    variance_xof: int | None = Field(description="Écart compté - théorique")
    notes: str | None = Field(description="Remarques de clôture")


class MovementResult(Schema):
    movement: MovementOut = Field(description="Mouvement créé")
    session: CashSessionOut = Field(description="Session à jour")


class PaymentMethodTotal(Schema):
    method: PaymentMethod = Field(description="Moyen de paiement")
    amount_xof: int = Field(description="Montant encaissé sur ce moyen, en XOF")
    count: int = Field(description="Nombre de paiements")


class FiscalGroupTotal(Schema):
    group: str = Field(description="Groupe fiscal (récap FNE)", examples=["POISSONS"])
    quantity: int = Field(description="Quantité vendue")
    amount_xof: int = Field(description="Montant TTC vendu sur ce groupe, en XOF")


class Controls(Schema):
    cancelled_orders: int = Field(description="Nombre de commandes annulées")
    removed_items: int = Field(description="Nombre de lignes retirées")
    reprints: int = Field(description="Nombre de ré-impressions")


class SessionTotals(Schema):
    gross_ttc_xof: int = Field(description="Chiffre d'affaires TTC encaissé, en XOF")
    vat_xof: int = Field(description="TVA collectée, en XOF")
    orders_count: int = Field(description="Nombre de commandes soldées")
    by_payment_method: list[PaymentMethodTotal] = Field(description="Ventilation par moyen")
    by_fiscal_group: list[FiscalGroupTotal] = Field(description="Ventilation par groupe fiscal")
    controls: Controls = Field(description="Compteurs de contrôle")


class XReportOut(Schema):
    session_id: uuid.UUID = Field(description="Session concernée")
    business_date: date = Field(description="Journée comptable")
    expected_cash_xof: int = Field(description="Espèces théoriques à l'instant du rapport")
    totals: SessionTotals = Field(description="Agrégats de la session, à date")


class ZReportOut(Schema):
    z_number: int = Field(description="Numéro de Z, séquence par caisse")
    business_date: date = Field(description="Journée comptable")
    expected_cash_xof: int = Field(description="Espèces théoriques")
    counted_cash_xof: int = Field(description="Espèces comptées")
    variance_xof: int = Field(description="Écart compté - théorique")
    totals: SessionTotals = Field(description="Agrégats figés de la session")
    print_job_id: uuid.UUID | None = Field(
        default=None, description="Ticket Z en file d'impression ; null tant que non disponible"
    )
