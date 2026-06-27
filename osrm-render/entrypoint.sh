#!/bin/bash
# Entrypoint OSRM — téléchargement + indexation au premier démarrage.
# Les démarrages suivants réutilisent les fichiers du Render Persistent Disk.

set -e

DATA_DIR="/data"
PBF="$DATA_DIR/ivory-coast-latest.osm.pbf"
OSRM="$DATA_DIR/ivory-coast-latest.osrm"
OSM_URL="https://download.geofabrik.de/africa/ivory-coast-latest.osm.pbf"

mkdir -p "$DATA_DIR"

if [ ! -f "$OSRM" ]; then
    echo "=== Premier démarrage — téléchargement + indexation OSRM ==="
    echo "Source : $OSM_URL"
    echo "Cela peut prendre 10 à 20 minutes selon la connexion Render."

    # Téléchargement de l'extrait OSM
    echo "[1/4] Téléchargement de l'extrait Côte d'Ivoire..."
    curl -L --progress-bar -o "$PBF" "$OSM_URL"

    # Extraction (profil voiture)
    echo "[2/4] Extraction OSRM (profil car)..."
    osrm-extract -p /opt/car.lua "$PBF"

    # Partition
    echo "[3/4] Partition MLD..."
    osrm-partition "$OSRM"

    # Customisation
    echo "[4/4] Customisation MLD..."
    osrm-customize "$OSRM"

    # Nettoyage du .pbf pour libérer de l'espace disque
    rm -f "$PBF"
    echo "=== Indexation terminée — démarrage du serveur OSRM ==="
else
    echo "=== Fichiers OSRM trouvés — démarrage direct (pas de téléchargement) ==="
fi

exec osrm-routed \
    --algorithm mld \
    --max-table-size 10000 \
    --port 5000 \
    --ip 0.0.0.0 \
    "$OSRM"
