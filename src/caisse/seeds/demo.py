"""Jeu de démonstration (développement uniquement). Mêmes données que les fixtures MSW du front."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.domain.enums import CategoryKind
from caisse.models.catalog import Category, Product
from caisse.models.stock import StockItem
from caisse.repositories import settings as settings_repo

# (catégorie, kind, groupe fiscal, couleur, [(nom, libellé ticket, prix, suivi stock)])
DEMO_MENU: list[tuple[str, CategoryKind, str, str, list[tuple[str, str, int, bool]]]] = [
    (
        "Poissons",
        CategoryKind.FOOD,
        "POISSONS",
        "#B45309",
        [
            ("Poisson braisé", "Poisson braisé", 3500, False),
            ("Carpe braisée", "Carpe braisée", 4000, False),
            ("Sosso braisé", "Sosso braisé", 5000, False),
        ],
    ),
    (
        "Viandes",
        CategoryKind.FOOD,
        "VIANDES",
        "#9F1239",
        [
            ("Poulet braisé", "Poulet braisé", 4000, False),
            ("Brochettes de boeuf", "Brochettes boeuf", 2000, False),
        ],
    ),
    (
        "Accompagnements",
        CategoryKind.FOOD,
        "PLATS",
        "#65A30D",
        [
            ("Attiéké", "Attiéké", 1000, False),
            ("Alloco", "Alloco", 1000, False),
            ("Riz blanc", "Riz blanc", 500, False),
        ],
    ),
    (
        "Jus",
        CategoryKind.DRINK,
        "JUS",
        "#EA580C",
        [
            ("Jus de bissap", "Bissap", 1000, True),
            ("Jus de gingembre", "Gingembre", 1000, True),
        ],
    ),
    (
        "Sucreries",
        CategoryKind.DRINK,
        "JUS",
        "#2563EB",
        [
            ("Sucrerie 33cl", "Sucrerie 33cl", 500, True),
        ],
    ),
    (
        "Eau",
        CategoryKind.DRINK,
        "EAU",
        "#0891B2",
        [
            ("Eau minérale 50cl", "Eau 50cl", 500, True),
            ("Eau minérale 1,5L", "Eau 1,5L", 1000, True),
        ],
    ),
]


def load_demo_menu(db: Session) -> int:
    """Idempotent : ne crée que ce qui manque. Retourne le nombre de produits créés."""
    created = 0
    vat_rate = settings_repo.default_vat_rate(db)
    for cat_order, (cat_name, kind, group, color, products) in enumerate(DEMO_MENU):
        category = db.scalar(select(Category).where(Category.name == cat_name))
        if category is None:
            category = Category(
                name=cat_name, kind=kind, fiscal_group=group, color=color, sort_order=cat_order
            )
            db.add(category)
            db.flush()
        for prod_order, (name, short, price, track) in enumerate(products):
            if db.scalar(select(Product).where(Product.name == name)) is not None:
                continue
            product = Product(
                category_id=category.id,
                name=name,
                short_name=short,
                price_xof=price,
                track_stock=track,
                sort_order=prod_order,
                vat_rate=vat_rate,
                color=color,
            )
            db.add(product)
            db.flush()
            if track:
                db.add(
                    StockItem(
                        product_id=product.id, quantity=Decimal(48), alert_threshold=Decimal(12)
                    )
                )
            created += 1
    return created
