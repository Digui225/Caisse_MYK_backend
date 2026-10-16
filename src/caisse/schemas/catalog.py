import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator

from caisse.domain.enums import CategoryKind
from caisse.schemas.common import Schema


class CategoryOut(Schema):
    id: uuid.UUID = Field(description="Identifiant de la catégorie")
    name: str = Field(description="Nom affiché", examples=["Poissons"])
    kind: CategoryKind = Field(description="Nature : FOOD (plat), DRINK (boisson), OTHER")
    sort_order: int = Field(description="Ordre d'affichage (croissant)")
    color: str | None = Field(description="Couleur du bouton, en hexadécimal", examples=["#B45309"])
    is_active: bool = Field(description="Visible dans le menu")
    fiscal_group: str = Field(
        description="Groupe du récapitulatif fiscal journalier (FNE)", examples=["POISSONS"]
    )


class ProductOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du produit")
    name: str = Field(description="Nom complet", examples=["Jus de bissap"])
    short_name: str = Field(
        description="Nom court pour les boutons et le ticket", examples=["Bissap"]
    )
    category_id: uuid.UUID = Field(description="Catégorie du produit")
    price_xof: int = Field(description="Prix TTC, en francs CFA entiers", examples=[1000])
    vat_rate: float = Field(description="Taux de TVA, en pourcentage", examples=[0.0])
    track_stock: bool = Field(
        default=False, description="Le produit a une fiche technique : sa vente déstocke"
    )
    stock_quantity: float | None = Field(
        default=None,
        description="Portions encore vendables avec le stock actuel ; null sans fiche technique",
    )
    is_active: bool = Field(description="Vendable")
    is_custom: bool = Field(description="Produit créé à la volée pendant une commande")
    color: str | None = Field(description="Couleur du bouton, en hexadécimal")
    sort_order: int = Field(description="Ordre d'affichage dans sa catégorie")


class CustomProductCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"name": "Poisson capitaine 1 kg", "price_xof": 9000, "category_id": "…"}]
        }
    )

    name: str = Field(min_length=1, max_length=120, description="Libellé de l'article libre")
    price_xof: int = Field(ge=0, description="Prix TTC, en francs CFA entiers")
    category_id: uuid.UUID = Field(description="Catégorie (sert au récapitulatif fiscal)")
    vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=99,
        decimal_places=2,
        description="Taux de TVA, en % ; défaut : paramètre `vat.default_rate` (0 % en régime TEE)",
    )


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


_COLOR = r"^#[0-9A-Fa-f]{6}$"


class CategoryCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Poissons", "kind": "FOOD", "fiscal_group": "POISSONS", "color": "#B45309"}
            ]
        }
    )

    name: str = Field(min_length=1, max_length=60, description="Nom unique (sans la casse)")
    kind: CategoryKind = Field(description="FOOD (plat), DRINK (boisson), OTHER")
    fiscal_group: str = Field(
        default="AUTRES",
        min_length=1,
        max_length=40,
        description="Groupe du récapitulatif fiscal : POISSONS, VIANDES, JUS, EAU, PLATS, AUTRES…",
    )
    color: str | None = Field(default=None, pattern=_COLOR, description="Couleur du bouton")
    sort_order: int | None = Field(
        default=None, ge=0, description="Ordre d'affichage ; défaut : après la dernière"
    )

    _strip_text = field_validator("name", "fiscal_group", mode="before")(_strip)


class CategoryUpdate(Schema):
    """Seuls les champs envoyés changent."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    kind: CategoryKind | None = None
    fiscal_group: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = Field(default=None, pattern=_COLOR, description="null : sans couleur")
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(
        default=None, description="false : refusé tant que la catégorie a des produits actifs"
    )

    _strip_text = field_validator("name", "fiscal_group", mode="before")(_strip)


class ProductCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "category_id": "…",
                    "name": "Plat poulet",
                    "short_name": "Plat poulet",
                    "price_xof": 3000,
                }
            ]
        }
    )

    category_id: uuid.UUID = Field(description="Catégorie active")
    name: str = Field(min_length=1, max_length=120, description="Nom unique dans le menu")
    short_name: str | None = Field(
        default=None, min_length=1, max_length=20, description="Libellé ticket ; défaut : le nom"
    )
    price_xof: int = Field(ge=0, description="Prix TTC, en francs CFA entiers")
    vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=99,
        decimal_places=2,
        description="Taux de TVA, en % ; défaut : paramètre `vat.default_rate`",
    )
    color: str | None = Field(default=None, pattern=_COLOR, description="Couleur du bouton")
    sort_order: int | None = Field(
        default=None, ge=0, description="Ordre dans la catégorie ; défaut : en dernier"
    )
    sku: str | None = Field(default=None, max_length=40, description="Code article, unique")

    _strip_text = field_validator("name", "short_name", "sku", mode="before")(_strip)


class ProductUpdate(Schema):
    """Seuls les champs envoyés changent. Le prix se modifie par `PATCH /products/{id}/price`."""

    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    short_name: str | None = Field(default=None, min_length=1, max_length=20)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=99, decimal_places=2)
    color: str | None = Field(default=None, pattern=_COLOR, description="null : sans couleur")
    sort_order: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=40, description="null : sans code")
    is_active: bool | None = Field(default=None, description="false : retiré du menu")

    _strip_text = field_validator("name", "short_name", "sku", mode="before")(_strip)


class PriceUpdate(Schema):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"price_xof": 3500, "reason": "Hausse du prix du poulet"}]}
    )

    price_xof: int = Field(ge=0, description="Nouveau prix TTC")
    reason: str = Field(min_length=1, max_length=255, description="Motif, obligatoire")

    _strip_text = field_validator("reason", mode="before")(_strip)


class PriceChangeOut(Schema):
    old_price_xof: int = Field(description="Ancien prix")
    new_price_xof: int = Field(description="Nouveau prix")
    reason: str = Field(description="Motif")
    changed_by: uuid.UUID = Field(description="Auteur")
    changed_at: datetime = Field(description="Date du changement")
