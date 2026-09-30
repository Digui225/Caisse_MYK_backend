# Endpoints testables — état au 27/09/2026

Ce document décrit les **18 routes réellement implémentées** dans `caisse-backend`, telles que le code les expose aujourd'hui. Le contrat cible complet est dans [`03-CONTRAT-API.md`](../../projet_caisse_MYK/03-CONTRAT-API.md). Toute route du contrat absente d'ici renvoie `404 NOT_FOUND`.

| Groupe | Routes |
|---|---|
| [Santé](#1-santé) | `GET /health`, `GET /health/ready` (servies aussi sous `/api/v1`) |
| [Authentification](#2-authentification) | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/override` |
| [Utilisateurs](#3-utilisateurs) | `GET /users`, `POST /users`, `PATCH /users/{id}`, `POST /users/{id}/pin` |
| [Catalogue](#4-catalogue) | `GET /categories`, `GET /products` |
| [Tables](#5-tables) | `GET /tables`, `GET /tables/board` |

---

## 0. Conventions communes

### Adresses

| | |
|---|---|
| API (Docker) | `http://localhost:8001` |
| Préfixe métier | `/api/v1` |
| Swagger | http://localhost:8001/docs (bouton **Authorize** → coller l'`access_token`) |
| OpenAPI brut | http://localhost:8001/openapi.json |

### En-têtes

| En-tête | Sens | Rôle |
|---|---|---|
| `Authorization: Bearer <access_token>` | requête | Obligatoire sur toutes les routes marquées « connecté » ou « ADMIN » |
| `X-Device-Id` | requête | Facultatif. Identifie le poste pour la temporisation des PIN (`/auth/override`) et pour l'audit. Sans lui, le poste est compté comme `unknown`. |
| `X-Request-Id` | requête / réponse | Facultatif en entrée. Toujours renvoyé en sortie, généré s'il est absent. Il apparaît dans les logs et dans les erreurs. |

### Rôles

Hiérarchie : `CAISSIER < RESPONSABLE < ADMIN`. Un rôle hérite des droits des rôles inférieurs.

| Mention dans ce document | Signification |
|---|---|
| **public** | Aucun jeton |
| **connecté** | N'importe quel utilisateur actif avec un `access_token` valide |
| **ADMIN** | Rôle ADMIN obligatoire, sinon `403 INSUFFICIENT_PRIVILEGE` |

### Durées de vie (valeurs du `.env`)

| Élément | Durée |
|---|---|
| `access_token` | 15 min (`ACCESS_TOKEN_TTL_MINUTES`) |
| `refresh_token` | 12 h (`REFRESH_TOKEN_TTL_HOURS`) |
| Jeton d'override | 60 s, usage unique |

### Listes

Les listes renvoient `{"items": [...], "next_cursor": null}`. Il n'y a **pas encore de pagination** : `next_cursor` est toujours `null` et tout est renvoyé en une fois.

### Montants

Tous les montants sont des **entiers en XOF** (`price_xof`, `total_ttc_xof`…). Seuls `vat_rate` et `stock_quantity` sont des nombres décimaux.

### Format des erreurs (`application/problem+json`)

```json
{
  "type": "https://caisse.local/errors/invalid-credentials",
  "title": "Code PIN invalide",
  "status": 401,
  "code": "INVALID_CREDENTIALS",
  "detail": "Code PIN invalide",
  "meta": { "remaining_attempts": 3 },
  "request_id": "9f1c…"
}
```

Le front doit se fier à **`code`**, qui est stable. `title` et `detail` sont des textes lisibles qui peuvent changer.

| Code | HTTP | Quand |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Corps ou paramètre mal formé. `meta.fields` liste les champs en cause. |
| `TOKEN_EXPIRED` | 401 | Jeton absent, expiré, invalide, du mauvais type, ou utilisateur désactivé |
| `INVALID_CREDENTIALS` | 401 | PIN inconnu |
| `ACCOUNT_LOCKED` | 423 | Poste temporairement bloqué après trop de PIN faux |
| `INSUFFICIENT_PRIVILEGE` | 403 | Rôle trop faible pour la route |
| `OVERRIDE_REQUIRED` | 403 | Le PIN saisi pour un override n'a pas le rôle requis |
| `NOT_FOUND` | 404 | Ressource ou route inexistante |
| `PIN_ALREADY_USED` | 409 | PIN déjà attribué à un autre utilisateur actif |
| `INTERNAL_ERROR` | 500 | Erreur imprévue. La trace est dans les logs, jamais dans la réponse. |

---

## 1. Santé

### `GET /health` — le processus répond

**Accès** : public · **Aussi servie sous** `/api/v1/health`

Réponse `200` :

```json
{ "status": "ok" }
```

Utilisée par le healthcheck Docker et par le bandeau de connexion du front.

### `GET /health/ready` — l'API est prête à vendre

**Accès** : public · **Aussi servie sous** `/api/v1/health/ready`

Réponse `200` :

```json
{
  "status": "ok",
  "database": "ok",
  "queues": { "print_queued": 0, "print_failed": 0, "fne_pending": 0 },
  "printer": { "agent_online": false, "printer_online": false, "paper": null }
}
```

| Cas | Réponse |
|---|---|
| Base injoignable | `503` avec `"status": "unavailable"`, `"database": "unreachable"` et sans `queues` |
| Agent d'impression arrêté | **Toujours `200`.** L'imprimante n'est qu'informative : `agent_online: false`. Le délai d'attente de l'agent est de 1,5 s. |

À tester :
- lancer l'agent en mode factice (`print-agent/README.md`) et vérifier que `agent_online` passe à `true` ;
- arrêter `infra-db` et vérifier la réponse `503`.

```bash
curl -s localhost:8001/health/ready | jq
```

---

## 2. Authentification

Préfixe : `/api/v1/auth`.

### `POST /auth/login` — connexion par PIN

**Accès** : public

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `pin` | chaîne | 4 à 8 chiffres (`^\d{4,8}$`). En pratique, les PIN créés font 6 chiffres. |
| `device_id` | chaîne | 1 à 64 caractères. Identifie le poste pour la temporisation. |

```json
{ "pin": "482913", "device_id": "poste-1" }
```

Réponse `200` :

```json
{
  "access_token": "eyJhbGciOi…",
  "refresh_token": "eyJhbGciOi…",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "id": "2b7c…", "full_name": "Isaac", "role": "ADMIN" },
  "open_session": null
}
```

`open_session` vaut `{id, business_date, cash_register_id}` si une session de caisse est ouverte. Elle est toujours `null` pour l'instant, car l'ouverture de session n'est pas encore implémentée.

Erreurs :

| Code | Cas | `meta` |
|---|---|---|
| `422 VALIDATION_ERROR` | PIN non numérique ou hors 4–8 chiffres, `device_id` absent. **Ne compte pas comme un essai.** | `fields` |
| `401 INVALID_CREDENTIALS` | PIN inconnu, ou PIN d'un utilisateur désactivé | `remaining_attempts` |
| `423 ACCOUNT_LOCKED` | Le poste (`device_id`) est bloqué | `locked_until` (ISO 8601, UTC) |

**Blocage progressif, par poste et non par utilisateur :**

| Échec n° | Effet |
|---|---|
| 1 à 4 | `401`, avec `remaining_attempts` de 4 à 1 |
| 5 | `423`, poste bloqué 30 s |
| 6 (après déblocage) | `423`, bloqué 60 s |
| 7, 8… | La durée double à chaque fois, **jusqu'à 15 min au plus** |
| Connexion réussie | Le compteur du poste revient à 0 |

Pendant le blocage, toute tentative renvoie `423` **sans être comptée**, même avec le bon PIN.

À tester :
- bon PIN → `200` ;
- 5 PIN faux sur `poste-test` → `423` au 5ᵉ essai ;
- pendant le blocage, se connecter avec le bon PIN sur `poste-1` → `200` (le blocage est limité au poste) ;
- PIN `"12ab"` → `422`, et le compteur ne bouge pas.

```bash
curl -s -X POST localhost:8001/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"pin":"482913","device_id":"poste-1"}' | jq
```

Traces dans `audit_logs` : `auth.login` en cas de succès, `auth.login_failed` en cas d'échec.

### `POST /auth/refresh` — renouveler les jetons

**Accès** : public (le `refresh_token` suffit)

Corps :

```json
{ "refresh_token": "eyJhbGciOi…" }
```

Réponse `200` : même format que `/auth/login`, avec une **nouvelle paire** de jetons.

**Rotation** : le `refresh_token` envoyé est révoqué à l'instant où le nouveau est émis.

| Code | Cas |
|---|---|
| `401 TOKEN_EXPIRED` | Jeton expiré ou falsifié, déjà utilisé une fois, révoqué par `/logout`, utilisateur désactivé entre-temps, ou `access_token` envoyé à la place (`detail: "Type de jeton inattendu"`) |

À tester :
- rafraîchir → `200` ;
- **rejouer le même** `refresh_token` → `401` ;
- envoyer l'`access_token` dans `refresh_token` → `401`.

### `POST /auth/logout` — déconnexion

**Accès** : connecté

Corps :

```json
{ "refresh_token": "eyJhbGciOi…" }
```

Réponse : `204`, sans corps.

- Révoque le `refresh_token` s'il appartient bien à l'utilisateur connecté.
- Renvoie `204` même si le `refresh_token` est déjà invalide : la déconnexion ne doit jamais échouer côté caisse.
- **L'`access_token` reste utilisable jusqu'à son expiration (15 min au plus).** Il n'est pas stocké côté serveur, c'est le front qui doit l'oublier.

À tester : après `/logout`, un `/auth/refresh` avec ce même jeton renvoie `401`.

Trace dans `audit_logs` : `auth.logout`.

### `GET /auth/me` — utilisateur courant

**Accès** : connecté

Réponse `200` :

```json
{
  "user": { "id": "2b7c…", "full_name": "Isaac", "role": "ADMIN" },
  "open_session": null
}
```

| Code | Cas |
|---|---|
| `401 TOKEN_EXPIRED` | Pas d'en-tête `Authorization` (`detail: "Authentification requise"`), jeton expiré ou utilisateur désactivé |

```bash
curl -s localhost:8001/api/v1/auth/me -H "Authorization: Bearer $TOKEN" | jq
```

### `POST /auth/override` — autorisation ponctuelle d'un responsable

**Accès** : connecté. C'est l'utilisateur **demandeur** qui est connecté, par exemple le caissier.

Un responsable tape son PIN sur le poste du caissier. L'API renvoie un jeton valable 60 s, utilisable une seule fois, lié à une action précise et au demandeur.

En-tête conseillé : `X-Device-Id`. Les PIN faux saisis ici comptent dans le blocage de ce poste.

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `pin` | chaîne | PIN du responsable, 4 à 8 chiffres |
| `action` | chaîne | 1 à 64 caractères, par ex. `order.remove_item` |
| `required_role` | `RESPONSABLE` \| `ADMIN` \| `CAISSIER` | Facultatif, `RESPONSABLE` par défaut |

```json
{ "pin": "654321", "action": "order.remove_item", "required_role": "RESPONSABLE" }
```

Réponse `200` :

```json
{
  "override_token": "eyJhbGciOi…",
  "expires_in": 60,
  "granted_by": { "id": "8e1a…", "full_name": "Responsable", "role": "RESPONSABLE" }
}
```

| Code | Cas | `meta` |
|---|---|---|
| `401 INVALID_CREDENTIALS` | PIN inconnu | `remaining_attempts` |
| `423 ACCOUNT_LOCKED` | Poste bloqué | `locked_until` |
| `403 OVERRIDE_REQUIRED` | PIN valide mais rôle insuffisant, par ex. un PIN de caissier | `required_role` |
| `401 TOKEN_EXPIRED` | Demandeur non connecté |  |

> **Limite actuelle :** on peut *obtenir* un jeton d'override, mais **aucune route ne le consomme encore**. Le retrait de ligne et l'annulation arriveront avec les commandes (L3), où il passera dans l'en-tête `X-Override-Token`. Pour l'instant, on ne teste que la délivrance et ses refus.
>
> Rien n'empêche un responsable de s'autoriser lui-même : avec le seul compte ADMIN, on peut donc tester le cas nominal.

Trace dans `audit_logs` : `auth.override_granted`, avec le demandeur et le responsable.

---

## 3. Utilisateurs

Préfixe : `/api/v1/users` · **Accès : ADMIN pour toutes les routes**, sinon `403 INSUFFICIENT_PRIVILEGE` avec `meta.required_role = "ADMIN"`.

Objet renvoyé (`UserDetail`) :

```json
{
  "id": "2b7c…",
  "full_name": "Awa Koné",
  "role": "CAISSIER",
  "is_active": true,
  "last_login_at": "2026-09-27T09:12:44.120Z",
  "created_at": "2026-09-24T15:21:03.004Z"
}
```

Le PIN et son haché ne sont jamais renvoyés.

### `GET /users` — liste

Réponse `200` : `{"items": [UserDetail…], "next_cursor": null}`, **utilisateurs désactivés compris**, triés par nom.

### `POST /users` — créer un utilisateur

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `full_name` | chaîne | 1 à 120 caractères. Les espaces en début et en fin sont retirés. |
| `role` | `CAISSIER` \| `RESPONSABLE` \| `ADMIN` | |
| `pin` | chaîne | **Exactement 6 chiffres** (`PIN_LENGTH`) |

```json
{ "full_name": "Awa Koné", "role": "CAISSIER", "pin": "111111" }
```

Réponse `201` : `UserDetail`.

| Code | Cas |
|---|---|
| `422 VALIDATION_ERROR` | PIN non numérique ou hors 4–8 chiffres (contrôle du schéma), **ou** PIN de 4, 5, 7 ou 8 chiffres (règle métier : `meta.fields[0].type = "pin_format"`) |
| `409 PIN_ALREADY_USED` | Un autre utilisateur **actif** a déjà ce PIN. Le PIN sert d'identifiant à la connexion, il doit donc être unique. |

Trace dans `audit_logs` : `user.create`.

### `PATCH /users/{user_id}` — modifier

Mise à jour partielle : seuls les champs envoyés changent.

| Champ | Type |
|---|---|
| `full_name` | chaîne, 1 à 120 caractères |
| `role` | `CAISSIER` \| `RESPONSABLE` \| `ADMIN` |
| `is_active` | booléen |

```json
{ "is_active": false }
```

Réponse `200` : `UserDetail`.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Identifiant inconnu (`meta.user_id`) |
| `422 VALIDATION_ERROR` | `user_id` n'est pas un UUID |

Effets à vérifier :
- **Désactivation** : l'utilisateur ne peut plus se connecter, et **ses jetons déjà émis cessent de fonctionner immédiatement** (`401` sur `/auth/me` et sur `/auth/refresh`).
- **Changement de rôle** : il s'applique dès la requête suivante, sans reconnexion. Le rôle est relu en base à chaque appel.

> **Comportement actuel :** rien n'empêche un ADMIN de se désactiver lui-même ou de retirer le dernier ADMIN. En cas de besoin, on s'en sort avec `python -m caisse.cli create-user`.

Trace dans `audit_logs` : `user.update`, avec l'état avant et après.

### `POST /users/{user_id}/pin` — réinitialiser le PIN

Corps :

```json
{ "pin": "222222" }
```

Réponse : `204`, sans corps.

| Code | Cas |
|---|---|
| `422 VALIDATION_ERROR` | PIN pas exactement 6 chiffres |
| `404 NOT_FOUND` | Utilisateur inconnu |
| `409 PIN_ALREADY_USED` | PIN déjà pris par un autre utilisateur actif. Remettre son propre PIN actuel est accepté. |

À tester : l'ancien PIN renvoie `401` à la connexion, le nouveau renvoie `200`.

Trace dans `audit_logs` : `user.pin_reset`.

---

## 4. Catalogue

Préfixe : `/api/v1` · **Accès : connecté** · **Lecture seule** : la création et la modification du catalogue ne sont pas encore implémentées.

### `GET /categories`

Réponse `200` : **catégories actives uniquement**, triées par `sort_order` puis par nom.

```json
{
  "items": [
    {
      "id": "c1d2…",
      "name": "Poissons",
      "kind": "FOOD",
      "sort_order": 0,
      "color": "#B45309",
      "is_active": true,
      "fiscal_group": "POISSONS"
    }
  ],
  "next_cursor": null
}
```

`kind` vaut `FOOD`, `DRINK` ou `OTHER`. `fiscal_group` sert au récapitulatif FNE journalier (L6).

Jeu de démo : Poissons, Viandes, Accompagnements, Jus, Sucreries, Eau.

### `GET /products`

Paramètres de requête, tous facultatifs :

| Paramètre | Type | Effet |
|---|---|---|
| `category_id` | UUID | Filtre sur une catégorie |
| `search` | chaîne | Recherche dans `name`, sans tenir compte de la casse, n'importe où dans le nom |
| `is_active` | booléen | `true` par défaut. `false` renvoie les produits désactivés. |

Réponse `200` : triée par `sort_order` puis par nom.

```json
{
  "items": [
    {
      "id": "a9f0…",
      "name": "Jus de bissap",
      "short_name": "Bissap",
      "category_id": "c1d2…",
      "price_xof": 1000,
      "vat_rate": 18.0,
      "track_stock": true,
      "stock_quantity": 48.0,
      "is_active": true,
      "is_custom": false,
      "color": null,
      "sort_order": 0
    },
    {
      "id": "b7e3…",
      "name": "Poulet braisé",
      "short_name": "Poulet braisé",
      "category_id": "d4e5…",
      "price_xof": 4000,
      "vat_rate": 18.0,
      "track_stock": false,
      "stock_quantity": null,
      "is_active": true,
      "is_custom": false,
      "color": null,
      "sort_order": 3
    }
  ],
  "next_cursor": null
}
```

- `stock_quantity` vaut `null` quand le stock n'est pas suivi (`track_stock: false`). Il est rempli par la même requête, sans appel supplémentaire.
- Les **produits personnalisés** (`is_custom: true`, créés à la volée pendant une commande) **n'apparaissent jamais** dans cette liste.
- Il n'existe **aucun moyen d'obtenir les produits actifs et inactifs en un seul appel** : `is_active` vaut `true` ou `false`, jamais « tous ».

| Code | Cas |
|---|---|
| `422 VALIDATION_ERROR` | `category_id` n'est pas un UUID, ou `is_active` n'est pas un booléen |

```bash
curl -s "localhost:8001/api/v1/products?search=jus" -H "Authorization: Bearer $TOKEN" \
  | jq '.items[] | {name, price_xof, stock_quantity}'
```

---

## 5. Tables

Préfixe : `/api/v1/tables` · **Accès : connecté**

### `GET /tables` — configuration de la salle

Réponse `200` : **tables actives uniquement**, triées par `sort_order` puis par libellé.

```json
{
  "items": [
    { "id": "5e6f…", "label": "1", "zone": "Salle", "seats": 4, "sort_order": 0, "is_active": true }
  ],
  "next_cursor": null
}
```

Jeu de démo : 15 tables.

### `GET /tables/board` — écran d'accueil de la caisse

Un seul appel fournit l'état de la salle et le résumé de la journée. Le back-end n'exécute qu'une requête pour les tables et une pour le résumé, jamais une par table.

Réponse `200` :

```json
{
  "business_date": null,
  "summary": { "revenue_today_xof": 0, "orders_count": 0, "open_orders": 0 },
  "tables": [
    {
      "id": "5e6f…",
      "label": "1",
      "zone": "Salle",
      "seats": 4,
      "status": "FREE",
      "order": null
    }
  ]
}
```

Quand une table a une commande active (`OPEN` ou `PARTIALLY_PAID`) :

```json
{
  "status": "OCCUPIED",
  "order": {
    "id": "0a1b…",
    "total_ttc_xof": 9000,
    "paid_xof": 0,
    "guests_count": 3,
    "opened_at": "2026-09-27T12:04:10Z",
    "status": "OPEN"
  }
}
```

| Champ | Contenu |
|---|---|
| `business_date` | Journée comptable de la session de caisse ouverte, `null` sinon |
| `summary.revenue_today_xof` | Total des commandes **payées** de la journée |
| `summary.orders_count` | Nombre de commandes payées de la journée |
| `summary.open_orders` | Nombre de commandes encore ouvertes |

> **Limite actuelle :** on ne peut encore créer ni session de caisse ni commande. On obtient donc toujours `business_date: null`, les compteurs à `0` et les 15 tables en `FREE`. On peut vérifier la forme de la réponse, pas le cas « table occupée ».

---

## 6. Scénario de test complet (curl + jq)

À lancer dans un terminal. Remplacer `ADMIN_PIN` par le PIN de l'administrateur créé avec `caisse.cli create-user`.

```bash
API=localhost:8001/api/v1
ADMIN_PIN=000000                                   # ← à remplacer

# 1. Santé
curl -s localhost:8001/health/ready | jq

# 2. Connexion admin
LOGIN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"pin\":\"$ADMIN_PIN\",\"device_id\":\"poste-1\"}")
TOKEN=$(echo "$LOGIN" | jq -r .access_token)
REFRESH=$(echo "$LOGIN" | jq -r .refresh_token)
AUTH="Authorization: Bearer $TOKEN"
curl -s $API/auth/me -H "$AUTH" | jq

# 3. Rotation du refresh : le 2e appel doit renvoyer 401
curl -s -X POST $API/auth/refresh -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}" | jq '.user'
curl -s -X POST $API/auth/refresh -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}" | jq '{status, code}'

# 4. Créer un caissier et un responsable
CAISSIER_ID=$(curl -s -X POST $API/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"full_name":"Caissier Test","role":"CAISSIER","pin":"111111"}' | jq -r .id)
curl -s -X POST $API/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"full_name":"Resp Test","role":"RESPONSABLE","pin":"222222"}' | jq
# PIN déjà pris → 409 PIN_ALREADY_USED
curl -s -X POST $API/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"full_name":"Doublon","role":"CAISSIER","pin":"111111"}' | jq '{status, code}'

# 5. Droits : le caissier n'a pas accès à /users → 403
CT=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"pin":"111111","device_id":"poste-1"}' | jq -r .access_token)
curl -s $API/users -H "Authorization: Bearer $CT" | jq '{status, code, meta}'

# 6. Override demandé par le caissier
#    PIN du responsable → 200 ; PIN du caissier → 403 OVERRIDE_REQUIRED
curl -s -X POST $API/auth/override -H "Authorization: Bearer $CT" -H 'X-Device-Id: poste-1' \
  -H 'Content-Type: application/json' -d '{"pin":"222222","action":"order.remove_item"}' | jq
curl -s -X POST $API/auth/override -H "Authorization: Bearer $CT" -H 'X-Device-Id: poste-1' \
  -H 'Content-Type: application/json' -d '{"pin":"111111","action":"order.remove_item"}' \
  | jq '{status, code}'

# 7. Catalogue et salle (avec le jeton du caissier)
curl -s $API/categories -H "Authorization: Bearer $CT" | jq '.items[] | {name, kind}'
curl -s "$API/products?search=jus" -H "Authorization: Bearer $CT" \
  | jq '.items[] | {name, price_xof, stock_quantity}'
curl -s $API/tables/board -H "Authorization: Bearer $CT" | jq '{business_date, summary, n: (.tables | length)}'

# 8. Désactiver le caissier : son jeton est aussitôt refusé (401)
curl -s -X PATCH $API/users/$CAISSIER_ID -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"is_active":false}' | jq '{full_name, is_active}'
curl -s $API/auth/me -H "Authorization: Bearer $CT" | jq '{status, code}'

# 9. Blocage progressif sur un poste dédié : 4 × 401 puis 423
for i in 1 2 3 4 5; do
  curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
    -d '{"pin":"999999","device_id":"poste-test"}' | jq -c '{status, code, meta}'
done
```

Pour vérifier l'audit après le scénario :

```bash
docker exec infra-db sh -c 'psql -U "$POSTGRES_USER" -d caisse -c \
  "select created_at, action, entity from audit_logs order by created_at desc limit 20"'
```

> Le scénario laisse deux utilisateurs de test en base, dont un désactivé. Comme les PIN doivent être uniques, relancer le scénario tel quel renverra `409` à l'étape 4 pour « Resp Test ». Changer les PIN ou désactiver ces comptes avant de le relancer.

---

## 7. Pas encore testable

| Lot | Routes du contrat absentes |
|---|---|
| L1 | `/cash-sessions` et toutes ses sous-routes (ouverture, clôture, X/Z, mouvements) |
| L2 | `POST/PATCH/DELETE /categories`, `POST/PATCH /products`, `PATCH /products/{id}/price`, `POST /products/custom`, `POST/PATCH /tables` |
| L3 | `/orders` et ses lignes, annulation, ré-impression |
| L4 | `/orders/{id}/payments`, `/refunds`, `/payment-methods`, `/printing/*` |
| L5 | `/stock/*` |
| L6 | `/customers`, `/orders/{id}/fne`, `/fne/*` |
| L5–L6 | `/reports/*` |
| Admin | `/settings`, `/cash-registers` |
