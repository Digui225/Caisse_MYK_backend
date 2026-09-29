import argparse
import csv
import sys
from caisse.database import SessionLocal
from caisse.models.catalog import Category, Product
from caisse.models.table import RestaurantTable
from caisse.services.auth_service import AuthService
from caisse.repositories.sessions import CashSessionRepository
from caisse.seeds.demo_data import seed_catalog_and_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI d'administration de la Caisse MYK")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Commande create-user
    user_parser = subparsers.add_parser("create-user", help="Créer un nouvel utilisateur")
    user_parser.add_argument("--name", help="Nom complet de l'utilisateur")
    user_parser.add_argument("--role", choices=["CAISSIER", "RESPONSABLE", "ADMIN"], help="Rôle")
    user_parser.add_argument("--pin", help="Code PIN (6 chiffres)")
    user_parser.add_argument("--noinput", action="store_true", help="Mode non interactif")

    # Commande reset-pin
    reset_parser = subparsers.add_parser("reset-pin", help="Réinitialiser le code PIN")
    reset_parser.add_argument("--name", required=True, help="Nom complet de l'utilisateur")
    reset_parser.add_argument("--new-pin", help="Nouveau code PIN")

    # Commande seed
    seed_parser = subparsers.add_parser("seed", help="Initialiser les données de test / démo")
    seed_parser.add_argument("--demo", action="store_true", help="Charger les données de démonstration")

    # Commande import-catalog
    import_parser = subparsers.add_parser("import-catalog", help="Importer le catalogue depuis un fichier CSV")
    import_parser.add_argument("file", help="Chemin du fichier CSV (format: categorie,nom,nom_court,prix_xof,suivi_stock,groupe_fiscal)")

    # Commande create-tables
    tables_parser = subparsers.add_parser("create-tables", help="Générer des tables de salle")
    tables_parser.add_argument("--count", type=int, default=15, help="Nombre de tables à générer")
    tables_parser.add_argument("--zone", default="Salle", help="Nom de la zone")

    args = parser.parse_args()
    db = SessionLocal()
    auth_service = AuthService(db)
    session_repo = CashSessionRepository(db)

    try:
        if args.command == "create-user":
            if args.noinput or (args.name and args.role and args.pin):
                name = args.name or sys.stdin.readline().strip()
                role = args.role or "CAISSIER"
                pin = args.pin or "123456"
            else:
                name = input("Nom complet : ").strip()
                role = input("Rôle [CAISSIER/RESPONSABLE/ADMIN] : ").strip().upper()
                pin = input("PIN (6 chiffres) : ").strip()

            user = auth_service.create_user(full_name=name, pin=pin, role=role)
            print(f"✅ Utilisateur '{user.full_name}' ({user.role}) créé avec succès. ID: {user.id}")

        elif args.command == "reset-pin":
            user = auth_service.user_repo.get_by_name(args.name)
            if not user:
                print(f"❌ Utilisateur '{args.name}' introuvable.")
                sys.exit(1)
            new_pin = args.new_pin or input(f"Nouveau PIN pour {user.full_name} : ").strip()
            from caisse.security import hash_pin
            user.pin_hash = hash_pin(new_pin)
            user.failed_attempts = 0
            user.locked_until = None
            db.commit()
            print(f"✅ PIN de '{user.full_name}' réinitialisé avec succès.")

        elif args.command == "seed":
            session_repo.get_or_create_default_register()
            if not auth_service.user_repo.list_all():
                auth_service.create_user("Caissière Principale", "111111", "CAISSIER")
                auth_service.create_user("Responsable Restaurant", "222222", "RESPONSABLE")
                auth_service.create_user("Administrateur", "999999", "ADMIN")
                print("✅ Utilisateurs de démo créés (Caissière: 111111, Responsable: 222222, Admin: 999999).")
            seed_catalog_and_tables(db)
            print("✅ Caisse, menu et tables de base initialisés avec succès.")

        elif args.command == "create-tables":
            created_count = 0
            for i in range(1, args.count + 1):
                label = f"Table {i}"
                if not db.query(RestaurantTable).filter(RestaurantTable.label == label).first():
                    t = RestaurantTable(
                        label=label,
                        zone=args.zone,
                        seats=4,
                        sort_order=i,
                        is_active=True,
                    )
                    db.add(t)
                    created_count += 1
            db.commit()
            print(f"✅ {created_count} tables créées dans la zone '{args.zone}'.")

        elif args.command == "import-catalog":
            with open(args.file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    cat_name = row["categorie"].strip()
                    category = db.query(Category).filter(Category.name == cat_name).first()
                    if not category:
                        category = Category(
                            name=cat_name,
                            kind="DRINK" if "boisson" in cat_name.lower() or "eau" in cat_name.lower() else "FOOD",
                            fiscal_group=row.get("groupe_fiscal", "PLATS"),
                        )
                        db.add(category)
                        db.flush()

                    short_name = row.get("nom_court", row["nom"][:20]).strip()
                    track_stock = row.get("suivi_stock", "false").lower() in ("true", "1", "oui")

                    prod = Product(
                        category_id=category.id,
                        name=row["nom"].strip(),
                        short_name=short_name,
                        price_xof=int(row["prix_xof"]),
                        track_stock=track_stock,
                    )
                    db.add(prod)
                    count += 1
                db.commit()
                print(f"✅ {count} produits importés avec succès depuis '{args.file}'.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
