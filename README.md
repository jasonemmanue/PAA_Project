# PAA-Traverse

Application web interactive de suivi et de visualisation en temps réel des
temps de traversée des axes routiers stratégiques du Port Autonome d'Abidjan.

> **Contexte permanent du projet :** [CLAUDE.md](CLAUDE.md).

---

## Stack

| Couche       | Technologies                                                                 |
|--------------|------------------------------------------------------------------------------|
| Backend      | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, APScheduler, httpx, redis-py    |
| Base/Cache   | PostgreSQL 16, Redis 7                                                       |
| Routage      | OSRM auto-hébergé (extrait OpenStreetMap de la Côte d'Ivoire, profil voiture)|
| Frontend     | Next.js (App Router) + React + TypeScript, Leaflet, Recharts                 |
| Orchestration| Docker Compose (5 services)                                                  |

---

## Démarrage rapide

### 1. Pré-requis

- **Docker Desktop** (ou Docker Engine ≥ 24 + Docker Compose plugin)
- ~2 Go d'espace libre pour les données OSRM

### 2. Préparer les fichiers d'environnement

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Compléter ensuite `backend/.env` avec :
- un `POSTGRES_PASSWORD` solide (et le reporter dans `DATABASE_URL`),
- une `API_SECRET_KEY` aléatoire (≥ 32 caractères),
- vos clés `GOOGLE_ROUTES_API_KEY` et `TOMTOM_API_KEY`
  (peuvent rester vides en P1 — la collecte arrive en P2).

### 3. Préparer l'extrait OSRM (à faire UNE fois)

L'étape télécharge l'extrait OSM de la Côte d'Ivoire (~80 Mo) depuis
[Geofabrik](https://download.geofabrik.de/africa/ivory-coast.html), puis
exécute la chaîne `osrm-extract` → `osrm-partition` → `osrm-customize` via
l'image officielle `osrm/osrm-backend`.

**Linux / macOS :**

```bash
chmod +x osrm-data/prepare.sh
./osrm-data/prepare.sh
```

**Windows (PowerShell) :**

```powershell
./osrm-data/prepare.ps1
```

À la fin, le dossier `osrm-data/` contient les fichiers `ivory-coast-latest.osrm.*`
nécessaires au service `osrm`.

### 4. Lancer la stack complète

```bash
docker compose up --build
```

Les 5 services démarrent dans l'ordre (db et redis attendus en healthy, puis
osrm, puis backend, puis frontend). Tout tourne en fuseau **`Africa/Abidjan`**.

| Service   | URL locale                  | Description                                   |
|-----------|-----------------------------|-----------------------------------------------|
| db        | `localhost:5432`            | PostgreSQL 16                                 |
| redis     | `localhost:6379`            | Cache Redis                                   |
| osrm      | `http://localhost:5000`     | Moteur de routage interne                     |
| backend   | `http://localhost:8000`     | API FastAPI (Swagger sur `/docs`)             |
| frontend  | `http://localhost:3000`     | Application Next.js (squelette en P1)         |

---

## Vérifier que chaque service est en ligne

```bash
# Backend : doit répondre {"status":"ok"}
curl http://localhost:8000/health

# Swagger interactif
# → ouvrir http://localhost:8000/docs dans un navigateur

# OSRM : route entre CARENA (Plateau) et Pharmacie Palm Beach
# (exemple — coordonnées à ajuster en P1 lors du seed des tronçons)
curl "http://localhost:5000/route/v1/driving/-4.0157,5.3193;-3.9789,5.2741?overview=false"

# PostgreSQL : sonde docker
docker compose exec db pg_isready -U "$POSTGRES_USER"

# Redis : sonde docker
docker compose exec redis redis-cli ping   # → PONG

# Frontend : page d'accueil
# → ouvrir http://localhost:3000 dans un navigateur
```

État des conteneurs et logs :

```bash
docker compose ps
docker compose logs -f backend
```

Arrêt :

```bash
docker compose down            # arrête les conteneurs
docker compose down -v         # supprime aussi les volumes (DB, node_modules)
```

---

## Arborescence

```
paa-traverse/
├── CLAUDE.md                ← contexte permanent du projet
├── README.md                ← ce fichier
├── docker-compose.yml       ← orchestration des 5 services
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py          ← FastAPI + route /health
│       └── core/
│           ├── __init__.py
│           └── config.py    ← chargement via pydantic-settings
├── frontend/
│   ├── .env.example
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   └── app/
│       ├── layout.tsx
│       └── page.tsx
└── osrm-data/
    ├── prepare.sh           ← prép. OSRM (bash)
    └── prepare.ps1          ← prép. OSRM (PowerShell / Windows)
```

---

## Feuille de route

Sept phases — détails dans [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases).
Phase courante : **P1 — Fondations** (cette livraison).
