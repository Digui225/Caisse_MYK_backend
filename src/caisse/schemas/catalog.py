import uuid

from pydantic import Field

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
    vat_rate: float = Field(description="Taux de TVA, en pourcentage", examples=[18.0])
    track_stock: bool = Field(description="Le stock de ce produit est suivi")
    stock_quantity: float | None = Field(
        default=None, description="Quantité en stock ; null si le stock n'est pas suivi"
    )
    is_active: bool = Field(description="Vendable")
    is_custom: bool = Field(description="Produit créé à la volée pendant une commande")
    color: str | None = Field(description="Couleur du bouton, en hexadécimal")
    sort_order: int = Field(description="Ordre d'affichage dans sa catégorie")
