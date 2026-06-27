# Dockerfile OSRM — Côte d'Ivoire
# Déployé sur Render en tant que Web Service (Docker).
# Au premier démarrage, télécharge et indexe l'extrait OSM Côte d'Ivoire
# dans /data (Render Persistent Disk). Les démarrages suivants réutilisent
# les fichiers déjà indexés — aucun téléchargement supplémentaire.

FROM osrm/osrm-backend:latest

# curl pour le téléchargement
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /data

# Script de démarrage intelligent :
# - Si les fichiers indexés existent → démarre directement OSRM
# - Sinon → télécharge l'extrait OSM et indexe en 3 étapes (10-15 min)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
