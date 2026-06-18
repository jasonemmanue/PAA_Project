#!/usr/bin/env bash
# ============================================================
# Préparation de l'extrait OSRM (Côte d'Ivoire, profil voiture)
# ------------------------------------------------------------
# À exécuter UNE SEULE FOIS avant le premier `docker compose up`.
# Re-exécuter uniquement si l'extrait OSM doit être rafraîchi.
# ============================================================
set -euo pipefail

# Dossier contenant ce script = dossier osrm-data/ partagé avec le service `osrm`
DATA_DIR="$(cd "$(dirname "$0")" && pwd)"
PBF_URL="https://download.geofabrik.de/africa/ivory-coast-latest.osm.pbf"
PBF_FILE="ivory-coast-latest.osm.pbf"
OSRM_IMAGE="osrm/osrm-backend:latest"

echo ">>> Dossier de données : ${DATA_DIR}"

# 1. Téléchargement de l'extrait OSM s'il est absent
if [ ! -f "${DATA_DIR}/${PBF_FILE}" ]; then
  echo ">>> Téléchargement de l'extrait Côte d'Ivoire depuis Geofabrik"
  curl -L --fail -o "${DATA_DIR}/${PBF_FILE}" "${PBF_URL}"
else
  echo ">>> Extrait déjà présent, étape de téléchargement ignorée."
fi

# 2. osrm-extract avec le profil voiture (car.lua fourni par l'image)
echo ">>> Étape 1/3 : osrm-extract (profil car)"
docker run --rm -t \
  -v "${DATA_DIR}:/data" \
  "${OSRM_IMAGE}" \
  osrm-extract -p /opt/car.lua "/data/${PBF_FILE}"

# 3. osrm-partition
echo ">>> Étape 2/3 : osrm-partition"
docker run --rm -t \
  -v "${DATA_DIR}:/data" \
  "${OSRM_IMAGE}" \
  osrm-partition "/data/ivory-coast-latest.osrm"

# 4. osrm-customize
echo ">>> Étape 3/3 : osrm-customize"
docker run --rm -t \
  -v "${DATA_DIR}:/data" \
  "${OSRM_IMAGE}" \
  osrm-customize "/data/ivory-coast-latest.osrm"

echo ">>> Préparation OSRM terminée. Vous pouvez lancer : docker compose up"
