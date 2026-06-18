# ============================================================
# Backend PAA-Traverse — FastAPI sur Python 3.11
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

EXPOSE 8000

# La commande effective est définie par docker-compose (mode --reload en dev).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
