#!/usr/bin/env bash
# =========================================================================
# FLUIDIS — script de déploiement Railway du service `backend`.
# -------------------------------------------------------------------------
# Pré-requis (à faire UNE SEULE FOIS) :
#   1. Installer la CLI Railway : https://docs.railway.app/cli/installation
#   2. Créer un projet Railway dans le dashboard.
#   3. Y créer les plugins :   railway add --plugin postgresql
#                              railway add --plugin redis
#   4. Régler dans le dashboard le service backend :
#        Settings → Root Directory = "backend"
#      OU lancer ce script depuis le dossier backend/ (cd backend && bash ../deploy.sh)
#   5. Injecter les variables d'environnement — voir bloc "VARIABLES" plus bas.
#
# Usage : bash deploy.sh
# =========================================================================

set -euo pipefail

# ---- Couleurs lisibles ---------------------------------------------------
ROUGE='\033[0;31m'
VERT='\033[0;32m'
JAUNE='\033[1;33m'
BLEU='\033[0;34m'
RAZ='\033[0m'

info()  { echo -e "${BLEU}ℹ ${1}${RAZ}"; }
ok()    { echo -e "${VERT}✓ ${1}${RAZ}"; }
warn()  { echo -e "${JAUNE}⚠ ${1}${RAZ}"; }
err()   { echo -e "${ROUGE}✗ ${1}${RAZ}"; }

# ---- 0. Sanity check : CLI installée -------------------------------------
if ! command -v railway >/dev/null 2>&1; then
  err "La CLI 'railway' est introuvable. Installer : npm i -g @railway/cli"
  exit 1
fi

# ---- 1. Login (no-op si déjà connecté) -----------------------------------
info "Vérification de l'authentification Railway…"
if ! railway whoami >/dev/null 2>&1; then
  warn "Pas de session active — ouverture du flux de login dans le navigateur."
  railway login
else
  ok "Déjà connecté : $(railway whoami)"
fi

# ---- 2. Lier le projet local au projet Railway ---------------------------
# Si le dossier n'a pas encore de project_id, on lance le sélecteur interactif.
if [ ! -f ".railway/config.json" ] && ! railway status >/dev/null 2>&1; then
  info "Liaison au projet Railway (sélectionner un projet existant)…"
  railway link
  ok "Projet lié."
else
  ok "Projet déjà lié à : $(railway status --json 2>/dev/null | grep -o '\"name\":\"[^\"]*\"' | head -1 || echo 'projet courant')"
fi

# ---- 3. Vérifier que les variables critiques sont positionnées -----------
info "Vérification des variables d'environnement critiques…"
VARS_REQUISES=("DATABASE_URL" "REDIS_URL" "GOOGLE_ROUTES_API_KEY" "API_SECRET_KEY" "ALLOWED_ORIGINS" "OSRM_BASE_URL")
VARS_ACTUELLES=$(railway variables --json 2>/dev/null || echo "{}")
MANQUANTES=()
for v in "${VARS_REQUISES[@]}"; do
  if ! echo "$VARS_ACTUELLES" | grep -q "\"$v\""; then
    MANQUANTES+=("$v")
  fi
done
if [ ${#MANQUANTES[@]} -ne 0 ]; then
  warn "Variables manquantes sur Railway : ${MANQUANTES[*]}"
  warn "Voir backend/.env.railway pour le détail. Pour injecter en bloc :"
  cat <<'EOF'
  --------------------------------------------------------------
  railway variables set DATABASE_URL='${{Postgres.DATABASE_URL}}'
  railway variables set REDIS_URL='${{Redis.REDIS_URL}}'
  railway variables set OSRM_BASE_URL='https://VOTRE-OSRM.example'
  railway variables set GOOGLE_ROUTES_API_KEY='AIza...'
  railway variables set API_SECRET_KEY='<32+ caractères aléatoires>'
  railway variables set ALLOWED_ORIGINS='https://VOTRE-FRONT.up.railway.app'
  railway variables set TZ=Africa/Abidjan
  railway variables set COLLECT_INTERVAL_MINUTES=15
  railway variables set COLLECT_START_HOUR=7
  railway variables set COLLECT_END_HOUR=19
  --------------------------------------------------------------
EOF
  read -p "Continuer le déploiement quand même ? [y/N] " reponse
  if [[ ! "$reponse" =~ ^[Yy]$ ]]; then
    err "Déploiement annulé."
    exit 1
  fi
fi

# ---- 4. Déploiement ------------------------------------------------------
info "Lancement du déploiement (railway up)…"
railway up --detach
ok "Build et déploiement déclenchés. Logs en direct : railway logs"

# ---- 5. URL publique -----------------------------------------------------
info "Récupération de l'URL publique du service…"
# `railway domain` crée un domaine .up.railway.app s'il n'en existe pas,
# sinon affiche celui déjà attaché.
URL=$(railway domain 2>/dev/null | tail -1 | tr -d '[:space:]' || true)
if [ -n "$URL" ]; then
  ok "URL publique : https://${URL}"
  echo
  info "Vérifications post-déploiement :"
  echo "  curl https://${URL}/health"
  echo "  curl https://${URL}/collecte/status"
  echo "  curl https://${URL}/carte/etat"
  echo "  open https://${URL}/docs"
else
  warn "Aucune URL publique détectée. Lancer manuellement : railway domain"
fi

# ---- 6. Initialisation des données (à faire une seule fois) --------------
echo
warn "Si c'est le PREMIER déploiement, initialiser les 6 tronçons via :"
echo "  railway run python -m app.seed_troncons"
echo "  railway run python -m app.complete_troncons   # nécessite OSRM_BASE_URL atteignable"
