import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator

from caisse.domain.enums import PaymentMethod
from caisse.schemas.common import Schema
from caisse.schemas.customers import NCC_PATTERN


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# --- Paramètres --------------------------------------------------------------------------


class WalkInClient(Schema):
    company_name: str = Field(max_length=160, description="Nom du client de passage sur la FNE")
    phone: str = Field(max_length=32, description="Téléphone exigé par la FNE")
    email: str = Field(max_length=160, description="E-mail exigé par la FNE")


class SettingsOut(Schema):
    restaurant_name: str = Field(description="Nom en tête du ticket")
    address: str = Field(description="Adresse en tête du ticket")
    phone: str = Field(description="Téléphone en tête du ticket")
    ncc: str = Field(description="N° de compte contribuable de l'établissement")
    rccm: str = Field(description="N° RCCM")
    receipt_footer: str = Field(description="Pied du ticket")
    default_vat_rate: float = Field(description="TVA des nouveaux produits, en % (0 : régime TEE)")
    cash_rounding_xof: int = Field(description="Arrondi des espèces, en XOF")
    cash_denominations_xof: list[int] = Field(description="Coupures du comptage de clôture")
    payment_methods: list[PaymentMethod] = Field(description="Moyens proposés, dans l'ordre")
    screen_lock_timeout_seconds: int = Field(description="Verrouillage de l'écran ; 0 : jamais")
    fne_point_of_sale: str = Field(description="Point de vente, tel que dans l'espace FNE")
    fne_establishment: str = Field(description="Établissement, tel que dans l'espace FNE")
    fne_walk_in_client: WalkInClient = Field(description="Client de passage des FNE B2C")


class SettingsUpdate(Schema):
    """Seuls les champs envoyés changent."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"restaurant_name": "RESTAURANT CHEZ SYLLA PLUS", "phone": "0700000000"}]
        }
    )

    restaurant_name: str | None = Field(default=None, min_length=1, max_length=80)
    address: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    ncc: str | None = Field(
        default=None, description="7 chiffres + 1 lettre, ou vide (espaces et minuscules acceptés)"
    )
    rccm: str | None = Field(default=None, max_length=40)
    receipt_footer: str | None = Field(default=None, max_length=255)
    default_vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=99,
        decimal_places=2,
        description="Pour les nouveaux produits ; ne change pas les produits existants",
    )
    cash_rounding_xof: int | None = Field(default=None, ge=1, le=100)
    cash_denominations_xof: list[int] | None = Field(default=None, min_length=1, max_length=20)
    payment_methods: list[PaymentMethod] | None = Field(default=None, min_length=1)
    screen_lock_timeout_seconds: int | None = Field(default=None, ge=0, le=3600)
    fne_point_of_sale: str | None = Field(default=None, max_length=80)
    fne_establishment: str | None = Field(default=None, max_length=160)
    fne_walk_in_client: WalkInClient | None = None

    _strip_text = field_validator(
        "restaurant_name",
        "address",
        "phone",
        "rccm",
        "receipt_footer",
        "fne_point_of_sale",
        "fne_establishment",
        mode="before",
    )(_strip)

    @field_validator("ncc", mode="before")
    @classmethod
    def _normalize_ncc(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.replace(" ", "").upper()
            if value and not re.fullmatch(NCC_PATTERN, value):
                raise ValueError("NCC : 7 chiffres + 1 lettre")
        return value

    @field_validator("cash_denominations_xof")
    @classmethod
    def _denominations(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(v <= 0 for v in value) or len(set(value)) != len(value):
            raise ValueError("coupures positives et distinctes")
        return sorted(value, reverse=True)

    @field_validator("payment_methods")
    @classmethod
    def _methods(cls, value: list[PaymentMethod] | None) -> list[PaymentMethod] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("moyen de paiement en double")
        return value


# --- Caisses -----------------------------------------------------------------------------


class OpenSessionInfo(Schema):
    id: uuid.UUID = Field(description="Session non clôturée")
    business_date: date = Field(description="Journée comptable")
    opened_by: str = Field(description="Nom de qui l'a ouverte")
    opened_at: datetime = Field(description="Heure d'ouverture")


class CashRegisterOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la caisse (pour POST /cash-sessions)")
    name: str = Field(description="Nom", examples=["Caisse 1"])
    is_active: bool = Field(description="Caisse en service")
    open_session: OpenSessionInfo | None = Field(description="Session en cours, null si fermée")


class CashRegisterCreate(Schema):
    name: str = Field(min_length=1, max_length=60, description="Nom unique (sans la casse)")

    _strip_text = field_validator("name", mode="before")(_strip)


class CashRegisterUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    is_active: bool | None = Field(
        default=None, description="false : refusé tant qu'une session y est ouverte"
    )

    _strip_text = field_validator("name", mode="before")(_strip)
