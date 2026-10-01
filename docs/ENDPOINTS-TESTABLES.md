# Endpoints testables — état au 01/10/2026

Ce document décrit les **39 routes réellement implémentées** dans `caisse-backend`, telles que le code les expose aujourd'hui. Le contrat cible complet est dans [`03-CONTRAT-API.md`](../../projet_caisse_MYK/03-CONTRAT-API.md). Toute route du contrat absente d'ici renvoie `404 NOT_FOUND`.

## Sommaire

| § | Section | Routes | En bref |
|---|---|---|---|
| 0 | [Conventions communes](#0-conventions-communes) | — | Adresses, en-têtes, rôles, format des erreurs et catalogue des codes |
| 1 | [Santé](#1-santé) | `GET /health`, `GET /health/ready` | L'API répond, la base et l'imprimante sont joignables |
| 2 | [Authentification](#2-authentification) | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/override` | Connexion par PIN, jetons, blocage par poste, autorisation ponctuelle d'un responsable |
| 3 | [Utilisateurs](#3-utilisateurs) | `GET /users`, `POST /users`, `PATCH /users/{id}`, `POST /users/{id}/pin` | Gestion des comptes (ADMIN) |
| 4 | [Catalogue](#4-catalogue) | `GET /categories`, `GET /products`, `POST /products/custom` | Menu en lecture, article libre |
| 5 | [Tables](#5-tables) | `GET /tables`, `GET /tables/board` | Salle et plan de salle (écran d'accueil) |
| 6 | [Sessions de caisse](#6-sessions-de-caisse) | `GET /cash-sessions/current`, `POST /cash-sessions`, `GET …/{id}/x-report`, `POST …/{id}/close`, `GET …/{id}/z-report`, `GET /cash-sessions`, `POST …/{id}/movements` | Ouverture, mouvements de tiroir, rapports X et Z, clôture |
| 7 | [Commandes](#7-commandes) | `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST …/{id}/items`, `PATCH …/items/{item_id}`, `DELETE …/items/{item_id}`, `POST …/{id}/cancel` | Prise de commande, lignes (ajout, quantité, retrait), annulation sous autorisation |
| 8 | [Clients entreprise et FNE](#8-clients-entreprise-et-fne) | `GET/POST /customers`, `POST/GET /orders/{id}/fne`, `GET /fne/documents`, `POST …/{id}/retry`, `POST …/{id}/resolve`, `POST …/{id}/refund`, `GET …/{id}/duplicate`, `GET /fne/pending-count`, `GET /fne/daily-summary` | Facture normalisée DGI à la demande, avoirs, suivi |
| 9 | [Scénario de test complet](#9-scénario-de-test-complet-curl--jq) | — | Tout le parcours en curl, de la connexion à la clôture |
| 10 | [Pas encore testable](#10-pas-encore-testable) | — | Routes du contrat pas encore implémentées |

**Par où commencer :**

1. Préparer la base avec `docker compose exec api python -m caisse.cli …` : `bootstrap` (caisse n° 1), `create-user` (un ADMIN), `seed --demo` (menu + 15 tables).
2. Ouvrir Swagger (http://localhost:8001/docs), se connecter avec `POST /auth/login`, coller l'`access_token` dans **Authorize**.
3. Suivre le parcours d'une journée : ouvrir la caisse (§6) → prendre des commandes (§7) → clôturer (§6). Le [§9](#9-scénario-de-test-complet-curl--jq) fait la même chose en curl.

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
| `X-Override-Token` | requête | Jeton obtenu par `POST /auth/override`. Permet à un CAISSIER d'annuler une commande (action `order.cancel`). Inutile pour un RESPONSABLE ou un ADMIN. |
| `Idempotency-Key` | requête | **Obligatoire** sur `POST /cash-sessions` et `POST /cash-sessions/{id}/close`. Rejouer la même clé avec le même corps renvoie la réponse d'origine en `200`, avec l'en-tête `Idempotent-Replay: true` en retour. |

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
| `NO_OPEN_SESSION` | 409 | Aucune session de caisse ouverte, ou mouvement demandé sur une session déjà clôturée |
| `SESSION_ALREADY_OPEN` | 409 | Une session est déjà ouverte sur cette caisse |
| `SESSION_ALREADY_CLOSED` | 409 | La session visée est déjà clôturée |
| `SESSION_NOT_CLOSED` | 409 | Rapport Z demandé avant la clôture |
| `SESSION_HAS_OPEN_ORDERS` | 409 | Clôture refusée : des commandes ne sont pas soldées (`meta.open_orders[]`) |
| `BUSINESS_DATE_MISMATCH` | 409 | Une session clôturée existe déjà pour cette journée comptable ; rejouer avec `confirm_business_date: true` |
| `IDEMPOTENCY_CONFLICT` | 409 | Même `Idempotency-Key`, corps différent |
| `TABLE_ALREADY_OCCUPIED` | 409 | La table porte déjà une commande active (`meta.order_id` : celle à ouvrir) |
| `ORDER_NOT_EDITABLE` | 409 | Commande soldée ou annulée (`meta.status`), ou modification qui ferait passer le total sous le montant déjà encaissé |
| `CUSTOMER_NCC_EXISTS` | 409 | NCC déjà enregistré (`meta.customer_id` : client à réutiliser) |
| `FNE_ORDER_NOT_PAID` | 409 | FNE demandée sur une commande non soldée |
| `FNE_NOT_CONFIGURED` | 409 | Paramètres `fne.point_of_sale` / `fne.establishment` vides (`meta.missing_settings`) |
| `FNE_DOCUMENT_STATE` | 409 | Action interdite dans l'état du document FNE (`meta.reason`) |
| `FNE_CUSTOMER_REQUIRED`, `FNE_NCC_REQUIRED`, `FNE_NO_PAYMENT`, `FNE_VAT_RATE_UNMAPPED`, `FNE_PAYMENT_METHOD_UNMAPPED`, `FNE_FIELD_REQUIRED` | 422 | Commande impossible à traduire en FNE (client, NCC, paiement, taux de TVA, client de passage non paramétré) |
| `FNE_REFUND_EXCEEDS` | 422 | Avoir supérieur à la quantité certifiée restante (`meta.available`) |
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

`open_session` vaut `{id, business_date, cash_register_id}` si une session de caisse est ouverte (voir [§6](#6-sessions-de-caisse)), `null` sinon.

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

`open_session` reflète la session de caisse ouverte, comme sur `/auth/login` (voir [§6](#6-sessions-de-caisse)).

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
| `action` | chaîne | 1 à 64 caractères, par ex. `order.cancel` |
| `required_role` | `RESPONSABLE` \| `ADMIN` \| `CAISSIER` | Facultatif, `RESPONSABLE` par défaut |

```json
{ "pin": "654321", "action": "order.cancel", "required_role": "RESPONSABLE" }
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

Le jeton se consomme dans l'en-tête `X-Override-Token` de `POST /orders/{id}/cancel` (action `order.cancel`), voir [§7](#7-commandes). Il est refusé (`403 OVERRIDE_REQUIRED`, `meta.reason`) s'il est expiré, déjà utilisé, demandé pour une autre action ou par un autre utilisateur.

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

Préfixe : `/api/v1` · **Accès : connecté** · La gestion du catalogue (création, modification, prix) n'est pas encore implémentée ; seul l'article libre (`POST /products/custom`) peut être créé.

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

### `POST /products/custom` — article libre

Produit créé à la volée pendant une commande (plat du jour, poisson au poids…). Il a `is_custom: true`, n'apparaît **jamais** dans `GET /products`, et s'ajoute ensuite à la commande avec `POST /orders/{id}/items`.

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `name` | chaîne | 1 à 120 caractères. Le libellé ticket (`short_name`) en reprend les 20 premiers. |
| `price_xof` | entier | ≥ 0, prix TTC |
| `category_id` | UUID | Catégorie active ; elle fixe le groupe fiscal de la ligne |
| `vat_rate` | décimal | Facultatif, `18.00` par défaut |

```json
{ "name": "Poisson capitaine 1 kg", "price_xof": 9000, "category_id": "c1d2…" }
```

Réponse `201` : le produit, au format de `GET /products` (`stock_quantity: null`, `track_stock: false`).

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Catégorie inconnue ou désactivée |
| `422 VALIDATION_ERROR` | Nom vide, prix négatif |

Trace dans `audit_logs` : `product.create_custom`.

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

À tester : ouvrir une session ([§6](#6-sessions-de-caisse)) → `business_date` se remplit ; créer une commande sur une table ([§7](#7-commandes)) → la table passe en `OCCUPIED` avec son total, et `summary.open_orders` augmente ; l'annuler → la table redevient `FREE`.

> **Limite actuelle :** l'encaissement n'existe pas encore, donc aucune commande ne peut être `PAID` : `revenue_today_xof` et `orders_count` restent à `0`.

---

## 6. Sessions de caisse

Préfixe : `/api/v1/cash-sessions` · **Accès : connecté**, sauf `GET /cash-sessions` (historique) réservé au **RESPONSABLE**.

MVP mono-poste : il n'y a qu'une caisse (`cash_register_id` unique, créée par `python -m caisse.cli bootstrap`) et jamais plus d'une session non clôturée à la fois, tous postes confondus.

Objet renvoyé (`CashSessionOut`) :

```json
{
  "id": "f1a2…",
  "cash_register_id": "b3c4…",
  "status": "OPEN",
  "business_date": "2026-09-30",
  "opening_float_xof": 20000,
  "opened_at": "2026-09-30T08:00:00Z",
  "closed_at": null,
  "z_number": null,
  "counted_cash_xof": null,
  "expected_cash_xof": null,
  "variance_xof": null,
  "notes": null
}
```

### `GET /cash-sessions/current` — session ouverte sur ce poste

Réponse `200` : `CashSessionOut`.

| Code | Cas |
|---|---|
| `409 NO_OPEN_SESSION` | Aucune session ouverte actuellement |

### `POST /cash-sessions` — ouvrir une session

**Idempotent** : en-tête `Idempotency-Key` obligatoire.

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `cash_register_id` | UUID | Caisse à ouvrir |
| `opening_float_xof` | entier | ≥ 0, fonds de caisse initial |
| `business_date` | date | Facultatif, défaut : date du jour (UTC) |
| `confirm_business_date` | booléen | Facultatif, défaut `false` — voir `BUSINESS_DATE_MISMATCH` |

```json
{ "cash_register_id": "b3c4…", "opening_float_xof": 20000 }
```

Réponse `201` : `CashSessionOut`. Rejeu de la même clé avec le même corps → `200` + en-tête `Idempotent-Replay: true` + le même corps.

| Code | Cas | `meta` |
|---|---|---|
| `409 SESSION_ALREADY_OPEN` | Une session est déjà ouverte sur cette caisse | |
| `409 BUSINESS_DATE_MISMATCH` | Une session déjà clôturée existe pour cette caisse et cette `business_date` | `business_date`, `existing_session_id` — rejouer avec `confirm_business_date: true` |
| `409 IDEMPOTENCY_CONFLICT` | Même `Idempotency-Key`, corps différent | `key` |

À tester :
- ouverture → `201` ; rejeu même clé/même corps → `200` + `Idempotent-Replay: true` ; même clé, corps différent → `409 IDEMPOTENCY_CONFLICT` ;
- deuxième ouverture (clé différente) sur la même caisse → `409 SESSION_ALREADY_OPEN`.

Trace dans `audit_logs` : `cash_session.open`.

### `GET /cash-sessions/{id}/x-report` — rapport X (lecture seule)

Réponse `200` (`XReportOut`) : agrégats de la session **en cours**, recalculés à chaque appel, sans aucun effet de bord.

```json
{
  "session_id": "f1a2…",
  "business_date": "2026-09-30",
  "expected_cash_xof": 23000,
  "totals": {
    "gross_ttc_xof": 0, "vat_xof": 0, "orders_count": 0,
    "by_payment_method": [], "by_fiscal_group": [],
    "controls": { "cancelled_orders": 0, "removed_items": 0, "reprints": 0 }
  }
}
```

Seules les commandes **soldées** (`PAID`) comptent dans le chiffre d'affaires et la ventilation par groupe fiscal ; `controls` compte les commandes annulées et les lignes retirées.

> Tant que l'encaissement n'est pas implémenté ([§9](#9-pas-encore-testable)), aucune commande n'est `PAID` : les montants de `totals` restent à zéro et `expected_cash_xof` ne reflète que `opening_float_xof` et les mouvements de tiroir. `controls.cancelled_orders` et `controls.removed_items`, eux, sont déjà testables.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Session inconnue |

### `POST /cash-sessions/{id}/close` — clôturer la session (Z)

**Idempotent** : en-tête `Idempotency-Key` obligatoire.

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `counted_breakdown` | objet | Comptage par dénomination, ex. `{"10000": 2, "1000": 3}` |
| `notes` | chaîne \| `null` | Facultatif, ≤ 500 caractères |

```json
{ "counted_breakdown": { "10000": 2, "1000": 3 }, "notes": "RAS" }
```

Réponse `201` (`ZReportOut`) :

```json
{
  "z_number": 1,
  "business_date": "2026-09-30",
  "expected_cash_xof": 23000,
  "counted_cash_xof": 23000,
  "variance_xof": 0,
  "totals": { "...": "identique à x-report, figé" },
  "print_job_id": null
}
```

`expected_cash_xof = opening_float_xof + encaissements espèces + entrées − sorties de tiroir`. `print_job_id` reste `null` tant que l'impression ([§9](#9-pas-encore-testable)) n'est pas implémentée.

| Code | Cas | `meta` |
|---|---|---|
| `404 NOT_FOUND` | Session inconnue | |
| `409 SESSION_ALREADY_CLOSED` | Déjà clôturée (hors rejeu idempotent) | |
| `409 SESSION_HAS_OPEN_ORDERS` | Des commandes ne sont pas soldées | `open_orders[]` |
| `409 IDEMPOTENCY_CONFLICT` | Même `Idempotency-Key`, corps différent | `key` |

À tester :
- clôture avec un comptage exact → `variance_xof: 0`, `z_number` commence à `1` et s'incrémente à chaque clôture sur la même caisse ;
- comptage différent du théorique → `variance_xof` non nul, signé (compté − théorique) ;
- rejeu de la même clé → `200` + `Idempotent-Replay: true`.

Trace dans `audit_logs` : `cash_session.close`.

### `GET /cash-sessions/{id}/z-report` — rapport Z figé

Réponse `200` : `ZReportOut`, identique à la réponse de clôture, relue depuis `totals_snapshot` (aucun recalcul).

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Session inconnue |
| `409 SESSION_NOT_CLOSED` | La session n'est pas encore clôturée |

### `GET /cash-sessions` — historique

**Accès : RESPONSABLE**, sinon `403 INSUFFICIENT_PRIVILEGE`.

Réponse `200` : `{"items": [CashSessionOut…], "next_cursor": null}`, sessions **clôturées** uniquement, les plus récentes en premier.

### `POST /cash-sessions/{id}/movements` — entrée ou sortie de tiroir

Pas d'`Idempotency-Key` (absent du contrat pour cette route).

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `type` | `IN` \| `OUT` | Entrée ou sortie |
| `amount_xof` | entier | > 0 |
| `reason` | chaîne | 1 à 255 caractères, obligatoire |

```json
{ "type": "OUT", "amount_xof": 2000, "reason": "achat glace" }
```

Réponse `201` (`MovementResult`) :

```json
{
  "movement": { "id": "…", "type": "OUT", "amount_xof": 2000, "reason": "achat glace", "created_at": "…" },
  "session": { "...": "CashSessionOut à jour" }
}
```

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Session inconnue |
| `409 NO_OPEN_SESSION` | La session n'est plus `OPEN` (déjà clôturée) |

Trace dans `audit_logs` : `cash_session.movement`.

```bash
curl -s -X POST $API/cash-sessions -H "$AUTH" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" -d '{"cash_register_id":"'"$REGISTER_ID"'","opening_float_xof":20000}' | jq
```

---

## 7. Commandes

Préfixe : `/api/v1/orders` · **Accès : connecté**. Seule l'annulation d'une commande demande un responsable (ou un caissier avec un `X-Override-Token`).

Une commande est toujours rattachée à la **session de caisse ouverte** et à sa journée comptable. Les montants sont **toujours recalculés par le backend** : le front n'additionne jamais rien.

**Toutes les mutations** (création, ajout, modification, retrait, annulation) renvoient la commande complète (`OrderResult`) :

```json
{
  "order": {
    "id": "0a1b…",
    "order_number": "2026-09-30-0001",
    "status": "OPEN",
    "business_date": "2026-09-30",
    "table_id": "5e6f…",
    "counter_number": null,
    "guests_count": 4,
    "total_ttc_xof": 9500,
    "total_ht_xof": 8051,
    "total_vat_xof": 1449,
    "paid_xof": 0,
    "due_xof": 9500,
    "opened_at": "2026-09-30T12:04:10Z",
    "paid_at": null,
    "cancelled_at": null,
    "cancelled_reason": null,
    "items": [
      {
        "id": "7c8d…",
        "product_id": "a9f0…",
        "name": "Poisson braisé",
        "unit_price_xof": 3500,
        "quantity": 2,
        "line_total_xof": 7000,
        "note": "bien cuit",
        "added_at": "2026-09-30T12:05:02Z"
      }
    ]
  },
  "warnings": []
}
```

| Règle | Détail |
|---|---|
| Numérotation | `order_number` = `<journée>-<n° sur 4 chiffres>`, séquence par journée comptable |
| Vente à emporter | `table_id: null` → `counter_number` attribué (« Comptoir n° X »), séquence par journée |
| Une table, une commande | Au plus une commande `OPEN` / `PARTIALLY_PAID` par table, garanti en base |
| Prix figé | Libellé, prix, TVA et groupe fiscal sont **copiés sur la ligne** à l'ajout : un changement de prix du menu ne touche pas les commandes en cours |
| TVA | Calculée depuis le TTC, par taux : `ht = arrondi(ttc / (1 + taux))`, `tva = ttc − ht` |
| Lignes modifiables | Uniquement en `OPEN` / `PARTIALLY_PAID`. Une fois soldée ou annulée, la commande est figée (`409 ORDER_NOT_EDITABLE`) |
| Lignes retirées | Jamais supprimées : marquées retirées (qui, quand, motif), absentes de `items` et des totaux, comptées dans le rapport X/Z |

### `POST /orders` — créer une commande

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `table_id` | UUID \| `null` | Table active ; `null` ou absent pour une vente à emporter |
| `guests_count` | entier \| `null` | Facultatif, 1 à 99 |

```json
{ "table_id": "5e6f…", "guests_count": 4 }
```

Réponse `201` : `OrderResult`, sans lignes.

| Code | Cas | `meta` |
|---|---|---|
| `409 NO_OPEN_SESSION` | Aucune session de caisse ouverte | |
| `404 NOT_FOUND` | Table inconnue ou désactivée | `table_id` |
| `409 TABLE_ALREADY_OCCUPIED` | La table a déjà une commande active | `order_id` : la commande à ouvrir à la place |

Trace dans `audit_logs` : `order.create`.

### `GET /orders` — lister les commandes d'une journée

Paramètres de requête, facultatifs :

| Paramètre | Effet |
|---|---|
| `business_date` | Journée comptable. Défaut : celle de la session ouverte, sinon le jour (UTC) |
| `status` | `OPEN`, `PARTIALLY_PAID`, `PAID`, `CANCELLED`, `REFUNDED` |

Réponse `200` : `{"items": [...], "next_cursor": null}`, les plus récentes en premier. Chaque élément a les mêmes champs que `order` ci-dessus **sans `items`** (détail : `GET /orders/{id}`).

Utile pour retrouver les ventes à emporter en cours, qui n'apparaissent pas sur le plan de salle : `GET /orders?status=OPEN`.

| Code | Cas |
|---|---|
| `403 INSUFFICIENT_PRIVILEGE` | Un CAISSIER demande une autre journée que celle de la session ouverte (historique réservé au RESPONSABLE) |

### `GET /orders/{id}` — détail

Réponse `200` : l'objet `order` complet, avec ses lignes actives. Erreur : `404 NOT_FOUND`.

### `POST /orders/{id}/items` — ajouter une ligne

Corps :

| Champ | Type | Contraintes |
|---|---|---|
| `product_id` | UUID | Produit actif du menu, ou article libre |
| `quantity` | entier | 1 à 999, `1` par défaut |
| `note` | chaîne \| `null` | Facultatif, ≤ 255 caractères (« bien cuit », « sans piment ») |

```json
{ "product_id": "a9f0…", "quantity": 2, "note": "bien cuit" }
```

Réponse `201` : `OrderResult`. Ajouter deux fois le même produit crée **deux lignes** (les notes peuvent différer).

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Commande ou produit inconnu |
| `409 ORDER_NOT_EDITABLE` | Commande soldée ou annulée |
| `422 VALIDATION_ERROR` | Produit désactivé (`meta.fields[0].type = "product_inactive"`), quantité hors bornes |

### `PATCH /orders/{id}/items/{item_id}` — modifier une ligne

Mise à jour partielle : un champ absent reste inchangé, `"note": null` efface la note.

| Champ | Type |
|---|---|
| `quantity` | entier, 1 à 999 |
| `note` | chaîne \| `null`, ≤ 255 caractères |

```json
{ "quantity": 3 }
```

Réponse `200` : `OrderResult`.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Commande inconnue, ou ligne inconnue / déjà retirée |
| `409 ORDER_NOT_EDITABLE` | Commande soldée ou annulée |

Trace dans `audit_logs` : `order.item_update`, avec quantité et note avant/après.

#### Baisser une quantité ou retirer une ligne : quelle différence ?

Exemple : une ligne « 3 × Poisson braisé = 10 500 ».

| | Baisse de quantité (`PATCH`, 3 → 1) | Retrait de ligne (`DELETE`) |
|---|---|---|
| La ligne | Reste sur la commande, à 1 | Disparaît de la commande |
| Total de la commande | − 7 000 | − 10 500 |
| Autorisation d'un responsable | Non | Non |
| Motif | Non demandé | **Obligatoire** |
| Trace | `audit_logs` (`order.item_update`, avant/après) | `audit_logs` (`order.item_remove`) + ligne conservée en base, marquée retirée |
| Compté dans le rapport X/Z (`controls.removed_items`) | **Non** | **Oui** |
| Limite | Minimum 1 : pour aller à 0, il faut retirer la ligne | — |

En résumé : la baisse corrige une quantité, le retrait annule un article. Les deux sont libres pour la caissière ; seul le retrait demande un motif et apparaît dans les contrôles du rapport Z.

### `DELETE /orders/{id}/items/{item_id}?reason=…` — retirer une ligne

**Accès : connecté**, sans autorisation de responsable (décision client du 30/09/2026). Le motif passe en **paramètre de requête** `reason` (1 à 255 caractères, obligatoire).

Réponse `200` : `OrderResult`, la ligne n'est plus dans `items` et les totaux sont recalculés.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Commande inconnue, ou ligne inconnue / déjà retirée |
| `409 ORDER_NOT_EDITABLE` | Commande soldée ou annulée |
| `422 VALIDATION_ERROR` | `reason` absent ou vide |

À tester : caissier sans `reason` → `422` ; avec `reason` → `200` et `controls.removed_items` augmente dans le rapport X ; retirer la même ligne une 2ᵉ fois → `404`.

Trace dans `audit_logs` : `order.item_remove`, avec le produit, la quantité, le montant et le motif.

### `POST /orders/{id}/cancel` — annuler une commande

Corps :

```json
{ "reason": "client parti" }
```

| Utilisateur | Condition |
|---|---|
| RESPONSABLE, ADMIN | Direct |
| CAISSIER | En-tête `X-Override-Token` obtenu par `POST /auth/override` avec `"action": "order.cancel"` |

Réponse `200` : `OrderResult` avec `status: "CANCELLED"`, `cancelled_at` et `cancelled_reason` remplis, `due_xof: 0`. **La table est libérée** et la commande est figée.

| Code | Cas | `meta` |
|---|---|---|
| `403 OVERRIDE_REQUIRED` | Caissier sans jeton valide | `action`, `reason` |
| `404 NOT_FOUND` | Commande inconnue | |
| `409 ORDER_NOT_EDITABLE` | Déjà soldée ou annulée (`status`), ou paiements déjà enregistrés (`reason: "has_payments"` — l'annulation avec remboursement viendra avec l'encaissement) | |

À tester : caissier sans jeton → `403` ; avec le jeton du responsable → `200` ; **rejouer le même jeton** sur une autre commande → `403` ; responsable sans jeton → `200`.

Trace dans `audit_logs` : `order.cancel`, avec le caissier (`user_id`) **et** le responsable qui a autorisé (`acting_as_user_id`).

Trace dans `audit_logs` : `order.cancel`.

> **Clôture de caisse :** une commande `OPEN` bloque la clôture (`409 SESSION_HAS_OPEN_ORDERS`). Tant que l'encaissement n'existe pas, il faut **annuler** les commandes de test avant de clôturer.

---

## 8. Clients entreprise et FNE

La **FNE** (facture normalisée électronique) est certifiée par la plateforme de la DGI. Elle est émise **à la demande**, sur une commande soldée, jamais automatiquement à l'encaissement. Plan et décisions : [`PLAN-FNE.md`](PLAN-FNE.md).

### Préparer le test

1. **Choisir le fournisseur FNE** dans `.env`, puis recréer le conteneur (`docker compose … up -d --force-recreate api`) :

   | `FNE_PROVIDER` | Effet |
   |---|---|
   | `manual` (défaut) | Aucun appel : le document passe en `MANUAL`, à saisir dans l'application FNE |
   | `mock` | FNE simulée, réponses au format réel, sans réseau : **pour tester l'API** |
   | `api` | Plateforme DGI (`FNE_API_BASE_URL`, `FNE_API_KEY`) |

2. **Renseigner les paramètres FNE** (pas encore de route `/settings`) :

   ```bash
   docker exec -i infra-db sh -c 'psql -U "$POSTGRES_USER" -d caisse' <<'SQL'
   INSERT INTO settings (key, value) VALUES
     ('fne.point_of_sale', '"CAISSE-1"'),
     ('fne.establishment', '"RESTAURANT CHEZ SYLLA PLUS"'),
     ('fne.walk_in_client', '{"company_name":"CLIENT DIVERS","phone":"0748735573","email":"restaurantmykpro@gmail.com"}')
   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
   SQL
   ```

3. **Solder une commande.** L'encaissement (lot L4) n'existe pas encore : on solde une commande de test directement en base (remplacer `<ORDER_ID>`) :

   ```bash
   docker exec -i infra-db sh -c 'psql -U "$POSTGRES_USER" -d caisse' <<'SQL'
   INSERT INTO payments (id, order_id, cash_session_id, method, amount_xof, change_xof, status,
                         idempotency_key, created_by_user_id, created_at)
     SELECT gen_random_uuid(), o.id, o.cash_session_id, 'CASH', o.total_ttc_xof, 0, 'CAPTURED',
            'test-' || o.id, o.opened_by_user_id, now()
     FROM orders o WHERE o.id = '<ORDER_ID>';
   UPDATE orders SET status = 'PAID', paid_xof = total_ttc_xof, due_xof = 0, paid_at = now()
     WHERE id = '<ORDER_ID>';
   SQL
   ```

### Statuts d'un document FNE

| `status` | `is_uncertain` | Sens | Action |
|---|---|---|---|
| `CERTIFIED` | false | Certifiée : `external_number` et `qr_payload` (lien de vérification DGI = page A4 imprimable) | — |
| `QUEUED` | false | FNE injoignable ou clé refusée : rien n'a été certifié | `retry` (renvoi automatique : à venir) |
| `FAILED` | false | Refusée par la DGI (données) | Corriger (client, paramètres) puis `retry` ou réémettre |
| `SUBMITTING` | **true** | Issue inconnue (délai dépassé, erreur 500) : la facture a **peut-être** été créée | Vérifier dans l'espace FNE, puis `resolve` |
| `MANUAL` | false | Mode manuel | Saisie dans l'application FNE |

Un document incertain n'est **jamais** renvoyé sans vérification : l'API FNE n'a aucune protection contre les doublons.

### `GET /customers?search=&ncc=` — rechercher un client entreprise

Rôle : CAISSIER. `search` cherche dans la raison sociale et le NCC ; `ncc` filtre sur le début du NCC. 50 résultats au plus.

### `POST /customers` — créer un client entreprise

```json
{ "company_name": "CGECI", "ncc": "9506466A", "phone": "0709080765", "email": "contact@cgeci.ci" }
```

Le NCC doit comporter **7 chiffres et 1 lettre** (espaces et minuscules acceptés : `"9506 466a"` devient `"9506466A"`). La FNE ne vérifie pas le NCC à la saisie : ce contrôle est le seul filet. Réponse `201` : le client.

| Code | Cas |
|---|---|
| `409 CUSTOMER_NCC_EXISTS` | NCC déjà enregistré ; `meta.customer_id` donne le client existant |
| `422 VALIDATION_ERROR` | Format du NCC (`meta.fields[0].loc = ["body","ncc"]`) |

### `POST /orders/{id}/fne` — émettre la FNE d'une commande

Rôle : CAISSIER.

```json
{ "template": "B2B", "customer_id": "…", "payment_method": null }
```

| Champ | Défaut | Sens |
|---|---|---|
| `template` | `B2C` | `B2C` particulier · `B2B` entreprise (NCC obligatoire) · `B2G` administration · `B2F` international |
| `customer_id` | null | Obligatoire sauf en `B2C` |
| `payment_method` | null | Sinon : moyen du plus gros montant encaissé (la FNE n'en accepte qu'un) |

Réponse `201` : `{ "document": {…}, "warnings": [] }`. L'issue se lit dans `document.status` et `warnings` (`FNE_REJECTED`, `FNE_UNCERTAIN`, `FNE_QUEUED`, `FNE_STICKER_LOW`) : un refus de la DGI n'est **pas** une erreur HTTP.

**Une seule FNE par commande** : si elle existe déjà (et n'a pas été refusée), elle est renvoyée telle quelle en `200`, sans nouvel appel à la DGI. Une FNE refusée est reconstruite et renvoyée.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Commande ou client inconnu |
| `409 FNE_ORDER_NOT_PAID` | Commande non soldée |
| `409 FNE_NOT_CONFIGURED` | Point de vente ou établissement non paramétré |
| `422 FNE_CUSTOMER_REQUIRED` | `B2B`, `B2G` ou `B2F` sans `customer_id` |
| `422 FNE_NCC_REQUIRED` | `B2B` avec un client sans NCC |
| `422 FNE_FIELD_REQUIRED` | Client de passage sans téléphone ou e-mail (`fne.walk_in_client`) |
| `422 FNE_NO_PAYMENT`, `FNE_VAT_RATE_UNMAPPED`, `FNE_PAYMENT_METHOD_UNMAPPED` | Paiement absent, taux de TVA ou moyen de paiement sans code FNE |

À tester (`FNE_PROVIDER=mock`) : émettre en B2C → `201 CERTIFIED` ; **rappeler** → `200`, même `id` ; B2B sans client → `422` ; commande non soldée → `409`.

### `GET /orders/{id}/fne` — FNE d'une commande

Rôle : CAISSIER. `404 NOT_FOUND` si aucune FNE n'a été émise.

### `GET /fne/documents?status=&business_date=` — suivi

Rôle : RESPONSABLE. 200 documents au plus, les plus récents en premier.

### `POST /fne/documents/{id}/retry` — renvoyer

Rôle : RESPONSABLE. Pour un document `QUEUED`, `FAILED` (reconstruit avec le client et les paramètres actuels) ou `PENDING`. Réponse `200` : `{ document, warnings }`.

`409 FNE_DOCUMENT_STATE` : `meta.reason = "uncertain"` (passer par `resolve`) ou `"not_retryable"` (certifié, manuel ou en cours).

### `POST /fne/documents/{id}/resolve` — trancher un cas incertain

Rôle : RESPONSABLE. Après vérification dans l'espace FNE, rubrique « Reçus et factures émis » :

```json
{ "is_certified": true, "external_number": "1304777N26000000023" }
```

- facture **numérotée** dans l'espace FNE → `is_certified: true` avec le n° relevé ; le document passe `CERTIFIED`. Il n'a alors pas les identifiants FNE nécessaires à un avoir par API ;
- facture **absente ou sans numéro** → `{ "is_certified": false }` ; le document est renvoyé.

`409 FNE_DOCUMENT_STATE` (`meta.reason = "not_uncertain"`) ; `422 VALIDATION_ERROR` si le n° manque.

### `POST /fne/documents/{id}/refund` — avoir

Rôle : RESPONSABLE. Avoir total ou partiel sur une FNE de vente certifiée par l'API :

```json
{ "items": [{ "order_item_id": "…", "quantity": 1 }] }
```

Réponse `201` : le document d'avoir (`type: "REFUND"`, `parent_document_id`), mêmes statuts que l'émission. Les quantités déjà reprises sont déduites.

| Code | Cas |
|---|---|
| `404 NOT_FOUND` | Document ou ligne absente de la FNE |
| `409 FNE_DOCUMENT_STATE` | `meta.reason = "not_refundable"` : non certifiée, manuelle, ou certifiée hors API |
| `422 FNE_REFUND_EXCEEDS` | Quantité supérieure au reste (`meta.available`) |

### `GET /fne/documents/{id}/duplicate` — duplicata

Rôle : CAISSIER. Le document certifié ; `qr_payload` ouvre la page A4 de la DGI à imprimer. `409 FNE_DOCUMENT_STATE` (`not_certified`) sinon.

### `GET /fne/pending-count` — compteur de la barre d'état

Rôle : CAISSIER. `{ "pending": 2, "uncertain": 1, "failed": 0 }` : documents en attente d'une action, dont incertains et refusés.

### `GET /fne/daily-summary?business_date=` — récapitulatif de la journée

Rôle : RESPONSABLE. Commandes soldées, part couverte par une FNE certifiée, documents en attente, ventes par groupe fiscal. Journée par défaut : celle de la session ouverte.

Trace dans `audit_logs` : `customer.create`, `fne.issue`, `fne.submit` (à chaque appel à la DGI), `fne.retry`, `fne.resolve`, `fne.refund`.

---

## 9. Scénario de test complet (curl + jq)

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
  -H 'Content-Type: application/json' -d '{"pin":"222222","action":"order.cancel"}' | jq
curl -s -X POST $API/auth/override -H "Authorization: Bearer $CT" -H 'X-Device-Id: poste-1' \
  -H 'Content-Type: application/json' -d '{"pin":"111111","action":"order.cancel"}' \
  | jq '{status, code}'

# 7. Catalogue et salle (avec le jeton du caissier)
curl -s $API/categories -H "Authorization: Bearer $CT" | jq '.items[] | {name, kind}'
curl -s "$API/products?search=jus" -H "Authorization: Bearer $CT" \
  | jq '.items[] | {name, price_xof, stock_quantity}'
curl -s $API/tables/board -H "Authorization: Bearer $CT" | jq '{business_date, summary, n: (.tables | length)}'

# 8. Session de caisse (avec le jeton du caissier)
#    Pas de GET /cash-registers pour l'instant : récupérer l'id via psql (bootstrap crée « Caisse 1 »)
REGISTER_ID=$(docker exec infra-db psql -U "$POSTGRES_USER" -d caisse -tAc \
  "select id from cash_registers limit 1")
KEY=$(cat /proc/sys/kernel/random/uuid)
curl -s -X POST $API/cash-sessions -H "Authorization: Bearer $CT" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' -d "{\"cash_register_id\":\"$REGISTER_ID\",\"opening_float_xof\":20000}" \
  | tee /tmp/session.json | jq
SESSION_ID=$(jq -r .id /tmp/session.json)
curl -s $API/tables/board -H "Authorization: Bearer $CT" | jq '.business_date'   # non nul désormais

# rejeu de la même clé → 200 + Idempotent-Replay: true, corps identique
curl -si -X POST $API/cash-sessions -H "Authorization: Bearer $CT" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' -d "{\"cash_register_id\":\"$REGISTER_ID\",\"opening_float_xof\":20000}" \
  | grep -i -E '^HTTP|Idempotent-Replay'

# mouvement de tiroir puis rapport X
curl -s -X POST $API/cash-sessions/$SESSION_ID/movements -H "Authorization: Bearer $CT" \
  -H 'Content-Type: application/json' -d '{"type":"OUT","amount_xof":2000,"reason":"achat glace"}' | jq
curl -s $API/cash-sessions/$SESSION_ID/x-report -H "Authorization: Bearer $CT" | jq '.expected_cash_xof'
# → 18000 (20000 - 2000)

# 9. Commandes (menu et tables de démo : caisse.cli seed --demo)
TABLE_1=$(curl -s $API/tables -H "Authorization: Bearer $CT" | jq -r '.items[0].id')
POISSON=$(curl -s "$API/products?search=poisson" -H "Authorization: Bearer $CT" | jq -r '.items[0].id')
ATTIEKE=$(curl -s "$API/products?search=atti" -H "Authorization: Bearer $CT" | jq -r '.items[0].id')
ORDER_ID=$(curl -s -X POST $API/orders -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d "{\"table_id\":\"$TABLE_1\",\"guests_count\":4}" | jq -r .order.id)
curl -s -X POST $API/orders/$ORDER_ID/items -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d "{\"product_id\":\"$POISSON\",\"quantity\":2,\"note\":\"bien cuit\"}" | jq '.order | {total_ttc_xof, total_ht_xof, total_vat_xof}'
ITEM_ID=$(curl -s -X POST $API/orders/$ORDER_ID/items -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d "{\"product_id\":\"$ATTIEKE\"}" | jq -r '.order.items[-1].id')
# table occupée : 2e commande refusée, plan de salle à jour
curl -s -X POST $API/orders -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d "{\"table_id\":\"$TABLE_1\"}" | jq '{status, code, meta}'
curl -s $API/tables/board -H "Authorization: Bearer $CT" | jq '.tables[0] | {label, status, order}'

# retrait d'une ligne par le caissier, motif obligatoire (sans motif → 422)
curl -s -X DELETE "$API/orders/$ORDER_ID/items/$ITEM_ID" -H "Authorization: Bearer $CT" | jq '{status, code}'
curl -s -X DELETE "$API/orders/$ORDER_ID/items/$ITEM_ID?reason=erreur%20de%20saisie" \
  -H "Authorization: Bearer $CT" | jq '.order | {total_ttc_xof, n: (.items | length)}'

# vente à emporter : Comptoir n° 1
curl -s -X POST $API/orders -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d '{"table_id":null}' | jq '.order | {order_number, counter_number}'

# pas encore d'encaissement : annuler les commandes ouvertes (responsable) pour pouvoir clôturer
RT=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"pin":"222222","device_id":"poste-1"}' | jq -r .access_token)
for ID in $(curl -s "$API/orders?status=OPEN" -H "Authorization: Bearer $CT" | jq -r '.items[].id'); do
  curl -s -X POST $API/orders/$ID/cancel -H "Authorization: Bearer $RT" -H 'Content-Type: application/json' \
    -d '{"reason":"test"}' | jq -c '.order | {order_number, status}'
done
curl -s $API/cash-sessions/$SESSION_ID/x-report -H "Authorization: Bearer $CT" | jq '.totals.controls'
# → cancelled_orders: 2, removed_items: 1

# clôture : Z n°1, écart nul si le comptage correspond
curl -s -X POST $API/cash-sessions/$SESSION_ID/close -H "Authorization: Bearer $CT" \
  -H "Idempotency-Key: $(cat /proc/sys/kernel/random/uuid)" -H 'Content-Type: application/json' \
  -d '{"counted_breakdown":{"10000":1,"5000":1,"1000":3},"notes":"RAS"}' | jq

# 10. Désactiver le caissier : son jeton est aussitôt refusé (401)
curl -s -X PATCH $API/users/$CAISSIER_ID -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"is_active":false}' | jq '{full_name, is_active}'
curl -s $API/auth/me -H "Authorization: Bearer $CT" | jq '{status, code}'

# 11. Blocage progressif sur un poste dédié : 4 × 401 puis 423
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

> Le scénario laisse deux utilisateurs de test en base, dont un désactivé, plus une session de caisse clôturée et deux commandes annulées. Comme les PIN doivent être uniques et qu'il ne peut y avoir qu'une session ouverte à la fois, relancer le scénario tel quel renverra `409` à l'étape 4 pour « Resp Test » (la session, elle, sera déjà clôturée et ne bloque rien). Changer les PIN avant de le relancer.

---

## 10. Pas encore testable

| Lot | Routes du contrat absentes |
|---|---|
| L2 | `POST/PATCH/DELETE /categories`, `POST/PATCH /products`, `PATCH /products/{id}/price`, `POST/PATCH /tables` |
| L3 | `POST /orders/{id}/reprint` (arrivera avec la file d'impression) |
| L4 | `/orders/{id}/payments`, `/refunds`, `/payment-methods`, `/printing/*` |
| L5 | `/stock/*` |
| L6 | `GET /fne/daily-summary/{id}/export` (export du récapitulatif figé à la clôture) |
| L5–L6 | `/reports/*` |
| Admin | `/settings`, `/cash-registers` |
