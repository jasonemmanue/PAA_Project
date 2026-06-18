# PAA-Traverse — Contexte permanent du projet

> Ce fichier est le **contrat de contexte** du projet. Tout assistant IA, contributeur ou
> reviewer doit le lire avant d'écrire la moindre ligne de code. Il définit le besoin,
> les contraintes techniques, les conventions et la feuille de route.

---

## 1. Contexte et besoin métier

**Client :** Port Autonome d'Abidjan (PAA).
**Contexte :** Hackathon — prototype d'une application web interactive de **suivi et de
visualisation en temps réel des temps de traversée** des axes routiers stratégiques de la
zone portuaire d'Abidjan.

L'application doit fournir :
- une **cartographie dynamique** des tronçons surveillés,
- un **zoom intelligent** sur les points de congestion,
- une **analyse en temps réel et historique** des congestions,
- des **recommandations opérationnelles** à destination des gestionnaires du port.

### 1.1 Axes surveillés

Trois axes officiels, mesurés en **aller ET retour** (soit **6 tronçons dirigés**) :

| # | Axe                                                                         | Distance | Temps de référence (à 50 km/h) |
|---|-----------------------------------------------------------------------------|----------|--------------------------------|
| 1 | CARENA (Plateau) ↔ Pharmacie Palm Beach                                     | 14,9 km  | ≈ 17 min 53 s                  |
| 2 | Toyota CFAO (Treichville) ↔ Pharmacie Palm Beach                            | 8,0 km   | ≈ 9 min 36 s                   |
| 3 | Agence SODECI (Zone 4) ↔ Pharmacie Palm Beach                               | 8,3 km   | ≈ 9 min 58 s                   |

Chaque axe est représenté par **deux tronçons dirigés** (sens A→B et sens B→A) qui
peuvent avoir des temps de parcours très différents selon l'heure et le sens du flux.

### 1.2 Résultats attendus (article 4 du cahier des charges)

1. Base de données fiable des **temps de traversée en temps réel**.
2. Analyse du **niveau de congestion** par tronçon et par créneau horaire.
3. **Identification des zones de congestion** récurrentes.
4. **Évolution de l'indicateur de performance** « temps de traversée ».
5. **Cartographie des congestions** (échelle de couleurs, heatmap).
6. **Recommandations opérationnelles** (créneaux conseillés, itinéraires alternatifs).

### 1.3 Exigences spécifiques

- **Confrontation hebdomadaire** des mesures API avec un **relevé terrain** (trace GPX).
- **Ajout de nouveaux parcours** possible après déploiement (sans redéploiement).
- **Estimation du temps optimal** d'acheminement d'une marchandise jusqu'au port.
- **Comparaison systématique** à un temps de référence calculé à 50 km/h.

---

## 2. Pile technique imposée

### 2.1 Backend

- **Python 3.11+**
- **FastAPI** — documentation Swagger automatique exposée sur `/docs`
- **SQLAlchemy** + **Alembic** (migrations)
- **APScheduler** — collecte planifiée des mesures
- **httpx** — appels aux APIs externes
- **PostgreSQL** — base de données principale
- **Redis** — cache et files d'attente légères
- **pydantic-settings** — chargement de la configuration depuis l'environnement

### 2.2 Moteur de routage interne

- **OSRM auto-hébergé** avec l'extrait **OpenStreetMap de la Côte d'Ivoire**
  (`ivory-coast-latest.osm.pbf`).
- Utilisé pour calculer la **polyline de référence** d'un tronçon et fournir un repli
  de routage en cas d'indisponibilité des sources externes.

### 2.3 Frontend

- **Next.js (App Router)** + **React** + **TypeScript**
- **100 % responsive** — PC, tablette, mobile : toutes les tailles d'interface, les
  boutons et les composants s'adaptent automatiquement.
- **Bilingue français / anglais sans rechargement** (i18n côté client).
- **Thème clair / sombre** sélectionnable par l'utilisateur.
- **Cartographie : Leaflet + OpenStreetMap** (tuiles OSM standard).
- **Graphiques : Recharts**.

### 2.4 Orchestration

- **Docker Compose** avec les services suivants :
  - `db` — PostgreSQL
  - `redis` — cache
  - `osrm` — moteur de routage OSRM
  - `backend` — API FastAPI
  - `frontend` — application Next.js

### 2.5 Sources de mesure — état confirmé

| Source                  | Rôle                                       | Couverture Abidjan |
|-------------------------|--------------------------------------------|--------------------|
| **Google Routes API**   | Source temps réel principale (TRAFFIC_AWARE_OPTIMAL) | ✅ couvert         |
| **OSRM** (auto-hébergé) | Polyline de référence, distance, durée fluide | ✅ couvert (Côte d'Ivoire complète) |
| **Prédicteur interne**  | Profils horaires historiques (P6)          | ✅ alimenté par la collecte |
| **TomTom Traffic Flow** | ~~Source de recoupement~~                  | ❌ **retiré du projet** |

#### Verdict TomTom (testé le 2026-06-18, retiré du projet)

Tests via `/diag/tomtom/{id}` sur les 6 tronçons dirigés (18 points échantillonnés,
équirépartis à 25 % / 50 % / 75 % du tracé) :
- 18/18 réponses HTTP 400 « *INVALID_REQUEST : Point too far from nearest existing segment* »
- 0/18 points couverts par un segment cartographié TomTom
- Confiance moyenne : **0,0** sur les 6 tronçons

**Conséquence appliquée :** le client `app/sources/tomtom.py`, l'endpoint
`/diag/tomtom/{id}` et la variable `TOMTOM_API_KEY` ont été **supprimés** du projet.
La cascade de dégradation gracieuse passe de 4 à 3 niveaux. Réévaluation possible
plus tard si TomTom étend sa cartographie en Côte d'Ivoire.

#### Cascade de dégradation gracieuse (3 niveaux)

1. **Google Routes API** avec `routingPreference=TRAFFIC_AWARE_OPTIMAL` (temps réel).
2. **Prédicteur interne** — estimation à partir des profils horaires historiques (P6).
3. **Temps de référence 50 km/h** via OSRM — repli déterministe ultime.

En cas d'échec total des trois, **on enregistre un trou de mesure** : aucune valeur
n'est inventée ni interpolée.

---

## 3. Modèle de données

Quatre tables principales gérées via SQLAlchemy + Alembic.

### 3.1 `troncons`

Un tronçon = un sens de circulation sur un axe. Chaque axe officiel produit donc deux lignes.

| Colonne          | Type          | Description                                                     |
|------------------|---------------|-----------------------------------------------------------------|
| `id`             | int (PK)      | Identifiant interne                                             |
| `nom`            | str           | Libellé humain (ex. « CARENA → Palm Beach »)                    |
| `lat_origine`    | float         | Latitude du point de départ                                     |
| `lon_origine`    | float         | Longitude du point de départ                                    |
| `lat_destination`| float         | Latitude du point d'arrivée                                     |
| `lon_destination`| float         | Longitude du point d'arrivée                                    |
| `polyline`       | text          | Polyline encodée du tracé (référence OSRM)                      |
| `distance_m`     | int           | Distance officielle en mètres                                   |
| `vitesse_ref_kmh`| float         | Vitesse de référence (50 km/h par défaut)                       |
| `couleur`        | str           | Couleur d'affichage sur la carte                                |
| `actif`          | bool          | **Suppression logique uniquement** (jamais physique)            |

### 3.2 `mesures`

Une mesure = un échantillon de temps de parcours horodaté provenant d'une source.

| Colonne              | Type          | Description                                                     |
|----------------------|---------------|-----------------------------------------------------------------|
| `id`                 | int (PK)      | Identifiant interne                                             |
| `troncon_id`         | int (FK)      | Tronçon mesuré                                                  |
| `horodatage`         | datetime      | Date et heure de la mesure (UTC, fuseau Africa/Abidjan affiché) |
| `duree_trafic_s`     | int           | Temps réel observé avec trafic, en secondes                     |
| `duree_sans_trafic_s`| int           | Temps fluide théorique, en secondes                             |
| `source`             | enum          | `google` \| `tomtom` \| `terrain` \| `interne`                  |
| `vitesse_moyenne_kmh`| float         | Vitesse moyenne calculée                                        |

### 3.3 `profils_horaires`

Table **agrégée recalculée chaque nuit** par un job APScheduler.
Sert à alimenter le prédicteur interne et les graphes d'analyse.

| Colonne       | Type          | Description                                                     |
|---------------|---------------|-----------------------------------------------------------------|
| `troncon_id`  | int (FK)      | Tronçon concerné                                                |
| `jour_semaine`| int (0-6)     | 0 = lundi, 6 = dimanche                                         |
| `heure`       | int (0-23)    | Heure de la journée                                             |
| `moyenne`     | float         | Temps moyen (s)                                                 |
| `mediane`     | float         | Temps médian (s)                                                |
| `min`         | float         | Minimum observé (s)                                             |
| `max`         | float         | Maximum observé (s)                                             |
| `p95`         | float         | 95e percentile (s)                                              |
| `nb_mesures`  | int           | Nombre d'échantillons agrégés                                   |

### 3.4 `releves_terrain`

Trace de chaque relevé terrain hebdomadaire utilisé pour valider les sources API.

| Colonne          | Type          | Description                                                     |
|------------------|---------------|-----------------------------------------------------------------|
| `id`             | int (PK)      | Identifiant interne                                             |
| `troncon_id`     | int (FK)      | Tronçon mesuré sur le terrain                                   |
| `date_session`   | date          | Date de la session de relevé                                    |
| `fichier_gpx`    | str           | Chemin / URL du fichier GPX                                     |
| `duree_mesuree_s`| int           | Durée effectivement mesurée sur le terrain                      |
| `ecart_relatif`  | float         | Écart relatif (terrain vs API) — sert au contrôle qualité       |

---

## 4. Feuille de route — 7 phases

| Phase | Intitulé                                                                      |
|-------|--------------------------------------------------------------------------------|
| **P1**| **Fondations** — squelette FastAPI, modèles SQLAlchemy, migrations Alembic, Docker Compose, seed des 6 tronçons. |
| **P2**| **Robot de collecte + base historique** — APScheduler, intégrations Google Routes / TomTom, dégradation gracieuse, écriture des `mesures`. |
| **P3**| **Indicateurs (FHWA)** — calcul des indices de congestion (Travel Time Index, Planning Time Index, Buffer Index) selon la méthodologie FHWA. |
| **P4**| **Tableau de bord cartographique** — frontend Next.js, carte Leaflet, graphiques Recharts, i18n, thème clair/sombre, responsive. |
| **P5**| **Validation terrain hebdomadaire** — import GPX, calcul de l'écart relatif, alerte si dérive des sources API. |
| **P6**| **Prédiction + fonctions différenciantes** — prédicteur interne basé sur les profils horaires, estimation du temps optimal d'acheminement, recommandations. |
| **P7**| **Tests, déploiement, pitch** — tests d'intégration, durcissement, documentation, déploiement, support de présentation. |

---

## 5. Conventions du projet

### 5.1 Code

- **Tous les commentaires de code sont rédigés en français.**
- **Noms de variables explicites** (pas d'abréviations cryptiques). Les noms de variables
  métier suivent le vocabulaire du cahier des charges : `troncon`, `mesure`,
  `duree_trafic_s`, `vitesse_ref_kmh`, etc.
- Les **schémas Pydantic** miroitent les modèles SQLAlchemy mais restent distincts
  (pas de fuite des modèles ORM vers l'API).
- Le **frontend reste typé en TypeScript strict** — pas de `any` implicite.

### 5.2 Sécurité et configuration

- **Aucune clé API en dur** dans le code. Tout passe par des **variables
  d'environnement** chargées via **`pydantic-settings`** côté backend et `process.env`
  côté frontend.
- Les fichiers `.env` sont **interdits dans git** (cf. `.gitignore`). Seuls les
  `*.env.example` sont versionnés.
- `ALLOWED_ORIGINS` côté backend liste explicitement les origines CORS autorisées.

### 5.3 Intégrité des données

- **Aucune valeur de mesure inventée ou interpolée.** En cas d'échec d'une source de
  mesure, on **enregistre un trou de mesure** (mesure absente, signalée comme telle).
- La **suppression d'un tronçon est logique** (`actif = false`), **jamais physique**,
  pour préserver l'intégrité de l'historique des mesures.
- Toutes les durées sont stockées en **secondes (entier)** et les distances en
  **mètres (entier)** pour éviter les pièges d'arrondi.
- Les horodatages sont stockés en **UTC**, affichés dans le fuseau `Africa/Abidjan`.

### 5.4 Documentation

- L'API FastAPI expose automatiquement sa documentation Swagger sur `/docs` et
  ReDoc sur `/redoc`.
- Toute nouvelle route ajoute un `summary`, une `description` et des `response_model`
  Pydantic.

---

## 6. Arborescence du dépôt

```
paa-traverse/
├── CLAUDE.md                  # Ce fichier — contexte permanent
├── .gitignore
├── docker-compose.yml         # Orchestration des 5 services
├── backend/
│   ├── .env.example           # Modèle d'environnement backend (sans secrets)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/                   # Code FastAPI (à créer dans P1)
├── frontend/
│   ├── .env.example           # Modèle d'environnement frontend (sans secrets)
│   ├── package.json
│   └── app/                   # Code Next.js App Router (à créer dans P4)
└── osrm-data/                 # Extrait OSM + index OSRM (volumineux, ignoré par git)
```

---

## 7. Variables d'environnement attendues

Voir `backend/.env.example` et `frontend/.env.example` pour la liste exhaustive et
les commentaires associés. Récapitulatif des plus importantes :

**Backend :**
- `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_URL`
- `OSRM_BASE_URL`
- `GOOGLE_ROUTES_API_KEY`, `TOMTOM_API_KEY`
- `COLLECT_INTERVAL_MINUTES`, `COLLECT_START_HOUR`, `COLLECT_END_HOUR`
- `REFERENCE_SPEED_KMH` (50 par défaut)
- `TZ=Africa/Abidjan`
- `API_SECRET_KEY`, `ALLOWED_ORIGINS`

**Frontend :**
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_DEFAULT_LANG` (`fr` par défaut)

---

## 8. Règles pour les assistants IA

1. **Toujours relire ce CLAUDE.md avant d'agir.**
2. **Ne jamais inventer une mesure ou une donnée terrain.** Si une donnée manque,
   le dire explicitement et proposer une stratégie de collecte.
3. **Respecter la pile technique imposée.** Ne pas substituer une autre librairie
   sans accord explicite du mainteneur.
4. **Commenter en français, nommer les variables en français** pour les concepts métier.
5. **Toute nouvelle source de mesure** doit s'intégrer dans la chaîne de dégradation
   gracieuse documentée en § 2.5.
6. **Toute évolution du modèle de données** passe par une migration Alembic — jamais
   par modification directe de la base.
