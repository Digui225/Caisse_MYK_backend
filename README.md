# caisse-backend — API FastAPI

Documentation de référence : `../projet_caisse_MYK/` (01-BACKEND, 03-CONTRAT-API, 04-EXPLOITATION).

## Démarrage

Prérequis : le socle `../infra` tourne (PostgreSQL partagé, réseau `infra_shared`).

```bash
cp .env.example .env && nano .env        # DATABASE_URL (mot de passe caisse du socle), JWT_SECRET
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m caisse.cli bootstrap        # caisse n° 1 + paramètres
docker compose exec api python -m caisse.cli create-user      # premier ADMIN (PIN 6 chiffres)
docker compose exec api python -m caisse.cli seed --demo      # dév. uniquement : menu + 15 tables
curl -s localhost:8001/health/ready
```

OpenAPI : http://localhost:8001/docs · http://localhost:8001/openapi.json

Après un redémarrage, ou en cas de doute : `./scripts/demarrer-caisse.sh` vérifie Docker, le réseau,
la base, l'API, les migrations et la santé, démarre ce qui manque et explique chaque résultat
(`--check` pour vérifier sans rien démarrer).

Développement (rechargement à chaud) :
`docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`

## Tests et qualité

```bash
docker build --target dev -t caisse-api:dev .
docker network create caisse_test
docker run -d --rm --name caisse-test-db --network caisse_test \
  -e POSTGRES_USER=caisse -e POSTGRES_PASSWORD=caisse -e POSTGRES_DB=caisse postgres:16-alpine
docker run --rm --network caisse_test -v $PWD:/app \
  -e TEST_DATABASE_URL=postgresql+psycopg://caisse:caisse@caisse-test-db:5432/caisse \
  caisse-api:dev sh -c "pytest && ruff check src tests && mypy src"
docker rm -f caisse-test-db && docker network rm caisse_test
```

Sans `TEST_DATABASE_URL`, les tests démarrent eux-mêmes un PostgreSQL via testcontainers
(nécessite l'accès au démon Docker).
Les tests d'intégration rejouent `alembic downgrade base` puis `upgrade head` :
toute migration doit rester réversible.

## Arborescence

```
src/caisse/
  domain/          règles pures, zéro I/O (money, enums, ids, ports)
  models/          SQLAlchemy — schéma complet de 01-BACKEND §4
  repositories/    accès données
  services/        cas d'usage + transactions (auth, users, audit)
  api/             routers FastAPI (/health, /api/v1/…)
  infrastructure/  client de l'agent d'impression
  seeds/ cli.py    amorçage et dépannage
alembic/           migrations
print-agent/       service systemd hors Docker (imprimante USB + tiroir)
```

## État d'avancement

| Lot | Fait | Reste |
|---|---|---|
| L0 | Squelette, schéma + migration, problem+json, `domain/money`, OpenAPI | Endpoints mockés du reste du contrat, CI |
| L1 | PIN Argon2, JWT + refresh (rotation), RBAC, override 60 s usage unique, blocage progressif par poste, users, audit, sessions de caisse (ouverture/clôture, X/Z, mouvements, idempotence générique) | — |
| L2 | Lecture catégories / produits / tables, seeds, import CSV | CRUD catalogue, historique de prix |
| L3 | `GET /tables/board` (requête agrégée), commandes (table / à emporter), lignes (ajout, modification, retrait avec motif), annulation sous override, article libre | Ré-impression (avec la file d'impression) |
| L4+ | Agent d'impression (USB + tiroir, mode dummy) | Paiements, file d'impression, FNE, rapports, worker, backup |
