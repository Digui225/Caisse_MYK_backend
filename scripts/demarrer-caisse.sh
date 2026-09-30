#!/usr/bin/env bash
# =============================================================================
#  demarrer-caisse.sh — vérifie et démarre tout le backend de la caisse
# =============================================================================
#
#  À lancer après un redémarrage de la machine, ou dès que « quelque chose ne
#  marche pas ». Le script vérifie les étapes dans l'ordre où elles dépendent
#  les unes des autres, démarre ce qui manque, et explique chaque résultat :
#
#    1. Docker          installé, démarré, activé au boot, accessible
#    2. Réseau          infra_shared (partagé avec le PMS)
#    3. Base            conteneur infra-db (PostgreSQL du socle)
#    4. API             conteneur api de caisse-backend
#    5. Migrations      schéma de la base à jour
#    6. Santé           /health/ready (base, files d'attente, imprimante)
#    7. Impression      agent d'impression (service systemd hors Docker)
#    8. Accès réseau    adresses à donner au dev front
#
#  Usage :
#    ./scripts/demarrer-caisse.sh            vérifie ET démarre ce qui manque
#    ./scripts/demarrer-caisse.sh --check    vérifie seulement, ne touche à rien
#    ./scripts/demarrer-caisse.sh --help
#
#  Code de sortie : 0 = tout va bien (avertissements possibles), 1 = au moins
#  une erreur bloquante (la caisse ne peut pas fonctionner).
#
#  Référence : projet_caisse_MYK/04-EXPLOITATION-BACKEND.md (§1.1, §6, §8).
# =============================================================================

set -uo pipefail

# --- Emplacements (modifiables par variables d'environnement) ----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAISSE_DIR="${CAISSE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
INFRA_DIR="${INFRA_DIR:-$(cd "$CAISSE_DIR/../infra" 2>/dev/null && pwd || echo "$CAISSE_DIR/../infra")}"
API_PORT="${API_PORT:-8001}"
NETWORK="infra_shared"
DB_CONTAINER="infra-db"
WAIT_SECONDS="${WAIT_SECONDS:-90}"   # attente max. qu'un conteneur devienne « healthy »

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  --help|-h) sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^#  \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "Option inconnue : $1 (voir --help)"; exit 2 ;;
esac

# --- Affichage ---------------------------------------------------------------
if [[ -t 1 ]]; then
  B=$'\e[1m'; DIM=$'\e[2m'; R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; C=$'\e[36m'; N=$'\e[0m'
else
  B=""; DIM=""; R=""; G=""; Y=""; C=""; N=""
fi

ERRORS=()
WARNINGS=()
FIXED=()      # problèmes trouvés puis corrigés par le script
STEP=0

section() { STEP=$((STEP + 1)); printf '\n%s[%d] %s%s\n' "$B$C" "$STEP" "$1" "$N"; }
ok()      { printf '  %s✔ %s%s\n' "$G" "$1" "$N"; }
warn()    { printf '  %s⚠ %s%s\n' "$Y" "$1" "$N"; WARNINGS+=("$1"); }
err()     { printf '  %s✘ %s%s\n' "$R" "$1" "$N"; ERRORS+=("$1"); }
action()  { printf '  %s➜ %s%s\n' "$B" "$1" "$N"; }
# Constat d'un problème que le script va tenter de corriger (non compté au bilan).
notice()  { printf '  %s⚠ %s%s\n' "$Y" "$1" "$N"; }
# Correction réussie : comptée au bilan dans « remis en route ».
fixed()   { printf '  %s✔ %s%s\n' "$G" "$1" "$N"; FIXED+=("$1"); }
# Explication de ce que signifie le résultat, ou de ce qu'il faut faire.
explain() { local line; while IFS= read -r line; do printf '    %s%s%s\n' "$DIM" "$line" "$N"; done <<< "$1"; }

# Démarre quelque chose seulement hors mode --check.
may_start() {
  if (( CHECK_ONLY )); then
    explain "Mode --check : je ne démarre rien. Relancez sans --check pour corriger."
    return 1
  fi
  return 0
}

# Attend que le conteneur $1 soit « healthy ». Affiche un point toutes les 2 s.
wait_healthy() {
  local container="$1" elapsed=0 status
  printf '    %sAttente de l’état « healthy » (max %ss) ' "$DIM" "$WAIT_SECONDS"
  while (( elapsed < WAIT_SECONDS )); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null)"
    case "$status" in
      healthy) printf '%s\n' "$N"; return 0 ;;
      unhealthy|exited|dead) printf '%s\n' "$N"; return 1 ;;
    esac
    printf '.'
    sleep 2
    elapsed=$((elapsed + 2))
  done
  printf '%s\n' "$N"
  return 1
}

# Montre les dernières lignes de journal d'un conteneur, pour le diagnostic.
show_logs() {
  explain "Dernières lignes du journal de $1 :"
  docker logs --tail 15 "$1" 2>&1 | sed "s/^/      ${DIM}│ /;s/\$/${N}/"
}

printf '%sVérification du backend caisse%s — %s\n' "$B" "$N" "$(date '+%d/%m/%Y %H:%M:%S')"
printf '%sProjet : %s · Socle : %s%s\n' "$DIM" "$CAISSE_DIR" "$INFRA_DIR" "$N"
(( CHECK_ONLY )) && printf '%sMode --check : lecture seule, rien ne sera démarré.%s\n' "$Y" "$N"


# =============================================================================
section "Docker"
# =============================================================================

if ! command -v docker >/dev/null 2>&1; then
  err "Docker n'est pas installé"
  explain "Sans Docker, ni la base ni l'API ne peuvent tourner.
Installer Docker Engine + le plugin compose (04-EXPLOITATION §1.1)."
  printf '\n%sArrêt : rien d’autre ne peut être vérifié sans Docker.%s\n' "$R" "$N"
  exit 1
fi
ok "Docker est installé ($(docker --version | sed 's/Docker version //;s/,.*//'))"

if docker compose version >/dev/null 2>&1; then
  ok "Docker Compose v2 est disponible"
else
  err "La commande « docker compose » est introuvable"
  explain "Installer le paquet docker-compose-plugin. L'ancien « docker-compose »
(avec un tiret) n'est pas utilisé par ce projet."
  exit 1
fi

# Le service démarre-t-il au boot ?
if systemctl is-enabled docker >/dev/null 2>&1; then
  ok "Docker est activé au démarrage de la machine"
  explain "Après un redémarrage, Docker se relance tout seul, puis les conteneurs
en « restart: always » (la base et l'API) repartent sans intervention."
else
  notice "Docker n'est PAS activé au démarrage de la machine"
  explain "C'est très probablement pour ça que rien n'a démarré après le reboot."
  if may_start; then
    action "Activation au boot : sudo systemctl enable docker"
    if sudo systemctl enable docker; then fixed "Docker activé au démarrage de la machine"
    else err "Impossible d'activer Docker au démarrage (droits sudo ?)"; fi
  else
    WARNINGS+=("Docker n'est pas activé au démarrage de la machine")
  fi
fi

# Le service tourne-t-il maintenant ?
if systemctl is-active docker >/dev/null 2>&1; then
  ok "Le service Docker est démarré"
else
  notice "Le service Docker est arrêté"
  if may_start; then
    action "Démarrage : sudo systemctl start docker"
    if sudo systemctl start docker && systemctl is-active docker >/dev/null 2>&1; then
      fixed "Service Docker démarré"
    else
      err "Docker refuse de démarrer"
      explain "Voir la cause : sudo journalctl -u docker -n 50 --no-pager"
      exit 1
    fi
  else
    err "Docker est arrêté : rien d'autre ne peut tourner"
    exit 1
  fi
fi

# L'utilisateur peut-il parler au démon sans sudo ?
if docker_info_err="$(docker info 2>&1 >/dev/null)"; then
  ok "L'utilisateur $(id -un) peut piloter Docker sans sudo"
else
  if grep -qi 'permission denied' <<< "$docker_info_err"; then
    err "L'utilisateur $(id -un) n'a pas le droit d'utiliser Docker"
    explain "Ajouter l'utilisateur au groupe docker, puis fermer et rouvrir la session :
  sudo usermod -aG docker $(id -un)"
  else
    err "Le démon Docker ne répond pas"
    explain "$docker_info_err"
  fi
  exit 1
fi


# =============================================================================
section "Réseau Docker partagé ($NETWORK)"
# =============================================================================

if docker network inspect "$NETWORK" >/dev/null 2>&1; then
  ok "Le réseau $NETWORK existe"
  explain "C'est par lui que l'API joint la base (adresse « db:5432 »)."
else
  notice "Le réseau $NETWORK n'existe pas"
  explain "Il est créé une seule fois à l'installation ; sans lui, ni la base ni
l'API ne peuvent démarrer (04-EXPLOITATION §1.3)."
  if may_start; then
    action "Création : docker network create $NETWORK"
    if docker network create "$NETWORK" >/dev/null; then fixed "Réseau $NETWORK créé"
    else err "Impossible de créer le réseau $NETWORK"; fi
  else
    err "Réseau $NETWORK absent"
  fi
fi


# =============================================================================
section "Base de données ($DB_CONTAINER, socle infra)"
# =============================================================================

db_ok=0
if [[ ! -f "$INFRA_DIR/docker-compose.yml" ]]; then
  err "Socle introuvable : $INFRA_DIR/docker-compose.yml"
  explain "Le dossier infra doit être à côté de caisse-backend, ou indiqué par
INFRA_DIR=/chemin/vers/infra ./scripts/demarrer-caisse.sh"
elif [[ ! -f "$INFRA_DIR/.env" ]]; then
  err "Fichier $INFRA_DIR/.env absent"
  explain "Il contient les mots de passe PostgreSQL. Le recréer depuis .env.example
(04-EXPLOITATION §1.4). Attention : les mots de passe doivent être ceux
utilisés à la création du volume, sinon l'API ne pourra plus se connecter."
else
  db_state="$(docker inspect --format '{{.State.Status}}' "$DB_CONTAINER" 2>/dev/null || echo absent)"
  case "$db_state" in
    running) ok "Le conteneur $DB_CONTAINER tourne" ;;
    absent)  notice "Le conteneur $DB_CONTAINER n'existe pas" ;;
    *)       notice "Le conteneur $DB_CONTAINER est arrêté (état « $db_state »)" ;;
  esac

  if [[ "$db_state" != running ]]; then
    if may_start; then
      action "Démarrage : docker compose up -d (dans $INFRA_DIR)"
      docker compose --project-directory "$INFRA_DIR" -f "$INFRA_DIR/docker-compose.yml" up -d 2>&1 \
        | sed "s/^/      ${DIM}│ /;s/\$/${N}/"
      db_state="$(docker inspect --format '{{.State.Status}}' "$DB_CONTAINER" 2>/dev/null || echo absent)"
      if [[ "$db_state" == running ]]; then fixed "Base de données ($DB_CONTAINER) démarrée"
      else err "La base n'a pas pu être démarrée (état « $db_state »)"; fi
    else
      err "La base est arrêtée : l'API ne peut pas fonctionner"
    fi
  fi

  if [[ "$db_state" == running ]]; then
    if wait_healthy "$DB_CONTAINER"; then
      ok "PostgreSQL accepte les connexions (healthy)"
      db_ok=1
      if dbs="$(docker exec "$DB_CONTAINER" sh -c 'psql -U "$POSTGRES_USER" -Atc "select datname from pg_database"' 2>/dev/null)"; then
        if grep -qx caisse <<< "$dbs"; then ok "La base « caisse » existe"
        else err "La base « caisse » est absente de l'instance"; fi
        grep -qx hotel_paix <<< "$dbs" \
          && explain "La base « hotel_paix » (PMS) est aussi présente dans le socle."
      fi
    else
      err "PostgreSQL ne devient pas « healthy »"
      explain "Causes fréquentes (04-EXPLOITATION §8) : port déjà pris par un autre
PostgreSQL (sudo lsof -i :5433), volume corrompu, disque plein (df -h)."
      show_logs "$DB_CONTAINER"
    fi
  elif [[ "$db_state" != absent ]] && (( ! CHECK_ONLY )); then
    show_logs "$DB_CONTAINER"
  fi
fi


# =============================================================================
section "API (caisse-backend)"
# =============================================================================

api_ok=0
COMPOSE_API=(docker compose --project-directory "$CAISSE_DIR" -f "$CAISSE_DIR/docker-compose.yml")
if [[ ! -f "$CAISSE_DIR/.env" ]]; then
  err "Fichier $CAISSE_DIR/.env absent"
  explain "Il contient DATABASE_URL et JWT_SECRET. Le recréer depuis .env.example
(04-EXPLOITATION §1.6)."
else
  api_id="$("${COMPOSE_API[@]}" ps -a -q api 2>/dev/null)"
  api_state="absent"
  [[ -n "$api_id" ]] && api_state="$(docker inspect --format '{{.State.Status}}' "$api_id" 2>/dev/null)"
  case "$api_state" in
    running) ok "Le conteneur de l'API tourne" ;;
    absent)  notice "Le conteneur de l'API n'existe pas" ;;
    *)       notice "Le conteneur de l'API est arrêté (état « $api_state »)" ;;
  esac

  if [[ "$api_state" != running ]]; then
    if (( ! db_ok )); then
      err "L'API ne peut pas démarrer tant que la base n'est pas prête (étape précédente)"
    elif may_start; then
      if [[ "$api_state" == absent ]] && [[ -n "$(ss -ltnH "sport = :$API_PORT" 2>/dev/null)" ]]; then
        warn "Le port $API_PORT est déjà occupé par un autre programme"
        explain "Le démarrage va échouer. Identifier le programme : sudo ss -ltnp 'sport = :$API_PORT'"
      fi
      action "Démarrage : docker compose up -d (dans $CAISSE_DIR)"
      explain "Si l'image n'existe pas encore, Docker la construit : compter 1 à 2 minutes."
      "${COMPOSE_API[@]}" up -d 2>&1 | sed "s/^/      ${DIM}│ /;s/\$/${N}/"
      api_id="$("${COMPOSE_API[@]}" ps -a -q api 2>/dev/null)"
      api_state="absent"
      [[ -n "$api_id" ]] && api_state="$(docker inspect --format '{{.State.Status}}' "$api_id" 2>/dev/null)"
      if [[ "$api_state" == running ]]; then fixed "API démarrée"
      else err "L'API n'a pas pu être démarrée (état « $api_state »)"; fi
    else
      err "L'API est arrêtée"
    fi
  fi

  if [[ "$api_state" == running ]]; then
    api_name="$(docker inspect --format '{{.Name}}' "$api_id" | sed 's|^/||')"
    if wait_healthy "$api_id"; then
      ok "L'API répond (healthy)"
      api_ok=1
      restarts="$(docker inspect --format '{{.RestartCount}}' "$api_id")"
      if (( restarts > 0 )); then
        warn "L'API a redémarré seule $restarts fois (plantages)"
        explain "Si ce nombre augmente d'un lancement à l'autre, elle plante en boucle :
docker compose logs api --tail 50"
      fi
    else
      err "L'API ne devient pas « healthy »"
      explain "Causes fréquentes (04-EXPLOITATION §8) : DATABASE_URL erroné dans .env,
mot de passe différent de CAISSE_DB_PASSWORD du socle, JWT_SECRET vide."
      show_logs "$api_name"
    fi
  elif [[ -n "$api_id" ]] && (( ! CHECK_ONLY )) && (( db_ok )); then
    show_logs "$(docker inspect --format '{{.Name}}' "$api_id" | sed 's|^/||')"
  fi
fi


# =============================================================================
section "Migrations de la base"
# =============================================================================

if (( api_ok )); then
  current="$("${COMPOSE_API[@]}" exec -T api alembic current 2>/dev/null | tail -1)"
  if grep -q '(head)' <<< "$current"; then
    ok "Schéma à jour (révision ${current%% *})"
  elif [[ -z "$current" ]]; then
    warn "Aucune migration appliquée : la base est vide"
    explain "Première installation ? Enchaîner (04-EXPLOITATION §2 et §3) :
  docker compose exec api alembic upgrade head
  docker compose exec api python -m caisse.cli bootstrap
  docker compose exec api python -m caisse.cli create-user"
  else
    warn "Des migrations sont en attente (révision actuelle : ${current:-inconnue})"
    explain "Le code est plus récent que la base. Sauvegarder puis appliquer :
  docker compose exec api alembic upgrade head"
  fi
else
  explain "Vérification impossible : l'API ne tourne pas."
fi


# Interprète la réponse de /health/ready : une ligne « niveau|message|explication » par point.
HEALTH_PY="$(cat <<'PY'
import json, sys
d = json.loads(sys.argv[1])
out = []
out.append(("ok" if d.get("database") == "ok" else "err",
            f"Base de données : {d.get('database')}",
            "L'API lit et écrit dans PostgreSQL." if d.get("database") == "ok"
            else "L'API tourne mais ne joint pas la base : vérifier DATABASE_URL."))
q = d.get("queues") or {}
if q:
    pf, pq, fp = q.get("print_failed", 0), q.get("print_queued", 0), q.get("fne_pending", 0)
    out.append(("warn" if pf else "ok", f"Impressions en échec : {pf}",
                "Tickets à relancer depuis l'écran Impression." if pf else ""))
    out.append(("warn" if pq else "ok", f"Impressions en attente : {pq}",
                "Des tickets attendent l'imprimante." if pq else ""))
    out.append(("warn" if fp else "ok", f"Factures FNE non transmises : {fp}",
                "Elles partiront quand Internet et le worker seront disponibles." if fp else ""))
p = d.get("printer") or {}
if p.get("agent_online"):
    out.append(("ok" if p.get("printer_online") else "warn",
                f"Imprimante : {'en ligne' if p.get('printer_online') else 'hors ligne'}"
                f" (papier : {p.get('paper')})", ""))
else:
    out.append(("info", "Agent d'impression injoignable",
                "Normal sur un poste de développement sans imprimante. La vente n'est pas bloquée."))
for level, msg, detail in out:
    print(f"{level}|{msg}|{detail}")
PY
)"

# =============================================================================
section "Santé de l'API (/health/ready)"
# =============================================================================

if (( api_ok )); then
  if ready="$(curl -s -m 5 "http://localhost:$API_PORT/health/ready")" && [[ -n "$ready" ]]; then
    while IFS='|' read -r level msg detail; do
      case "$level" in
        ok)   ok "$msg" ;;
        warn) warn "$msg" ;;
        err)  err "$msg" ;;
        info) printf '  %sℹ %s%s\n' "$C" "$msg" "$N" ;;
      esac
      [[ -n "$detail" ]] && explain "$detail"
    done < <(python3 -c "$HEALTH_PY" "$ready")
  else
    err "/health/ready ne répond pas sur le port $API_PORT"
    explain "Le conteneur tourne mais n'est pas joignable depuis la machine :
vérifier le port publié avec docker compose ps."
  fi
else
  explain "Vérification impossible : l'API ne tourne pas."
fi


# =============================================================================
section "Agent d'impression (hors Docker)"
# =============================================================================

if systemctl list-unit-files caisse-print-agent.service >/dev/null 2>&1 \
    && systemctl list-unit-files caisse-print-agent.service | grep -q caisse-print-agent; then
  if systemctl is-active caisse-print-agent >/dev/null 2>&1; then
    ok "Le service caisse-print-agent tourne"
  else
    notice "Le service caisse-print-agent est installé mais arrêté"
    if ! may_start; then
      WARNINGS+=("Agent d'impression arrêté : rien ne s'imprimera")
    else
      action "Démarrage : sudo systemctl start caisse-print-agent"
      sudo systemctl start caisse-print-agent && fixed "Agent d'impression démarré" \
        || err "L'agent refuse de démarrer : journalctl -u caisse-print-agent -n 50"
    fi
  fi
else
  printf '  %sℹ Agent d’impression non installé%s\n' "$C" "$N"
  explain "Normal sur un poste de développement. Sur la machine de la caisse, il
s'installe avec print-agent/install.sh une fois l'imprimante branchée
(04-EXPLOITATION §1.7). Sans lui, la vente fonctionne mais rien ne s'imprime."
fi


# =============================================================================
section "Accès depuis le réseau local"
# =============================================================================

lan_ips="$(ip -4 -o addr show scope global 2>/dev/null | awk '$2 !~ /^(docker|br-|veth)/ {split($4,a,"/"); print a[1]}')"
if [[ -n "$lan_ips" ]]; then
  for ipaddr in $lan_ips; do
    ok "Adresse réseau de la machine : $ipaddr"
    explain "À donner au dev front (même Wi-Fi) :
  API     http://$ipaddr:$API_PORT/api/v1
  Swagger http://$ipaddr:$API_PORT/docs
Cette adresse est attribuée par le routeur et peut changer après un redémarrage."
  done
else
  warn "Aucune adresse réseau trouvée : la machine n'est connectée à aucun réseau"
  explain "L'API reste utilisable en local : http://localhost:$API_PORT/docs"
fi

cors="$(grep -E '^CORS_ORIGINS=' "$CAISSE_DIR/.env" 2>/dev/null | cut -d= -f2-)"
if [[ "$cors" == "*" ]]; then
  explain "CORS ouvert à toutes les origines (CORS_ORIGINS=*) : réglage de développement."
elif [[ -n "$cors" ]]; then
  explain "CORS limité à : $cors"
fi


# =============================================================================
#  Bilan
# =============================================================================

printf '\n%s══════════════════════════ Bilan ══════════════════════════%s\n' "$B" "$N"
if (( ${#FIXED[@]} )); then
  printf '%sRemis en route par ce script :%s\n' "$B" "$N"
  for f in "${FIXED[@]}"; do printf '  %s✔ %s%s\n' "$G" "$f" "$N"; done
  printf '\n'
fi
if (( ${#ERRORS[@]} == 0 && ${#WARNINGS[@]} == 0 )); then
  printf '%s✔ Tout est en ordre : la caisse est prête.%s\n' "$G$B" "$N"
elif (( ${#ERRORS[@]} == 0 )); then
  printf '%s✔ La caisse fonctionne%s, avec %d point(s) à surveiller :\n' "$G$B" "$N" "${#WARNINGS[@]}"
  for w in "${WARNINGS[@]}"; do printf '  %s⚠ %s%s\n' "$Y" "$w" "$N"; done
else
  printf '%s✘ %d erreur(s) bloquante(s)%s — la caisse ne peut pas fonctionner :\n' "$R$B" "${#ERRORS[@]}" "$N"
  for e in "${ERRORS[@]}"; do printf '  %s✘ %s%s\n' "$R" "$e" "$N"; done
  if (( ${#WARNINGS[@]} )); then
    printf 'Et %d avertissement(s) :\n' "${#WARNINGS[@]}"
    for w in "${WARNINGS[@]}"; do printf '  %s⚠ %s%s\n' "$Y" "$w" "$N"; done
  fi
  printf '\n%sRelire les explications ci-dessus, puis 04-EXPLOITATION-BACKEND.md §8 (Dépannage).%s\n' "$DIM" "$N"
fi
printf '%sRelancer ce script à tout moment : %s/scripts/demarrer-caisse.sh%s\n' "$DIM" "$CAISSE_DIR" "$N"

(( ${#ERRORS[@]} == 0 ))
