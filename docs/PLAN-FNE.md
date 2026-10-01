# Plan d'implémentation — FNE (Facture Normalisée Électronique, DGI Côte d'Ivoire)

Référence : *Procédure d'interfaçage des entreprises par API*, DGI, mai 2025.
Document vivant : on coche, on corrige et on note les découvertes au fil de l'intégration.

## 0. Rappel de l'API

| | |
|---|---|
| URL test | `http://54.247.95.108/ws` (URL de prod transmise par la DGI après validation) |
| Auth | `Authorization: Bearer <API KEY>` (onglet « Paramétrage » de l'espace FNE) |
| Vente | `POST {url}/external/invoices/sign` — `invoiceType: "sale"` |
| Avoir | `POST {url}/external/invoices/{invoice.id}/refund` — `items: [{id, quantity}]` |
| Réponse | `reference` (n° FNE), `token` (URL de vérification → QR), `balance_sticker`, `warning`, `invoice` (avec `id` et `items[].id`) |
| Erreurs | 400 requête invalide (détail par champ dans `errors`), 401 clé invalide, 500 erreur serveur (**peut laisser une facture créée**) |
| Établissement | `RESTAURANT CHEZ SYLLA PLUS` |

## 1. Décisions de conception

| # | Décision | Statut |
|---|---|---|
| D1 | **Quand émettre** : **à la demande** via `POST /orders/{id}/fne`, sur une commande soldée. Pas de certification automatique à l'encaissement : `fiscal_document` vaut `null` dans la réponse de paiement (écart avec l'exemple v1.1 du contrat §4.6, à signaler au front) | **décidé** 01/10 |
| D2 | **Prix HT** : `amount` = prix unitaire HT calculé depuis le TTC. On envoie un HT décimal (4 décimales) si l'API l'accepte, sinon arrondi entier ; l'écart TTC caisse ↔ TTC FNE est stocké et surveillé | à valider en sonde (phase 1) |
| D3 | **Codes TVA** : 18 → `TVA`, 9 → `TVAB`, 0 → `TVAD` (paramètre `fne.vat_codes`). Un seul code par article (exigé par l'API). ⚠ Le restaurant est au **régime TEE** (en-tête FNE) et la FNE décrit `TVAD` comme l'exonération « TEE, TCE, Microentreprise » : si le comptable confirme, **tous les produits passent à 0 % / `TVAD`** (taux par défaut de la caisse aujourd'hui : 18 %) | codes décidés 01/10 ; vraie FNE du 01/10 entièrement en `TVAD` → passer la caisse à 0 % (confirmation comptable souhaitée) |
| D9 | `clientSellerName` = nom du caissier connecté (rempli sur les vraies FNE du restaurant) ; `measurementUnit` = `U` ; `reference` = code produit | proposé |
| D10 | **Impression** : la FNE est remise en **A4** (pratique du restaurant). Pas de FNE sur le ticket 80 mm : la caisse expose le lien de vérification FNE (`token`) que le front ouvre pour impression A4 ; le ticket de caisse peut mentionner le n° FNE. À vérifier en test : la page de vérification s'imprime-t-elle en A4 complet ? Imprimante A4 au poste de caisse ? | **décidé** 01/10 (A4) |
| D11 | Point de vente et établissement = **paramètres** (`fne.point_of_sale`) : `CAISSE-1` en test, « Service Facturation » en production | proposé |
| D4 | **Moyen de paiement** : CASH→`cash`, CARD→`card`, MOBILE_MONEY→`mobile-money`, BANK_TRANSFER→`transfer`, CREDIT→`deferred`, OTHER à paramétrer. Paiement mixte : moyen du plus gros montant | proposé |
| D5 | **Pas d'idempotence côté FNE** : un délai dépassé = résultat **incertain**, jamais renvoyé automatiquement. Seules les erreurs certaines (connexion refusée, 401, 502/503) repartent en file ; **un 500 est incertain** (constaté : facture créée non signée). Pour ne pas ajouter de valeur d'énumération (cassant en pratique, contrat §6), l'incertain reste en `SUBMITTING` avec un champ ajouté `is_uncertain: true` | proposé |
| D6 | **Une seule FNE de vente active par commande** (index unique partiel), donc pas de double certification par double clic | proposé |
| D7 | `DAILY_SUMMARY` n'a pas d'équivalent dans l'API. Avec D1, il couvre les tickets sans FNE (`/fne/daily-summary`, contrat §4.8) | proposé |
| D8 | Client de passage (B2C) : nom / téléphone / e-mail par défaut paramétrables (`fne.walk_in_client`) — l'API les exige même en B2C | à valider en sonde |

## 2. Cycle de vie d'un document FNE

```
PENDING ──(soumission)──► SUBMITTING ──200──► CERTIFIED
                             │
                             ├─ connexion refusée / 502 / 503 / 401 ─► QUEUED ──(worker, backoff)──► SUBMITTING
                             ├─ 400 (données invalides) ─────► FAILED   (correction puis nouvel essai manuel)
                             └─ délai dépassé / 500 / 504 ────► SUBMITTING + is_uncertain (vérification dans
                                                                         l'espace FNE : « certifiée » avec n° saisi,
                                                                         ou « non certifiée » → renvoi)
MANUAL : document traité hors API.
```

## 3. Phases

### Phase 1 — Sonde sur l'environnement de test
- [x] Clé API de test vérifiée (01/10) : acceptée, la plateforme répond depuis le poste local
- [x] Commande `python -m caisse.cli fne-probe` : facture B2C (TVA 18 % + TVAD) puis avoir d'une unité (`--refund`) ; requêtes et réponses écrites dans `fne-probe/<horodatage>/` (hors git)
- [ ] Lancer la sonde et ramener les traces dans `tests/fixtures/fne/`
- [ ] Questions à trancher : HT décimal accepté (D2) ? valeurs client acceptées en B2C (D8) ? arrondi du TTC FNE ? format de `token` ?
- Lancement (`.env` avec `FNE_API_BASE_URL=http://54.247.95.108/ws` et `FNE_API_KEY`, puis `docker compose up -d` pour recharger) :
  ```bash
  docker compose exec api python -m caisse.cli fne-probe \
    --point-of-sale "<point de vente FNE>" \
    --client-phone 07XXXXXXXX --client-email contact@exemple.ci --refund --yes
  # établissement par défaut : RESTAURANT CHEZ SYLLA PLUS ; variante : --ht-decimals 0
  ```

### Phase 2 — Domaine pur (sans I/O)
- [x] `domain/fne.py` : construction de la requête depuis une commande figée (lignes, TVA, moyen de paiement, template B2C/B2B/B2G/B2F, client), calcul HT, avoir
- [x] Tests unitaires (`tests/unit/domain/test_fne.py`)

### Phase 3 — Client HTTP (`infrastructure/fne/`)
- [x] Port `FneProvider` : `sign(payload)` et `refund(invoice_id, payload)` ; `FneResult` (`invoice_id`, `items`, montants, `balance_sticker`, `warning`)
- [x] `HttpFneProvider` (httpx) avec classification des erreurs : `FneRejectedError` (4xx), `FneAuthError` (401), `FneUnavailableError` (connexion impossible, 502/503), `FneUncertainError` (délai dépassé après envoi, 500, 504, réponse illisible)
- [x] `MockFneProvider` (dév. et tests) et sélection selon `FNE_PROVIDER`
- [x] Tests du client avec `httpx.MockTransport` (`tests/unit/infrastructure/test_fne_client.py`) ; à compléter avec les traces réelles de la sonde

### Phase 4 — Schéma (migration Alembic réversible)
- [ ] `fne_documents` : `fne_invoice_id`, `parent_document_id` (avoir → vente), `items_map` (JSONB : ligne caisse → id article FNE), `fne_amount_ttc`, `sticker_balance`, `is_uncertain`
- [ ] Enum `FneDocumentType.REFUND` (prévenir le front, contrat §6)
- [ ] Index unique partiel : une vente FNE non échouée par commande (D6)
- [ ] Paramètres métier : `fne.point_of_sale`, `fne.establishment`, `fne.vat_codes`, `fne.payment_methods`, `fne.walk_in_client`, `fne.sticker_alert_threshold`

### Phase 5 — Service (`services/fne_service.py`)
- [ ] `create_for_order` : copie figée de la commande soldée, idempotent par commande
- [ ] `submit` : verrou de ligne, passage en `SUBMITTING` commité **avant** l'appel, appel synchrone (`fne_sync_timeout_seconds`), transitions de la §2, audit
- [ ] `refund` : avoir total ou partiel à partir de `items_map`
- [ ] `retry`, `resolve_uncertain` (certifiée avec n° saisi, ou non certifiée → renvoi), `mark_manual`
- [ ] Alerte stock de stickers (`warning` ou solde sous le seuil) → journal + `/health`

### Phase 6 — API (contrat §4.8, + ajouts non cassants)
- [ ] `GET /customers?search=&ncc=` · `POST /customers` — contrôle du **format** du NCC côté caisse (7 chiffres + 1 lettre d'après les exemples DGI, à confirmer) : la FNE ne le vérifie pas à la validation
- [ ] `POST /orders/{id}/fne` : template (B2C par défaut, B2B/B2G avec `customer_id`), commande soldée obligatoire, soumission synchrone 4 s puis file
- [ ] `GET /fne/documents?status=&business_date=` · `POST /fne/documents/{id}/retry` (R)
- [ ] `GET /fne/documents/{id}/duplicate` (C) · `GET /fne/pending-count` (C)
- [ ] `GET /fne/daily-summary?business_date=` · `GET /fne/daily-summary/{id}/export` (R)
- [ ] Ajouts (endpoints nouveaux = non cassants) : `POST /fne/documents/{id}/resolve` (R, cas incertain) · `POST /fne/documents/{id}/refund` (R, avoir)
- [ ] Erreurs : refus DGI → `FNE_REJECTED` ; nouveaux codes `FNE_NCC_REQUIRED`, `FNE_VAT_RATE_UNMAPPED`… à ajouter au catalogue §2 avec le front
- [ ] Tests d'intégration avec `MockFneProvider`

### Phase 7 — Worker de renvoi
- [ ] `python -m caisse.cli fne-worker` (service dans `docker-compose.yml`) : traite les `QUEUED` échus avec un backoff exponentiel plafonné, ne touche jamais aux documents incertains (`is_uncertain`)

### Phase 8 — Branchements (dépendent de L4)
- [ ] Remboursement → avoir FNE
- [ ] FNE remise en A4 via le lien de vérification (`token`) renvoyé par l'API (D10) ; n° FNE optionnel sur le ticket de caisse

### Phase 9 — Validation DGI et production
- [ ] Jeu de spécimens : B2C espèces, B2C mobile money, B2B avec NCC, multi-taux, avoir partiel
- [ ] Envoi à support.fne@dgi.gouv.ci (factures FNE + factures correspondantes de la caisse)
- [ ] Après validation : URL et clé de prod, surveillance des journaux

## 4. Journal des découvertes

| Date | Constat | Conséquence |
|---|---|---|
| 01/10/2026 | Contrat d'API : routes FNE au §4.8, statuts au §4.6 (`PENDING`, `SUBMITTING`, `CERTIFIED`, `QUEUED`, `FAILED`, `MANUAL`) | D5 sans nouvelle valeur d'énumération ; phase 6 alignée |
| 01/10/2026 | Clé de test valide : corps vide → 400 avec détail par champ ; clé bidon → 401 `"error": "unauthorized"` (la procédure indiquait `unauthorized_exception`) | Ne pas se fier au libellé `error`, seulement au statut HTTP |
| 01/10/2026 | Champs exigés : `invoiceType`, `paymentMethod`, `template`, `clientCompanyName`, `clientPhone` (**chaîne**, la procédure dit `int`), `clientEmail`, `pointOfSale`, `establishment`, `items` ; `isRne` non exigé | `clientPhone` envoyé en chaîne |
| 01/10/2026 | `items` : « exactly one tax » parmi `TVA`, `TVAB`, `TVAC`, `TVAD`, **`TVAE`** (absent de la procédure) | Un code par article ; demander à la DGI ce que couvre `TVAE` |
| 01/10/2026 | `pointOfSale` inconnu → 400 `"Point of sale is invalid"`. Il faut créer un point de vente dans l'espace FNE (outil « Application FNE », l'autre choix étant « TPE ») ; `CAISSE-1` créé | `fne.point_of_sale = "CAISSE-1"` |
| 01/10/2026 | Avec `CAISSE-1` : validation passée puis 500 `invoice_signing_error`, identique avec un HT à 4 décimales ou entier | Cause côté compte FNE (stickers, établissement incomplet ou point de vente non actif) ; un 500 de signature doit être vérifié dans l'espace FNE avant d'être considéré « sans danger » |
| 01/10/2026 | Les deux 500 ont laissé **deux factures « Vente » sans numéro** dans « Reçus et factures émis » ; solde de stickers à 0 FCFA | 500 reclassé incertain ; demander des stickers de test à la DGI. Montants FNE : 6 932 HT + 1 068 TVA = 8 000 TTC, identiques à la caisse avec un HT à 4 décimales comme entier (D2 rassurante) |
| 01/10/2026 | Essai B2B avec un NCC absurde (`0000000X`) : pas de 400 sur `clientNcc`, même 500 de signature qu'en B2C | La FNE ne vérifie pas le NCC à la validation → contrôle de format côté caisse ; le blocage de signature ne dépend pas du modèle |
| 01/10/2026 | Ébauche PDF téléchargée depuis l'espace FNE (essai de 12:12) : pas de n° ni de QR ; émetteur repris de l'espace FNE (NCC 1304777N, RCCM, adresse, PDV) ; P.U HT affiché arrondi (2 966), totaux exacts (6 932 + 1 068 = 8 000) ; **régime d'imposition TEE** | D3 : taux de TVA de la caisse à faire confirmer ; format NCC 7 chiffres + lettre confirmé ; la caisse n'envoie pas les données de l'émetteur |
| 01/10/2026 | Vraie FNE de production (photo) : n° `1304777N26000000023` = NCC + année + n° d'ordre sur 9 chiffres ; tous les articles en `TVAD (0)`, TVA 0 ; client B2B CGECI `9506466A` affiché avec son régime (« RS employeur ») retrouvé par la FNE ; vendeur, unité `U` et références renseignés ; PDV de prod « Service Facturation » ; coordonnées du restaurant différentes du test ; format A4 | TEE confirmé en pratique (D3) ; la FNE connaît les NCC ; D9, D10, D11 ; la caisse continuera la série déjà entamée via l'application FNE (éviter la double facturation d'une même vente) |
