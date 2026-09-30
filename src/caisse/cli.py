"""Outils d'amorçage et de dépannage (04-EXPLOITATION-BACKEND §3 et §4).

python -m caisse.cli bootstrap
python -m caisse.cli create-user [--noinput]
python -m caisse.cli reset-pin --name "Awa"
python -m caisse.cli seed --demo
python -m caisse.cli create-tables --count 15 --zone Salle
python -m caisse.cli import-catalog /data/menu.csv
"""

import argparse
import csv
import getpass
import os
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caisse.database import get_sessionmaker
from caisse.domain.enums import CategoryKind, UserRole
from caisse.errors import DomainError
from caisse.models.catalog import Category, Product
from caisse.models.stock import StockItem
from caisse.models.table import RestaurantTable
from caisse.repositories import users as users_repo
from caisse.seeds.defaults import ensure_defaults
from caisse.services import user_service
from caisse.services.audit_service import RequestContext

CLI_CTX = RequestContext(device_id="cli")


def _ask(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        sys.exit("Valeur obligatoire.")
    return value


def _ask_pin() -> str:
    pin = getpass.getpass("PIN (6 chiffres) : ")
    if getpass.getpass("Confirmer le PIN : ") != pin:
        sys.exit("Les deux saisies diffèrent.")
    return pin


def cmd_bootstrap(db: Session, _: argparse.Namespace) -> None:
    ensure_defaults(db)
    db.commit()
    print("Caisse et paramètres par défaut en place.")


def cmd_create_user(db: Session, args: argparse.Namespace) -> None:
    if args.noinput:
        try:
            name = os.environ["CAISSE_USER_NAME"]
            role = os.environ["CAISSE_USER_ROLE"]
            pin = os.environ["CAISSE_USER_PIN"]
        except KeyError as exc:
            sys.exit(f"Variable d'environnement manquante : {exc.args[0]}")
    else:
        name = _ask("Nom complet : ")
        role = _ask("Rôle [CAISSIER/RESPONSABLE/ADMIN] : ").upper()
        pin = _ask_pin()
    try:
        user = user_service.create_user(
            db, full_name=name, role=UserRole(role.upper()), pin=pin, actor_id=None, ctx=CLI_CTX
        )
    except ValueError:
        sys.exit(f"Rôle inconnu : {role}")
    print(f"Utilisateur créé : {user.full_name} ({user.role}) — id {user.id}")


def cmd_reset_pin(db: Session, args: argparse.Namespace) -> None:
    matches = users_repo.find_by_name(db, args.name)
    if len(matches) != 1:
        sys.exit(f"{len(matches)} utilisateur(s) nommé(s) « {args.name} » : précisez.")
    user_service.set_pin(db, matches[0].id, _ask_pin(), actor_id=None, ctx=CLI_CTX)
    print(f"PIN réinitialisé pour {matches[0].full_name}.")


def cmd_seed(db: Session, args: argparse.Namespace) -> None:
    ensure_defaults(db)
    if args.demo:
        from caisse.seeds.demo import load_demo_menu

        created = load_demo_menu(db)
        _create_tables(db, 15, "Salle")
        print(f"Jeu de démonstration chargé ({created} produit(s) créé(s)).")
    db.commit()


def _create_tables(db: Session, count: int, zone: str) -> int:
    existing = set(db.scalars(select(RestaurantTable.label)))
    next_order = (db.scalar(select(func.max(RestaurantTable.sort_order))) or 0) + 1
    created = 0
    for n in range(1, count + 1):
        if str(n) not in existing:
            db.add(RestaurantTable(label=str(n), zone=zone, seats=4, sort_order=next_order))
            next_order += 1
            created += 1
    return created


def cmd_create_tables(db: Session, args: argparse.Namespace) -> None:
    created = _create_tables(db, args.count, args.zone)
    db.commit()
    print(f"{created} table(s) créée(s).")


def cmd_import_catalog(db: Session, args: argparse.Namespace) -> None:
    """CSV : categorie,nom,prix_xof,suivi_stock,groupe_fiscal (en-tête obligatoire)."""
    path = Path(args.csv)
    created = 0
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            try:
                cat_name = row["categorie"].strip()
                name = row["nom"].strip()
                price = int(row["prix_xof"])
                track = row["suivi_stock"].strip().lower() in {"1", "oui", "true", "o", "x"}
                group = (row.get("groupe_fiscal") or "AUTRES").strip().upper()
            except (KeyError, ValueError) as exc:
                sys.exit(f"Ligne {line_no} invalide : {exc}")
            category = db.scalar(select(Category).where(Category.name == cat_name))
            if category is None:
                category = Category(
                    name=cat_name,
                    fiscal_group=group,
                    kind=CategoryKind.DRINK if track else CategoryKind.FOOD,
                )
                db.add(category)
                db.flush()
            if db.scalar(select(Product).where(Product.name == name)) is not None:
                continue
            product = Product(
                category_id=category.id,
                name=name,
                short_name=name[:20],
                price_xof=price,
                track_stock=track,
                vat_rate=Decimal("18.00"),
            )
            db.add(product)
            db.flush()
            if track:
                db.add(StockItem(product_id=product.id))
            created += 1
    db.commit()
    print(f"{created} produit(s) importé(s).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="caisse.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Caisse n° 1 + paramètres par défaut")
    p = sub.add_parser("create-user", help="Créer un utilisateur (PIN)")
    p.add_argument(
        "--noinput",
        action="store_true",
        help="lit CAISSE_USER_NAME / CAISSE_USER_ROLE / CAISSE_USER_PIN",
    )
    p = sub.add_parser("reset-pin", help="Réinitialiser un PIN")
    p.add_argument("--name", required=True)
    p = sub.add_parser("seed", help="Données initiales")
    p.add_argument("--demo", action="store_true", help="menu et tables de démonstration")
    p = sub.add_parser("create-tables", help="Créer les tables de la salle")
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--zone", default="Salle")
    p = sub.add_parser("import-catalog", help="Importer le menu depuis un CSV")
    p.add_argument("csv")

    args = parser.parse_args(argv)
    handler = {
        "bootstrap": cmd_bootstrap,
        "create-user": cmd_create_user,
        "reset-pin": cmd_reset_pin,
        "seed": cmd_seed,
        "create-tables": cmd_create_tables,
        "import-catalog": cmd_import_catalog,
    }[args.command]
    with get_sessionmaker()() as db:
        try:
            handler(db, args)
        except DomainError as exc:
            sys.exit(f"Erreur : {exc.detail}")


if __name__ == "__main__":
    main()
