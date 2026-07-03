# ============================================================
# Backend FLUIDIS — FastAPI sur Python 3.11
# ============================================================
FROM python:3.11-slim

# Variables d'environnement Python sûres pour les conteneurs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Africa/Abidjan

# Dépendances système minimales + fuseau horaire d'Abidjan
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        curl \
        build-essential \
        libpq-dev \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python en premier (meilleur cache Docker)
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copie du code applicatif
COPY . .

# Port d'écoute par défaut. En local (docker-compose) on garde 8000.
# Sur Railway, la variable $PORT est injectée dynamiquement et écrase la valeur.
ENV PORT=8000
EXPOSE 8000

# Commande de démarrage — utilisée hors docker-compose (Railway, K8s, etc.).
# La forme `sh -c` permet l'interpolation de $PORT au runtime.
# docker-compose surcharge cette CMD (mode --reload pour dev).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=*"]
