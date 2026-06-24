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

- **Next.js 14 (App Router)** + **React 18** + **TypeScript** strict
- **Tailwind CSS 3** avec design system PAA (palette dérivée du bleu marine
  institutionnel, tailles fluides via `clamp()`, 3 breakpoints explicites
  375 / 768 / 1024).
- **100 % responsive** — PC, tablette, mobile : toutes les tailles d'interface,
  les boutons et les composants s'adaptent automatiquement.
- **Bilingue français / anglais sans rechargement** (provider React custom,
  permutation de dictionnaire en mémoire, persistance `localStorage`).
- **Thème clair / sombre** sélectionnable par l'utilisateur (`next-themes`,
  persistance `localStorage`).
- **Cartographie : Leaflet + OpenStreetMap** (tuiles OSM standard) + plugin
  `leaflet.heat` pour la heatmap des congestions.
- **Graphiques : Recharts** (LineChart pour la série temporelle, BarChart pour
  l'évolution pluriannuelle).
- **Écran de démarrage HACKATONIA** (splash screen 4 s avec effet laser printing
  en bleu ciel, à chaque ouverture du site).

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
3. **Temps de référence 50 km/h** calculé depuis `distance_m` du tronçon — repli déterministe.

En cas d'échec total des trois, **on enregistre un trou de mesure** : aucune valeur
n'est inventée ni interpolée.

#### Sources de données historiques (P6.1 — importées en production le 2026-06-19)

| Source | Table | Valeur `source` | Volume |
|--------|-------|-----------------|--------|
| Campagne terrain fév 2025 (`Base_Nettoyee_PAA_Fev2025.xlsx`) | `mesures` | `historique_paa_2025` | **2 016 mesures** (336 × 6 tronçons) |
| Synthèse pluriannuelle fév 2026 (feuille `SYNTHESE COMPAREE`) | `evolution_indicateur` | — | **24 lignes** (6 axes × 2 périodes × 2 type_jour) |

> **Règle d'or :** ne jamais mélanger `source='historique_paa_2025'` et `source='google'`
> dans les calculs de TTI temps réel. Les données 2025 alimentent le prédicteur (P6.2)
> et les comparaisons pluriannuelles — pas l'état instantané de la carte.

---

## 3. Modèle de données

Cinq tables gérées via SQLAlchemy + Alembic (migrations `0001` → `0009`).

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
| `duree_trafic_s`     | int (nullable)| Temps réel observé avec trafic, en secondes (NULL = trou de mesure). Sert aux temps min/moyen/max (Tableaux 3-15 DEESP). |
| `duree_sans_trafic_s`| int (nullable)| Temps fluide théorique, en secondes — **conservé en base, plus exposé publiquement** depuis la refonte 2026-06-22. |
| `source`             | enum          | `google` \| `terrain` \| `interne` \| `historique_paa_2025`     |
| `vitesse_moyenne_kmh`| float         | Vitesse moyenne calculée                                        |
| `aberrante`          | bool          | Marquée par l'IQR nocturne (P2) — conservée mais exclue des stats |
| `pourcentage_rouge`  | float (nullable) | % du tracé en TRAFFIC_JAM Google (migration 0008 — cf. § 4.5.2bis). NULL si Google n'a pas qualifié la couleur. |
| `pourcentage_orange` | float (nullable) | % du tracé en SLOW Google (migration 0008). |
| `pourcentage_vert`   | float (nullable) | % du tracé en NORMAL Google (migration 0008). |
| `est_congestionne`   | bool (nullable) | Verdict DEESP : True si rouge>0 OU orange ≥ 50 %. NULL si pas de couleur. **Critère officiel de congestion depuis 2026-06-22.** |

> `tomtom` reste présent dans la définition Python de l'enum à des fins historiques
> (mais aucune mesure n'est jamais insérée avec cette valeur depuis le retrait TomTom).

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

### 3.4 `evolution_indicateur`

Table alimentée par l'import de la feuille `SYNTHESE COMPAREE` du fichier FEVRIER_2026.xlsx.
Permet de comparer les temps de traversée entre campagnes de mesure.

| Colonne          | Type          | Description                                                     |
|------------------|---------------|-----------------------------------------------------------------|
| `id`             | int (PK)      | Identifiant interne                                             |
| `axe`            | str           | Libellé de l'axe (ex. « CARENA → Pharmacie Palm Beach »)        |
| `sens`           | str           | « Aller » ou « Retour »                                         |
| `periode`        | str           | Code campagne : `oct_2025`, `fev_2026`, etc.                    |
| `type_jour`      | str           | « Jours ouvrables » ou « Week-ends »                            |
| `temps_min_s`    | float         | Temps minimum observé (secondes)                                |
| `temps_moyen_s`  | float         | Temps moyen observé (secondes)                                  |
| `temps_max_s`    | float         | Temps maximum observé (secondes)                                |

Clé unique : `(axe, sens, periode, type_jour)` — import idempotent.

### 3.5 `releves_terrain`

Trace de chaque relevé terrain hebdomadaire utilisé pour valider les sources API.

| Colonne          | Type          | Description                                                     |
|------------------|---------------|-----------------------------------------------------------------|
| `id`             | int (PK)      | Identifiant interne                                             |
| `troncon_id`     | int (FK)      | Tronçon mesuré sur le terrain                                   |
| `date_session`   | date          | Date de la session de relevé                                    |
| `horodatage_passage` | datetime tz | Instant médian du passage (UTC) — sert à apparier finement avec la mesure Google la plus proche (migration 0004) |
| `fichier_gpx`    | str           | Chemin / nom de fichier GPX (logs + repli disque local)         |
| `contenu_gpx`    | bytea         | **Contenu binaire du `.gpx` — source de vérité, survit aux redéploiements Railway** (migration 0005) |
| `duree_mesuree_s`| int           | Durée effectivement mesurée sur le terrain                      |
| `duree_api_s`    | int           | Durée API utilisée comme référence (migration 0004)             |
| `ecart_relatif`  | float         | Écart relatif (terrain vs API) — sert au contrôle qualité       |
| `confiance_matching` | float (0..1) | Confiance OSRM Match — `NULL` si OSRM indisponible (migration 0004) |

---

## 4. Feuille de route — 7 phases

| Phase | Statut | Intitulé                                                                      |
|-------|--------|--------------------------------------------------------------------------------|
| **P1**| ✅ Terminée | **Fondations** — squelette FastAPI, modèles SQLAlchemy, migrations Alembic, Docker Compose, seed des 6 tronçons. |
| **P2**| ✅ Terminée | **Robot de collecte + base historique** — APScheduler (Google Routes, dégradation gracieuse), écriture des `mesures`, agrégation IQR, exports CSV/XLSX. |
| **P3**| ✅ Terminée *(refondu 2026-06-22)* | **Indicateurs DEESP** — depuis le 2026-06-22 (cf. § 4.5.2bis), la qualification fluide / congestionné vient des **couleurs Google Maps** (`speedReadingIntervals`). On garde les temps min / moyen / max pour les Tableaux 3-15 du rapport. Plus de classe « dense » ni de TTI / PTI / BTI publics. |
| **P6.1** | ✅ Terminée | **Import historique Excel** — 2 016 mesures terrain Fév 2025 + 24 lignes comparatif pluriannuel. Endpoints `/import/*`. |
| **Déploiement** | ✅ Terminé (2026-06-19) | **Backend Railway en ligne** — collecte Google active 24h/24, DB et Redis managés. |
| **P4.1** | ✅ Terminée *(refondu 2026-06-22)* | **Carte Accueil enrichie** — zoom intelligent au chargement vers le **point chaud** (worst classe DEESP puis worst % rouge), **4 markers POI** étiquetés `C`/`T`/`S`/`P`, **panneau latéral** avec **barre couleur 3 segments rouge/orange/vert par tronçon**, bandeau KPI à 3 classes DEESP (fluide / congestionné / indéterminé), encart « Point chaud actuel » avec libellé du tronçon et ses pourcentages de couleur Google Maps. Cf. `CarteLeaflet.tsx` + `PanneauTroncons.tsx`. |
| **P4**| ✅ Terminée | **Frontend Next.js complet** — design system PAA, responsive 3 breakpoints (375/768/1024), i18n FR/EN sans rechargement, thème clair/sombre, splash screen HACKATONIA (laser printing 4 s), favicon multi-tailles, page Carte (Leaflet + WebSocket + heatmap + popups), page Indicateurs (Recharts : courbe + heatmap horaire + évolution pluriannuelle + KPI), sélecteur période fonctionnel **24h / 7j / 30j / 90j** (cf. § 4.1), barre de pilotage avec **pastille 3 états + libellé plage active + prochain cycle** reflétant la veille nocturne automatique (cf. § 4.2), exports CSV/XLSX. |
| **P5**| ✅ Terminée | **Validation terrain hebdomadaire** — `POST /terrain/import` (parsing GPX + OSRM Match + découpage automatique aux bornes des 6 tronçons), appariement avec la mesure Google la plus proche (fenêtre 30 min), `GET /terrain/releves` + `GET /terrain/calibration` (moyenne mobile des écarts). Frontend : page Fiabilité avec import GPX, graphique Recharts d'évolution de ε par tronçon, tableau de calibration coloré 3 niveaux. Script `app/generer_gpx_synthetiques.py` (Option A) produit des GPX placeholder à partir d'OSRM pour valider la boucle sans relevé terrain. Cf. § 4.4. |
| **P6.2** | ✅ Terminée *(refondu 2026-06-24)* | **Page « Temps de traversée par période »** — Google Maps en haut (temps actuel + ce mois + cette semaine, jours-ouvrables/week-ends), confrontation terrain GPX en bas. Cf. § 4.7. |
| **P6.3** | ❌ Retiré du périmètre (2026-06-23) | Module « Heure optimale de départ » supprimé : code, endpoints, UI. La logique restante (temps de traversée) couvre le besoin opérationnel sans le calcul d'approche géocodée. |
| **P6.4** | ⏳ À venir | **Administration + sous-tronçons codifiés** (T1A, T1B, T1C…) comme dans le rapport DEESP. Cf. [§ 6.4](PROMPTS_RESTANTS_DEESP.md). |
| **P6.5** | ⏳ Optionnel | **ML Random Forest** avec évaluation honnête vs prédicteur niveau 2. Cf. [§ 6.5](PROMPTS_RESTANTS_DEESP.md). |
| **P7.1**| ⏳ À venir | **Tests + Cache Redis + Optimisations** — pytest pour rapport_paa, cache /carte/etat et /predire, Lighthouse mobile ≥ 80. Cf. [§ 7.1](PROMPTS_RESTANTS_DEESP.md). |
| **P7.2**| ⏳ À venir | **Déploiement Vercel** (frontend) + ALLOWED_ORIGINS Railway + URL publique finale. Cf. [§ 7.2](PROMPTS_RESTANTS_DEESP.md). |
| **P7.3**| ⏳ À venir | **Rapport final article 4** + **trame de pitch 5-7 min** revendiquant l'alignement DEESP. Cf. [§ 7.3](PROMPTS_RESTANTS_DEESP.md). |

### 4.1 Sélecteur de période de la page Indicateurs — contrat frontend/backend

Le backend `GET /troncons/{id}/indicateurs?periode=...` n'accepte **que le format
`Nj`** (`1j`, `7j`, `30j`, `90j`) — son parseur (`_parse_periode`,
`backend/app/api/troncons.py`) rejette tout autre format avec un **HTTP 400**.

L'UI conserve l'étiquette « **24 h** » pour la lisibilité, donc
[`getIndicateursTroncon`](frontend/lib/api.ts) **traduit `"24h" → "1j"`** avant
d'appeler l'API. Les 4 boutons sont donc fonctionnels :

| Bouton UI | Envoyé au backend | Fenêtre |
|-----------|-------------------|---------|
| `24 h`    | `?periode=1j`     | 1 jour glissant |
| `7 jours` | `?periode=7j`     | 7 jours glissants |
| `30 jours`| `?periode=30j`    | 30 jours glissants |
| `90 jours`| `?periode=90j`    | 90 jours glissants |

**Conséquence attendue les premiers jours après mise en production** : tant que
la collecte Google n'a pas accumulé plusieurs jours d'historique, les 4
sélecteurs renvoient le **même contenu** (uniquement les mesures du jour). Les
2 016 mesures historiques `source='historique_paa_2025'` (P6.1) datent de
février 2025 et restent donc hors fenêtre même à 90 jours — elles
n'apparaissent que dans la **heatmap horaire** et le **graphique d'évolution
pluriannuelle** qui exploitent respectivement `profils_horaires` et
`evolution_indicateur`, indépendamment du sélecteur. C'est conforme à la
**règle d'or** du § 2.5 : on ne mélange jamais `historique_paa_2025` avec les
mesures `google` temps réel.

**Compteur « Nb mesures » du KPI** : porte sur **un seul tronçon** (celui
sélectionné dans le dropdown). Pour vérifier la collecte globale, comparer avec
`GET /collecte/status` → `compteurs_jour.nb_mesures_total` qui agrège les
6 tronçons.

### 4.2 Barre de pilotage et veille nocturne automatique

Le scheduler APScheduler n'est **pas** en collecte continue : il utilise un
`CronTrigger` restreint à la plage `COLLECT_START_HOUR → COLLECT_END_HOUR - 1`
(défaut **7h–18h59 Africa/Abidjan**, soit la fenêtre `[7h, 19h[`). Conséquence
factuelle :

- **Dernier cycle** : ≈ `END_HOUR - 1` à `60 - INTERVAL_MINUTES` (ex. 18:40).
- **Aucune requête Google entre 19h00 et 06:59** — pas besoin de stopper
  manuellement la collecte le soir, et inutile de la redémarrer le matin :
  `prochaine_execution` saute automatiquement au lendemain 07:00 dès qu'on
  franchit l'heure de fermeture.
- Le scheduler **reste vivant** toute la nuit : `etat_scheduler()` continue de
  renvoyer `actif=True` car cela reflète l'état du process, pas le statut de
  collecte instantané.
- Un job nocturne indépendant tourne **à 23h00** : recalcul des profils horaires
  (`agregation_profils_horaires`) — pas de requête externe.

**Reflet frontend** ([`BarrePilotage.tsx`](frontend/components/indicateurs/BarrePilotage.tsx)) :

| État réel | Pastille | Libellé | Ligne « Prochain cycle » |
|-----------|----------|---------|---------------------------|
| `actif=true` ET heure ∈ `[start, end[` | **vert + `animate-pulse`** | « Collecte active » | *aujourd'hui HH:MM* |
| `actif=true` ET heure ∉ `[start, end[` | **bleu calme** (`bg-paa-blue-400`, sans pulse) | « Collecte en veille » | *demain 07:00* |
| `actif=false` | gris fixe | « Collecte arrêtée » | — |

La plage horaire est **parsée** depuis `config.plage_horaire` (regex
`/(\d+)h-(\d+)h/`) — donc si l'opérateur change `COLLECT_START_HOUR` /
`COLLECT_END_HOUR` côté Railway, l'UI suit automatiquement au prochain
`/collecte/status` (rafraîchi toutes les 30 s côté client). Un `setInterval`
local de 60 s force un re-render afin que la pastille bascule en bleu **à
l'instant T** de la fermeture, sans attendre le polling de statut suivant.

La conversion en heure Africa/Abidjan est faite côté client via
`Intl.DateTimeFormat({ timeZone: "Africa/Abidjan" })` — pas de nouvel endpoint
backend nécessaire.

### 4.3 P5 — Validation terrain hebdomadaire

**Modèle de données** : la table `releves_terrain` est enrichie par la
migration **0004** (`horodatage_passage`, `duree_api_s`, `confiance_matching`)
pour permettre l'appariement temporel fin avec les mesures Google.

**Pipeline `POST /terrain/import`** :

1. **Parsing GPX** (`app/sources/gpx_parser.py`) — uniquement les points
   `<trkpt>` avec un `<time>` sont conservés (sinon impossible de calculer une
   durée). Le fichier original est persisté sur disque (`GPX_STORAGE_DIR`,
   défaut `./data/gpx`).
2. **Découpage automatique** (`app/terrain/decoupage.py`) — pour chaque
   tronçon des 6 actifs et résolus, recherche du point de la trace le plus
   proche de l'origine puis de la destination (rayon Haversine ≤ **80 m**).
   Si les deux extrémités sont trouvées et que `index_fin > index_debut`,
   un segment est créé avec :
   - `duree_s = horodatage(fin) − horodatage(debut)`
   - `horodatage_passage = milieu temporel`
3. **OSRM Match best-effort** sur la sous-trace pour récupérer une
   `confiance_matching` (0..1). Échec silencieux si OSRM indisponible — le
   reste du calcul fonctionne sans.
4. **Appariement Google** — recherche dans `mesures` (source=`google`,
   `duree_trafic_s NOT NULL`) la ligne dont l'horodatage est le plus proche de
   `horodatage_passage` (fenêtre **30 min**). Si trouvée :
   `ecart_relatif = (T_terrain − T_api) / T_api`. Sinon NULL.

**Calibration** (`GET /terrain/calibration?fenetre=4`) — moyenne des
`ecart_relatif` des N derniers relevés par tronçon. Sert à signaler une
dérive systématique des sources API.

**Script Option A** (`python -m app.generer_gpx_synthetiques --congestion 1.4`) :
Pour chaque tronçon, appelle OSRM `/route`, décode la polyline (Google
precision 5), interpole à ~1 pt/s, écrit un GPX 1.1 standard avec horodatages
plausibles. Permet de valider la boucle d'import sans déplacement terrain.

**Argument `--horodatage-debut`** (ISO 8601 UTC) : permet de **caller** les
GPX synthétiques sur une fenêtre où des mesures Google existent déjà en base.
Sans cet argument, le script utilise « aujourd'hui 08:00 UTC », ce qui produit
souvent un appariement vide quand on teste en dehors des heures de collecte
(par ex. samedi matin avant 7h). Pour la démo, viser un horaire représentatif
d'un jour ouvré : `--horodatage-debut "2026-06-19T14:00:00"` (mi-après-midi
d'un vendredi). Chaque tronçon suivant démarre 10 min après la fin du
précédent → couvre une plage de ~2h30 ⇒ ≈ 7-8 cycles Google de 20 min ⇒
appariement garanti.

⚠️  **Données synthétiques uniquement** — les GPX générés suivent le tracé OSRM
théorique et NE remplacent PAS de vrais relevés terrain. L'alignement définitif
des `releves_terrain` (P5) devra utiliser des traces GPS issues d'un téléphone
parcourant réellement les 6 tronçons (OsmAnd Tracker, Strava, GPX Logger…).

### 4.3.1 État actuel — mode simulation (à remplacer par du terrain réel)

À la date du **2026-06-20**, la démo P5 tourne en **mode simulation** :

| Composant | Localisation | État |
|-----------|--------------|------|
| Backend FastAPI | Railway (`backend-production-6cbf.up.railway.app`) | ✅ Production |
| PostgreSQL | Plugin Railway managé | ✅ Production |
| Redis | Plugin Railway managé | ✅ Production |
| Frontend Next.js | Local (`npm start` sur le PC opérateur) | ⏳ À déployer (Vercel ou Railway) |
| **OSRM** | **Docker local uniquement** | ⏳ Pas hébergé en prod (cf. § 8.3) |
| Relevés terrain GPX | **Générés synthétiquement** via `generer_gpx_synthetiques.py` | ⏳ À remplacer par des relevés smartphone |

**Conséquences mesurables sur la table `releves_terrain` côté Railway :**

- `duree_mesuree_s` : valeur du **générateur synthétique** (`temps_fluide × congestion`),
  pas un temps réel mesuré sur le terrain.
- `ecart_relatif` : calculé contre la vraie mesure Google la plus proche → la
  **comparaison est réelle**, le **terrain est simulé**.
- `confiance_matching` : toujours `NULL` (OSRM non exposé sur Railway).
- `fichier_gpx` : pointe sur un fichier généré par le script, pas un fichier
  remonté du terrain.

**Plan de bascule vers le réel (post-hackathon) :**

1. Exposer OSRM en prod (Option B Oracle Cloud Free Tier de § 8.3) →
   `confiance_matching` renseignée.
2. Déployer le frontend sur Vercel ou Railway → opérateurs accèdent sans
   `npm start` local.
3. Munir un opérateur PAA d'une app GPX (**OsmAnd Tracker** recommandé, libre
   et offline) et organiser une session hebdomadaire de parcours des 6
   tronçons aux heures de pointe.
4. Uploader les vrais `.gpx` via la même page Fiabilité — l'argument
   `--horodatage-debut` n'est plus nécessaire puisque le téléphone enregistre
   les vraies heures.
5. Supprimer ou archiver les `releves_terrain` synthétiques actuels via un
   `DELETE FROM releves_terrain WHERE fichier_gpx LIKE '%gpx_synth%'` (à
   exécuter dans la Console Railway).

**~~Acronymes des indices FHWA~~** *(retirés le 2026-06-22)* — la page
Indicateurs n'expose plus TTI / PTI / BTI. Elle affiche désormais les
indicateurs DEESP officiels du rapport :

| Bloc UI affiché | Source backend |
|---|---|
| **Temps moyen / minimum / maximum** (mm:ss) | `snapshot.{moyenne_s, min_s, max_s}` agrégés sur la fenêtre choisie |
| **Taux de congestion** (%) | `snapshot.taux_congestion` = `nb_mesures congestionnées / nb_qualifiées` (couleur Google Maps) |
| **% rouge moyen** | `snapshot.pourcentage_rouge_moyen` (TRAFFIC_JAM Google moyenné sur la fenêtre) |
| **% orange moyen** | `snapshot.pourcentage_orange_moyen` (SLOW Google moyenné sur la fenêtre) |

Les anciennes clés i18n `indicateurs.tti/pti/bti` ont été supprimées des
fichiers `frontend/messages/{fr,en}.json` et les `tti_seuil_*` du backend
ont été marqués legacy dans `app/core/config.py` (encore lus pour
compatibilité Railway, jamais consommés par le code d'analyse).

**Frontend** — `app/fiabilite/page.tsx` orchestre 5 blocs :
- 3 KPI compacts (dernière session, écart moyen global, tronçons validés)
- `<ImportGpx>` : **input multi-fichiers** (`<input type="file" multiple>`) +
  boucle séquentielle d'appels `POST /terrain/import` avec barre de progression
  et **tableau consolidé** mentionnant le fichier d'origine de chaque relevé.
  Les erreurs par fichier sont remontées séparément sans bloquer les suivants.
- `<CarteApercu>` : **carte Leaflet de prévisualisation** affichant les 6
  tronçons officiels (lignes pointillées colorées) en superposition avec la
  ou les traces GPX uploadées (couleur dorée). Marqueurs verts/rouges aux
  bornes des tronçons détectés. Les traces sont parsées **côté client** via
  `lib/gpxClient.ts` (DOMParser, pas de dépendance externe) dès la sélection
  du fichier, donc affichage instantané avant même l'upload. À noter : la
  trace affichée est la **trace brute** (la "trace recalée" OSRM Match n'est
  pas renvoyée par le backend ; OSRM n'étant pas exposé sur Railway, le
  matching n'a de toute façon pas lieu en prod). **Persistance côté Railway**
  via deux endpoints dédiés : la page Fiabilité, à chaque montage, identifie
  la dernière session terrain dans le payload `GET /terrain/releves`, télécharge
  les `.gpx` bruts via `GET /terrain/releves/{id}/gpx` (1 appel par fichier
  unique), parse côté client et repeuple traces + marqueurs. **Aucun
  localStorage**.

  **Stockage** : depuis la migration **0005**, le contenu binaire du GPX est
  stocké dans la colonne `releves_terrain.contenu_gpx` (`BYTEA`). C'est la
  **source de vérité** — survit à tous les redéploiements Railway (le disque
  Railway est éphémère par défaut). Le disque local sert de repli en
  développement, et pour les relevés pré-0005 qui n'ont que `fichier_gpx`
  sans contenu (returnent un **HTTP 410 Gone** clair côté API si plus de
  fichier sur disque). Le parseur
  GPX utilise `getElementsByTagNameNS("*", "trkpt")` pour rester
  **agnostique au namespace** (le GPX produit par notre script Python
  déclare `xmlns="http://www.topografix.com/GPX/1/1"`, et l'appel sans
  namespace ne matcherait alors aucun élément). Les coords des tronçons
  sont lues à la fois au top-level et sous `geometrie.{lat,lon}_*` du
  payload `/carte/etat` (les marqueurs début/fin n'apparaissaient pas avant
  cette double-lecture car le backend les expose uniquement sous
  `geometrie` — bug historique de l'interface).
- `<EvolutionEcart>` : Recharts LineChart, 1 ligne par tronçon, axe Y en %.
  Tant qu'il n'y a qu'**une seule session** importée, Recharts n'affiche que
  des **dots** (pas de trait) — c'est attendu, un trait nécessite ≥ 2 points
  par série. Les vraies courbes apparaissent dès la 2e session terrain.
- `<CalibrationTable>` : moyenne mobile + code couleur 3 états
  (vert ≤ 10 % / orange ≤ 25 % / rouge > 25 %)

### 4.3.2 État final P5 — ce qui marche bout-en-bout

À la date du **2026-06-21**, P5 est livrée et opérationnelle :

| Composant | État | Détail |
|-----------|------|--------|
| Endpoint `POST /terrain/import` | ✅ | Parse GPX, découpe auto, calcule ε, stocke en DB (contenu BYTEA + disque) |
| Endpoint `GET /terrain/releves` | ✅ | Historique enrichi de `nom_fichier_gpx` |
| Endpoint `GET /terrain/releves/{id}/gpx` | ✅ | Sert le binaire BYTEA en priorité, repli disque, 410 Gone si perdu |
| Endpoint `GET /terrain/calibration` | ✅ | Moyenne mobile par tronçon, fenêtre paramétrable |
| Script `generer_gpx_synthetiques` | ✅ | Avec arg `--horodatage-debut` pour caller sur la fenêtre de collecte |
| Migration 0004 (timestamp + ε API + confiance) | ✅ | Appliquée sur Railway |
| Migration 0005 (BYTEA contenu_gpx) | ✅ | Appliquée sur Railway, résout le bug du disque éphémère |
| Frontend page Fiabilité | ✅ | 5 blocs : 3 KPI + Import + Carte aperçu + LineChart + Calibration |
| Hydratation Railway au montage | ✅ | Charge automatiquement la dernière session → traces + markers visibles dès l'ouverture |
| Markers début/fin dédupés par libellé | ✅ | 4 POIs avec badges numériques, tooltip détaillé, zIndexOffset prioritaire |
| Persistance des traces après F5 | ✅ | Aucun localStorage, source de vérité = DB Railway |
| 6 couleurs distinctes par trace | ✅ | PALETTE_TRACES (ambre, rose, violet, turquoise, indigo, orange) |

**Ce qui reste à venir** (hors scope P5) :

- ❌ **OSRM exposé en prod** → polylines réelles routières + `confiance_matching` non NULL (cf. § 8.7)
- ❌ **Vrais GPX terrain** → remplacer les synthétiques actuels (workflow opérationnel documenté en § 4.3.1)
- ⏳ Cumul **≥ 4 sessions hebdomadaires** pour que la moyenne mobile de calibration ait du sens statistiquement

### 4.4bis Carnet d'exécution restant

Les prompts pour exécuter les phases P6.2 → P7.3 sont consolidés dans
[`PROMPTS_RESTANTS_DEESP.md`](PROMPTS_RESTANTS_DEESP.md) à la racine du
dépôt. Chaque prompt est récrit pour respecter la méthodologie DEESP
(§ 4.5) — distinction jour-ouvrable/week-end, durées en minutes, critère
ratio 1,5, règles d'occurrence 3/4, sous-tronçons codifiés.

À exécuter dans l'ordre : 6.2 → 6.3 → 6.4 → (6.5 opt.) → 7.1 → 7.2 → 7.3.

### 4.5 Méthodologie d'analyse — alignement DEESP/DEEF (rapport oct. 2025)

> Référence : *« Evaluation du temps de traversée — rapport provisoire octobre 2025 »*
> rédigé par la **DEESP/DEEF** du Port Autonome d'Abidjan.

Le rapport établit la méthodologie officielle d'évaluation du temps de
traversée. À l'origine, notre back-end implémentait des indicateurs FHWA
(TTI/PTI/BTI) en monitoring continu. **Depuis le 2026-06-22, FHWA a été
retiré au profit du critère couleur officiel DEESP** (cf. § 4.5.2bis) :
on lit directement `speedReadingIntervals` de Google Routes pour
qualifier fluide/congestionné, et on conserve uniquement les temps min /
moyen / max comme indicateurs publiés (Tableaux 3-15 du rapport).

#### 4.5.1 Cadre temporel et collecte

| Élément | Spécification PAA | Implémentation alignée |
|--------|-------------------|------------------------|
| **Source primaire** | Application Google Maps (couleurs) + parcours terrain réels | API Google Routes (durée chiffrée) + GPX terrain (P5) |
| **Périodicité campagne** | 2 fois/an : forte activité + creuse | Continu (octobre + février exposés comme campagnes) |
| **Fréquence collecte** | **1 mesure / heure** (à chaque heure pleine) | `COLLECT_INTERVAL_MINUTES=60` (passé de 20 à 60) |
| **Plage horaire** | 7h à 19h | `COLLECT_START_HOUR=0`, `COLLECT_END_HOUR=24` — **collecte étendue à 24h/24** (cf. note ci-dessous) |
| **Durée campagne** | 1 mois complet (4 lundis, 4 mardis, 5 mercredis, 5 jeudis, 5 vendredis, 4 samedis, 4 dimanches) | Fenêtre glissante 28 jours pour aligner les rapports |
| **Plafond Google** | — | 24 cycles × 6 tronçons = **144 req/jour** (très en-dessous des 250) |

**Note sur l'extension 24h/24 (décidée le 2026-06-21)** :

Le rapport DEESP couvre **strictement 7h à 19h**. Notre back-end étend
volontairement la collecte à **24h/24** pour les raisons suivantes :

1. **Coût négligeable** — à 1 mesure/heure × 6 tronçons, l'extension de
   12h à 24h fait passer de 78 à 144 req/jour, toujours largement sous le
   quota Google de 250.
2. **Couverture analytique enrichie** — capture la nuit (22h-06h), qui
   sera *probablement* fluide et confirmera quantitativement les
   observations du rapport DEESP sur la fluidité hors plage portuaire.
3. **Détection d'événements exceptionnels** — convoi nocturne, route
   barrée, incident accidentel peuvent survenir hors 7h-19h.
4. **Conformité préservée** — le rapport DEESP officiel reste calculé sur
   les mesures 7h-19h via le filtre côté `app/analyse/rapport_paa.py` (les
   mesures 0h-7h et 19h-24h ne polluent pas les Tableaux 3-15 ni le
   Tableau 16).
5. **Plus de veille nocturne** — la barre de pilotage du frontend affiche
   désormais une pastille verte permanente (pas de bascule « en veille »
   à 19h00 comme c'était le cas avant).

#### 4.5.2 Critère de congestion (méthode DEESP)

Un **tronçon est congestionné** sur une heure donnée selon la couleur Google Maps :

- ✅ **Rouge** → congestionné
- ✅ **Orange sur ≥ 50% du tronçon** → congestionné
- ❌ Orange sur courte distance → fluide (juste feux ou manœuvres)

#### 4.5.2bis Critère couleur DEESP — implémentation depuis 2026-06-22

> **Refonte importante** : avant le 2026-06-22, le back-end approximait le
> critère couleur par un ratio `duree_trafic_s / T_ref_50kmh ≥ 1.5`. Cette
> approximation n'était PAS le critère officiel du rapport et donnait des
> résultats incohérents quand le ralentissement venait des feux tricolores
> (le ratio passait au-dessus de 1.5 sans qu'il y ait embouteillage réel).
>
> Depuis le 2026-06-22, **on lit directement les couleurs Google Maps** via
> le champ `routes.travelAdvisory.speedReadingIntervals` de l'API Google
> Routes. Ce champ contient pour chaque segment de la polyline un enum
> `Speed` (NORMAL / SLOW / TRAFFIC_JAM) qui correspond exactement aux
> couleurs vert / orange / rouge utilisées par le rapport.

**Chaîne de qualification** :

1. **`app/sources/google_routes.py`** — récupère les `speedReadingIntervals`
   à chaque cycle de collecte. Le `FieldMask` est étendu :
   ```python
   "X-Goog-FieldMask": (
       "routes.duration,routes.staticDuration,"
       "routes.distanceMeters,routes.polyline.encodedPolyline,"
       "routes.travelAdvisory.speedReadingIntervals"
   )
   # + body: "extraComputations": ["TRAFFIC_ON_POLYLINE"]
   ```
2. **`calculer_pourcentages_couleur()`** — décode la polyline, calcule pour
   chaque intervalle la distance Haversine entre `startPolylinePointIndex`
   et `endPolylinePointIndex`, somme par couleur, divise par la distance
   totale → 3 pourcentages (rouge / orange / vert).
3. **`evaluer_congestion_deesp(pct_rouge, pct_orange)`** — applique la règle
   du rapport :
   - rouge > 0 → `est_congestionne = True`
   - orange ≥ 50 % → `est_congestionne = True`
   - sinon → `est_congestionne = False`
   - pct couleur tous None → `est_congestionne = None` (indéterminé, **pas inventé**)

**Persistance — migration 0008** : la table `mesures` reçoit 4 nouvelles
colonnes nullable :

| Colonne | Type | Sens |
|---------|------|------|
| `pourcentage_rouge` | float | % du tracé en TRAFFIC_JAM |
| `pourcentage_orange` | float | % du tracé en SLOW |
| `pourcentage_vert` | float | % du tracé en NORMAL |
| `est_congestionne` | bool | verdict DEESP appliqué (NULL si pas de couleur) |

Index `ix_mesures_est_congestionne (troncon_id, est_congestionne, horodatage)`
pour accélérer le Tableau 16 du rapport (« heures × jours congestionnés »).

**Module central** : `backend/app/analyse/congestion.py` expose
`classer_congestion(pct_rouge, pct_orange, pct_vert)` retournant un
`VerdictCongestion` avec la **classe** (`fluide` / `congestionne` /
`indetermine` — **plus de `dense`**), les 3 pourcentages, et un **motif
humain** rendu dans les popups Leaflet.

**Conséquences sur les indicateurs publiés** :

- `/troncons/{id}/indicateurs` : `snapshot` contient désormais `min_s /
  moyenne_s / max_s`, `taux_congestion`, `pourcentage_rouge_moyen`,
  `pourcentage_orange_moyen`, `classe_congestion`. **Plus de TTI / PTI /
  BTI** dans la réponse publique — les seuils `TTI_SEUIL_*` du `.env`
  sont conservés en config mais marqués legacy (cf. `app/core/config.py`).
- `/carte/etat` : chaque tronçon renvoie `classe_congestion`,
  `libelle_classe`, `motif_congestion`, `couleur_google.{pourcentage_*}`.
  Le bloc `seuils.tti_*` a disparu et `couleurs` ne contient plus que
  3 entrées (`fluide`, `congestionne`, `indetermine`).
- `/rapport/zones-congestionnees` : la requête SQL filtre directement sur
  `Mesure.est_congestionne.is_(True)` (au lieu de comparer `duree_trafic_s`
  à `1.5 × T_ref`). Les règles ≥ 3 / jour et ≥ 4 / semaine restent
  inchangées.

**Pourquoi on conserve `duree_trafic_s`** : pour les **temps min / moyen /
max** des Tableaux 3-15 du rapport (cf. § 4.5.4). Le rapport publie 5
indicateurs **temps** en minutes — ces calculs ont toujours besoin de la
durée. C'est uniquement le **verdict fluide/congestionné** qui passe sur
les couleurs. La colonne `duree_sans_trafic_s` reste en base mais n'est
plus exposée par l'API publique (elle servait au TTI ; le rapport DEESP
utilise T_ref(50 km/h), pas le freeflow Google).

**Cas indéterminé** — quand Google ne renvoie pas
`speedReadingIntervals` (zone non couverte par les données trafic), les
4 colonnes restent NULL et le tronçon s'affiche **gris** sur la carte
avec le libellé `Indéterminé`. On ne tranche jamais en l'absence de
donnée — conformément à la règle d'or du § 5.3.

**Procédure de bascule (déjà exécutée)** :

```bash
# 1. Local — commit & deploy
git add backend/ frontend/
git commit -m "Refonte critere congestion : couleurs Google Maps DEESP"
railway up --service backend

# 2. Console Railway — migration + vidage des données legacy
alembic upgrade head

python -c "
from app.db.session import SessionLocal
from app.models.models import Mesure
from sqlalchemy import delete
db = SessionLocal()
n = db.execute(
    delete(Mesure).where(Mesure.pourcentage_rouge.is_(None))
).rowcount
db.commit()
print(f'{n} mesures legacy supprimees')
"
```

Le vidage évite que les **anciennes** mesures (qui ont les 4 colonnes
couleur à NULL) polluent le taux de congestion des 7/30/90 prochains
jours. Les nouvelles mesures collectées après le déploiement se
remplissent automatiquement.

#### 4.5.3 Règles de qualification (extrait rapport § 2)

**Hypothèse mensuelle** : 4 lundis, 4 mardis, 5 mercredis, 5 jeudis, 5
vendredis, 4 samedis, 4 dimanches sur le mois étudié.

**Tri rapporté au jour-type** :
> *« Pour une tranche horaire, un tronçon est considéré comme congestionné
> lorsqu'il apparaît au moins 3 fois le jour indicatif (exemple : 3 fois sur
> les 4 lundis). »*

**Tri rapporté à la semaine** :
> *« Lorsque le tronçon retenu ressort au moins 4 fois à la même tranche
> horaire au cours de la semaine (peu importe le jour), il est considéré
> comme congestionné. »*

Cf. fonction `troncons_congestionnes()` de `app/analyse/rapport_paa.py`.

#### 4.5.4 Indicateurs publiés (5 indicateurs DEESP)

Le rapport ne publie **PAS** TTI/PTI/BTI mais 5 indicateurs simples en
**minutes** :

1. **Temps théorique 50 km/h** (Tableau 1) : `distance_km / 50 × 60` mn
2. **Temps minimal** (Tableaux 3-7) : `min(duree_trafic)` sur la campagne, par axe × sens × type-jour
3. **Temps moyen** (Tableaux 8-11) : `Σ moyennes_journalières / nb_jours`
4. **Temps maximal** (Tableaux 12-15) : `max(duree_trafic)` sur la campagne
5. **Liste des tronçons congestionnés** (Tableau 16) selon les règles § 4.5.3

Et un **6e indicateur dérivé** :
6. **Comparaison pluriannuelle** (Tableau 19) : delta entre 2 campagnes
   (oct. 2025 vs fév. 2025 dans le rapport).

#### 4.5.5 Distinction jours ouvrables / week-ends

Le rapport agrège systématiquement par **type de jour** (col. JOURS
OUVRABLES vs WEEK-ENDS), pas par jour de la semaine individuel.
Côté implémentation :

```python
TYPE_JOUR = "jour_ouvrable" if weekday < 5 else "week_end"
```

Tous les tableaux 3-15 ont donc 2 colonnes côte à côte.

#### 4.5.6 Format des graphiques attendus

Le rapport mentionne **12 graphiques** (Graphique 1 à Graphique 12),
**tous des BarCharts** :

- Graphiques 1, 3, 5 → Temps minimal observé dans le sens **aller** (1 par axe)
- Graphiques 2, 4, 6 → Temps minimal observé dans le sens **retour**
- Graphiques 7, 9, 11 → Temps maximal observé dans le sens **aller**
- Graphiques 8, 10, 12 → Temps maximal observé dans le sens **retour**

Format : axe X = jour de l'observation, axe Y = temps en minutes,
1 barre par observation. Pas de courbes Recharts type LineChart pour
ces graphiques — exclusivement `BarChart` avec axe Y en minutes entières.

**Implication pour notre frontend** : la page Indicateurs garde ses graphes
FHWA (cohérent monitoring temps réel), mais une **nouvelle page « Rapport
DEESP »** reproduit fidèlement les 17 tableaux et 12 graphiques attendus.

#### 4.5.7 Recommandations opérationnelles (extrait conclusion)

Le rapport conclut sur 5 recommandations :

1. Mise en place d'un **système de programmation et d'appel des camions**
2. **Relocalisation** des cités résidentielles du port
3. **Délocalisation** de la SICTA (visite et immatriculation)
4. Réparation des **défauts d'asphaltage** post-projet
5. **Système d'alerte temps réel** sur les conditions de circulation
   (radio, applications mobiles)

Le point 5 correspond précisément à notre prototype — il devra être mis
en valeur dans le pitch.

### 4.4 Sous-phases de P6

| Sous-phase | Statut | Intitulé | Endpoints |
|------------|--------|----------|-----------|
| **P6.1** | ✅ Terminée | **Import des données historiques Excel** — `Base_Nettoyee_PAA_Fev2025.xlsx` (2 016 mesures terrain) + `FEVRIER_2026.xlsx` feuille `SYNTHESE COMPAREE` (24 lignes pluriannuelles). | `POST /import/base-nettoyee`, `POST /import/evolution` |
| **P6.2** | ✅ Terminée *(refondu 2026-06-24)* | **Temps de traversée par période** — Google Maps en avant (temps actuel + ce mois + cette semaine), confrontation terrain GPX en bas. Cf. § 4.7. | `GET /predire/resume?troncon_id=` + `GET /terrain/segments/resume/{id}` |
| ~~P6.3~~ | ❌ Retiré (2026-06-23) | ~~Heure optimale d'acheminement~~ — module supprimé : code backend (`app/api/heure_optimale.py`, `app/predicteur/heure_optimale.py`) et UI (`OngletHeureOptimale.tsx`) retirés du dépôt. | — |
| **P6.4** | ✅ Terminée | **Ajout de nouveaux parcours** — interface admin frontend + endpoint backend pour créer un nouveau tronçon sans redéploiement. | `POST /administration/troncons` |

### 4.7 Page « Temps de traversée par période » (P6.2 refondu — 2026-06-24)

Refonte décidée le **2026-06-23**, structure finale fixée le **2026-06-24**.

**Sous-titre :** *« Temps réel basé sur Google Maps — confrontation avec les
temps terrain GPX en bas de page. »*

#### Structure du contenu — trois zones verticales

**Zone 1 — Google Maps (en haut, en avant)**

Données temps réel API Google Routes, mises à jour toutes les heures par le
scheduler. Trois blocs `paa-card` affichés directement (sans dépliable) :

1. **Temps réel (Google Maps)** — Min / Moyen / Max + badge source coloré
   (vert = mesure temps réel, bleu = moyenne 7 j, gris = 50 km/h).
2. **Ce mois — Google Maps** — stats jours-ouvrables / week-ends depuis le
   1er du mois. Nombre de mesures affiché.
3. **Cette semaine — Google Maps** — idem depuis le lundi de la semaine.

**Principe de collecte et de calcul Google (`backend/app/predicteur/profils.py`) :**

Toutes les heures, le scheduler appelle l'API Google Routes pour chaque tronçon
et insère une ligne dans la table `mesures` (source=`google`, `duree_trafic_s`
en secondes, `est_congestionne` calculé depuis les couleurs Maps).

**Temps actuel** — cascade à 3 niveaux :

| Niveau | Source | Condition | Confiance |
|--------|--------|-----------|-----------|
| 1 | Mesure Google ±15 min | Une mesure existe à ±15 min du présent | 1.0 |
| 2 | Mesures Google 7 j même `type_jour` | Toutes les mesures du même type de jour (jo/we) sur 7 j glissants — pas de filtre par heure | 0.5–0.93 |
| 3 | Distance / 50 km/h | Repli déterministe | 0.3 |

**Ce mois / Cette semaine** — calcul backend (`_stats_mesures_periode`) :
- Filtre : `source=google`, `aberrante=False`, fenêtre = [1er du mois ou lundi] → maintenant
- Sépare par `type_jour` : `weekday() < 5` → `jour_ouvrable`, sinon `week_end`
- Calcule `min / fmean / max` des `duree_trafic_s` et convertit en minutes entières

**Zone 2 — Bandeau d'écart Google ↔ Terrain**

Affiché entre les deux sections, uniquement si données Google **et** GPX
disponibles simultanément. Calcul **entièrement côté client** :

```typescript
// Moyenne Google mensuelle pondérée (jours ouvrables + week-ends)
googleMoyenMn = (jo.moyen_mn × jo.nb + we.moyen_mn × we.nb) / (jo.nb + we.nb)

// Écart GPX (toutes sessions) vs Google mensuel
deltaMn = (gpxMoyen_s / 60) − googleMoyenMn
pct     = (deltaMn / googleMoyenMn) × 100
```

Rendu :
- **▲ rouge** `BandeauEcart` → terrain plus long → *« Google sous-estime »*
- **▼ vert** → terrain plus court → *« Google surestime »*
- **≈ neutre** → écart < 30 s → cohérence confirmée

Un badge `PuceEcart` identique est répété dans chaque colonne GPX
(Toutes sessions / Ce mois / Cette semaine) pour lecture rapide par période.

**Zone 3 — Confrontation terrain GPX (en bas, fond bleu pâle)**

Temps réellement parcourus en voiture — importés via la page Fiabilité.
Même découpage temporel (toutes sessions / ce mois / cette semaine) mais
calculé depuis `segments_terrain` côté client. Filtrage par `date_session`.

Si aucun GPX importé → message d'invitation vers la page Fiabilité.

#### Endpoint backend

**`GET /predire/resume?troncon_id={id}`** — réponse JSON unique :

```json
{
  "troncon_id": 1,
  "troncon_nom": "CARENA → Palm Beach",
  "courante": {
    "instant_local": "2026-06-23T14:23:00+00:00",
    "type_jour": "jour_ouvrable",
    "prediction": { "min_mn": 17, "moyen_mn": 19, "max_mn": 24 },
    "source": "google_routes",
    "confiance": 1.0,
    "calibration_appliquee": 0.0,
    "avertissement": null
  },
  "semaine": {
    "debut": "2026-06-22", "fin": "2026-06-23",
    "nb_mesures_total": 14,
    "jours_ouvrables": { "min_mn": 16, "moyen_mn": 19, "max_mn": 25, "nb_mesures": 14 },
    "week_ends": null
  },
  "mois": {
    "debut": "2026-06-01", "fin": "2026-06-23",
    "nb_mesures_total": 312,
    "jours_ouvrables": { ... },
    "week_ends": { ... }
  }
}
```

Le tag Swagger est **« temps de traversée par période »**.

#### Cascade « Temps actuel » — refondu 2026-06-23 (mesures temps réel par type de jour)

> Avant la refonte, le niveau 2 utilisait la table `profils_horaires` (60 jours
> glissants × créneau `(jour_semaine, heure)`). C'était lent à réagir aux
> changements récents et impliquait un job nocturne d'agrégation. La refonte
> remplace ce mécanisme par une lecture **directe des mesures Google récentes**.

Cascade actuelle (`backend/app/predicteur/profils.py`) :

| Niveau | Source                                     | Conditions                                                                  | Confiance |
|--------|---------------------------------------------|-----------------------------------------------------------------------------|-----------|
| 1      | **Mesure Google ±15 min**                  | Une mesure existe à ±15 min de l'instant cible                              | 1.0       |
| 2      | **Mesures Google même type de jour (7 j)** | Au moins 1 mesure du même `type_jour` (jour_ouvrable / week_end) sur 7 j    | 0.5–0.93 (log nb_mesures) |
| 3      | **Référence 50 km/h**                      | Repli déterministe depuis `distance_m`                                      | 0.3       |

Particularités du **niveau 2** :

- **Pas de filtre par heure** — toutes les mesures du même type de jour
  alimentent les stats. Le bloc « Temps actuel » affiche donc la fourchette
  min/moyen/max **du type de jour courant**, indépendamment du créneau
  horaire. C'est plus stable que de découper par heure sur un faible volume.
- **Fenêtre glissante de 7 jours** (constante `FENETRE_JOUR_TYPE_JOURS=7`)
  — typiquement 5 jours ouvrables + 2 week-ends, suffisamment représentatif
  sans traîner d'historique stale.
- **Aucune dépendance** à la table `profils_horaires` ni au job nocturne
  d'agrégation. La table existe encore pour la **heatmap** de la page
  Indicateurs (vue 24×7) mais n'est plus consommée par le prédicteur.
- L'identifiant de source dans la réponse JSON passe de
  `predicteur_profils_60j` à **`mesures_jour_type_7j`**.

#### Rôle des fichiers GPX dans la précision

Les relevés GPX importés via [`POST /terrain/import`](backend/app/api/terrain.py)
améliorent **uniquement la valeur « Temps actuel »** quand la cascade
tombe sur le niveau 2. Voici la chaîne exacte :

1. Chaque relevé terrain ayant `ReleveTerrain.source_reelle=True` (vrai
   GPX, pas synthétique) et `ecart_relatif` non-NULL est lu par
   `calculer_calibration()` ([backend/app/predicteur/profils.py](backend/app/predicteur/profils.py)).
   **Depuis le fix 2026-06-23**, l'endpoint marque automatiquement
   `source_reelle=True` (paramètre Form `synthetique=false` par défaut) —
   avant ce fix, la calibration n'a jamais été active en prod.
2. La moyenne des **8 derniers écarts** (constante `FENETRE_CALIBRATION_DEFAUT`)
   produit un **facteur de calibration** `ε = (T_terrain − T_api) / T_api`.
   Le filtre `type_jour_cible` ne retient que les ε des relevés du même
   type de jour que l'instant prédit (alignement DEESP § 4.5.5), avec repli
   sur l'ensemble si l'échantillon est trop petit.
3. **Seuil minimal** : sous **4 relevés réels** (constante `MIN_RELEVES_CALIBRATION`),
   la calibration reste désactivée pour éviter le bruit d'échantillonnage.
4. Le résultat niveau 2 est multiplié par `(1 + ε)` avant arrondi en minutes
   — exposé comme `calibration_appliquee` dans la réponse.
5. Tant que `nb_releves_reels < 4` pour un tronçon, `calibration_appliquee=0.0`
   et un `avertissement` explicite l'indique côté UI.

> **Important :** la calibration NE s'applique PAS aux blocs « Cette
> semaine » / « Ce mois » qui agrègent directement les mesures Google
> sans transformation. Elle agit uniquement sur le bloc « Temps actuel »
> et uniquement si la cascade descend au niveau 2 (Google indisponible
> au moment précis de la requête).

**Nombre cible de GPX par tronçon** : viser **8 relevés réels** étalés
sur ~4 semaines avec ≥ 2 week-ends pour que le filtre par type_jour ait
de quoi statuer. 4 sorties terrain de 2h30 couvrant les 6 tronçons en
une fois suffisent (48 relevés en base, ≈ 8 par tronçon).

#### OSRM — état après nettoyage 2026-06-23

`/diag/osrm/{id}` a été supprimé. OSRM ne reste utile que pour deux usages
**optionnels** :

| Usage                          | Fichier                         | Sans OSRM         |
|--------------------------------|---------------------------------|-------------------|
| Vraies polylines routières     | `app/complete_troncons.py`      | Pas de polyline (le tronçon nouvellement créé est simplement absent de la carte tant qu'on n'a pas lancé `complete_troncons`) |
| Confiance matching des GPX     | `app/api/terrain.py:_match_sous_trace` | `confiance_matching=NULL` — `ecart_relatif` est quand même calculé |

Le script `complete_sans_osrm.py` (polylines en segments droits) a été
**supprimé** : c'était un repli esthétique de transition. L'approche
recommandée maintenant est de lancer OSRM en local + tunnel Cloudflare
(`cloudflared tunnel --url http://localhost:5000`) ponctuellement pour
exécuter `python -m app.complete_troncons` une fois sur la console Railway,
puis de couper. Les polylines persistent en base (cf. § 8.5.1).

#### Code mort restant

- `_stats_profils()` et `evaluer_qualite()` dans
  [backend/app/predicteur/profils.py](backend/app/predicteur/profils.py)
  n'ont plus d'appelant (l'ancien niveau 2 par profils horaires et son
  endpoint qualité ont été supprimés). À nettoyer dans un commit ultérieur.
- Les fichiers `app/predicteur/heure_optimale.py`, `app/api/heure_optimale.py`,
  `frontend/components/prediction/OngletHeureOptimale.tsx`, et
  `backend/app/complete_sans_osrm.py` ont été supprimés.

### 4.8 Mesure au niveau sous-tronçon (P6.4bis — 2026-06-23)

> Refonte décidée le **2026-06-23** : la méthodologie DEESP (cf. § 4.5)
> codifie chaque axe en sous-tronçons (T1A, T1B, T1C…). Le code stockait
> déjà ces sous-tronçons (table `sous_troncons`, P6.4) mais ne les
> mesurait pas. Cette section décrit le pipeline complet désormais en place.

#### Modèle de données — migration 0009

`mesures.sous_troncon_id` (nullable, FK `sous_troncons.id` ON DELETE CASCADE)
+ index composite `(sous_troncon_id, horodatage)`.

Règle : une mesure porte **soit** sur un sous-tronçon (`sous_troncon_id`
renseigné, `troncon_id` = parent), **soit** sur l'axe entier (`sous_troncon_id`
NULL). Pas de contrainte SQL — la logique vit dans le scheduler.

#### Scheduler — règle d'exclusion parent/sous-tronçon

`cycle_de_collecte()` ([backend/app/collecte/scheduler.py](backend/app/collecte/scheduler.py)) :

1. Charge les tronçons parents actifs avec coords résolues.
2. Charge les sous-tronçons actifs.
3. **Pour chaque parent qui a ≥ 1 sous-tronçon actif** → on ne mesure
   PAS le parent (la granularité fine prend le relais). On mesure
   UNIQUEMENT les sous-tronçons via leurs `(lat_debut, lon_debut)` /
   `(lat_fin, lon_fin)`.
4. **Sinon** → on mesure le parent comme avant (comportement P2 inchangé).

Cette règle évite la double mesure et garde le quota Google sous contrôle.

#### Quota Google — recalcul après la refonte

`estimer_requetes_par_jour()` prend désormais `nb_entites_mesurees =
nb_parents_sans_sous + nb_sous_actifs`. Limites pratiques avec
`COLLECT_INTERVAL_MINUTES=60` (1 cycle/h, 24h/24) :

| Configuration | Entités mesurées | Req/jour | Statut |
|---|---|---|---|
| 6 parents seuls (P2 historique) | 6 | 144 | ✅ Sous quota |
| 6 parents + 5 sous-tronçons | 11 | 264 | ⚠️ **Au-dessus de 250** |
| 6 parents → décomposés en 11 sous-tronçons | 11 | 264 | ⚠️ Idem |

Solutions si on dépasse le plafond :
- Réduire la fréquence (`COLLECT_INTERVAL_MINUTES=120` → 1 cycle / 2h)
- Limiter la plage horaire (`COLLECT_START_HOUR=7`, `COLLECT_END_HOUR=19`)
- Activer le plan Google payant

L'endpoint `POST /administration/troncons` renvoie un bloc `adoption_collecte`
qui calcule l'impact en temps réel.

#### Carte temps réel

`GET /carte/etat` enrichit désormais chaque tronçon parent d'un tableau
`sous_troncons[]`. Chaque entrée contient : `code`, `nom_court`, `polyline`,
`distance_m`, `classe_congestion`, `couleur_etat`, `derniere_mesure`,
`couleur_google.pourcentage_*`.

Côté frontend ([CarteLeaflet.tsx](frontend/components/carte/CarteLeaflet.tsx)) :
- Si un parent a des sous-tronçons → le parent est tracé en **pointillé léger
  (opacity 0.35)** pour situer l'axe, et chaque sous-tronçon est tracé
  en **trait plein épais** coloré selon SA classe DEESP.
- Sinon → comportement inchangé (1 trait épais par tronçon).

Cleanup automatique : si un sous-tronçon disparaît (archivé), sa polyline
est retirée de la carte au prochain refresh.

#### Aperçu Fiabilité

[CarteApercu.tsx](frontend/components/fiabilite/CarteApercu.tsx) affiche
désormais les sous-tronçons (lignes pleines colorées) en superposition
des tronçons parents (pointillés) — utile pour confronter visuellement
les GPX terrain à la granularité fine.

#### Tableau 16 (Rapport DEESP)

`troncons_congestionnes()` ([backend/app/analyse/rapport_paa.py](backend/app/analyse/rapport_paa.py))
applique désormais les règles ≥ 3-jour / ≥ 4-semaine **au niveau sous-tronçon**
quand celui-ci porte les mesures. Chaque entrée du tableau remontée par
`GET /rapport/zones-congestionnees` contient :

```json
{
  "troncon_id": 1, "troncon_nom": "CARENA → Palm Beach",
  "sous_troncon_id": 7, "sous_troncon_code": "T1C", "sous_troncon_nom": "Pont H-B",
  "heure": 8, "tranche": "08h-09h",
  "nb_par_jour_semaine": {"lundi": 4, "mardi": 3, "mercredi": 4},
  "regle_jour_indicatif": true, "regle_semaine": true
}
```

Le frontend affiche une colonne **« SOUS-TRONÇON »** dédiée. Pour les
mesures sans sous-tronçon, la cellule indique *« axe entier »* en italique.

#### Polylines réelles via OSRM

À la création d'un tronçon ou sous-tronçon, le backend tente
automatiquement OSRM `/route` si `OSRM_BASE_URL` est configurée — la
polyline et la distance suivent alors les vraies routes. Repli silencieux
sur segment droit + distance Haversine si OSRM est indisponible.

`python -m app.complete_troncons` (re)génère les polylines pour TOUS les
tronçons + sous-tronçons actifs en une seule commande. Le script accepte
maintenant les tronçons créés via Admin (utilise leurs coords en base)
en plus des 6 axes officiels mappés par nom dans `coordonnees.py`.

#### Procédure « Ajouter un tronçon/sous-tronçon avec tracé routier réel »

> À faire chaque fois que vous créez un nouveau tronçon ou sous-tronçon via
> la page Administration et que vous voulez qu'il s'affiche avec le tracé
> réel sur la carte (pas une ligne droite).

**Durée totale : ~10 minutes.**

**Étape 1 — Créer le tronçon via la page Administration**

Remplissez le formulaire (nom, coordonnées origine + destination).
Le tronçon apparaît immédiatement sur la carte en **ligne droite** — c'est
normal, OSRM n'a pas encore calculé le tracé routier.

**Étape 2 — Démarrer OSRM en local** (Windows PowerShell)

```powershell
# Dans le dossier du projet
docker compose up -d osrm
# Attendre ~30 secondes que le service démarre
docker compose logs osrm --tail 5
# → doit afficher "running and waiting for requests"
```

**Étape 3 — Créer un tunnel Cloudflare** (nouvelle fenêtre PowerShell)

```powershell
# cloudflared-windows-amd64.exe doit être dans le dossier du projet
.\cloudflared-windows-amd64.exe tunnel --url http://localhost:5000
# → affiche une URL du type : https://xxxx-yyyy-zzzz.trycloudflare.com
# Laisser cette fenêtre ouverte pendant toute la procédure
```

**Étape 4 — Connecter Railway à votre OSRM local**

```powershell
# Remplacer l'URL par celle affichée par cloudflared à l'étape 3
railway variable set "OSRM_BASE_URL=https://xxxx-yyyy-zzzz.trycloudflare.com" --service backend
```

**Étape 5 — Regénérer toutes les polylines** (Console Railway — onglet Console du service backend)

```bash
python -m app.complete_troncons
# → affiche [OK] pour chaque tronçon et sous-tronçon avec leur polyline
# → les nouveaux tronçons créés en Administration sont inclus automatiquement
```

**Étape 6 — Nettoyer**

```powershell
# Supprimer la variable Railway (OSRM n'est plus nécessaire)
railway variable delete OSRM_BASE_URL --service backend
# Fermer la fenêtre cloudflared (Ctrl+C)
# Arrêter OSRM local (optionnel — libère de la RAM)
docker compose stop osrm
```

**Étape 7 — Vérifier sur la carte**

Ouvrir la page **Accueil / Carte** et faire **Ctrl+Shift+R** (hard refresh).
Le nouveau tronçon doit maintenant suivre les vraies routes (pas une ligne droite).

> **Les polylines sont persistées en base PostgreSQL Railway.** Une fois
> générées, elles restent même si OSRM est éteint. Il ne faut répéter
> cette procédure qu'à chaque ajout de nouveau tronçon ou sous-tronçon.

---

### 4.6 Adoption dynamique des tronçons créés via /administration

> Question récurrente : *« Si j'ajoute un nouvel axe via la page
> Administration, est-ce que la collecte, les indicateurs, le rapport DEESP
> et la calibration GPX s'appliquent à lui automatiquement ? »*
>
> **Réponse : oui, sans redéploiement ni redémarrage**, sous réserve des
> deux conditions ci-dessous.

#### Conditions

1. Le tronçon est créé avec `actif = true` (toujours le cas via
   `POST /administration/troncons`).
2. Les 4 coordonnées (lat/lon origine + destination) sont renseignées
   (le formulaire de la page Administration les exige).

#### Chaîne d'adoption automatique

| Couche | Mécanisme | Visibilité |
|--------|-----------|------------|
| **Collecte Google** | `cycle_de_collecte()` recharge la liste des tronçons actifs à chaque tick (filtres `actif=True` + `lat/lon_*` NOT NULL). | Au **prochain cycle** (≤ `COLLECT_INTERVAL_MINUTES`). |
| **Carte temps réel** | `construire_etat_carte()` sélectionne `Troncon.actif.is_(True)` — diffusion WebSocket post-cycle. | Dès la prochaine collecte. |
| **Indicateurs DEESP + série + heatmap** | Tous indexés par `troncon_id`, sans whitelisting. La qualification fluide/congestionné est lue depuis `est_congestionne` (couleur Google Maps). | Dès qu'il y a ≥ 1 mesure couleur (cf. § 4.5.2bis). |
| **Profils horaires nocturnes** | `executer_agregation()` boucle sur toutes les mesures de la fenêtre 90 j. | Au prochain run nocturne (23h00 Africa/Abidjan). |
| **Prédicteur DEESP** | Lit `profils_horaires` par `troncon_id`. | Une fois l'agrégation passée et les buckets remplis. |
| **Heure optimale** | `_trouver_troncon_le_plus_proche()` ouvre la liste à tous les actifs. | Immédiatement. |
| **Rapport DEESP** (Tableaux 1, 3-17, 19 + Graphiques 1-12) | `temps_theoriques`, `temps_traversee_par_troncon`, `troncons_congestionnes`, `serie_graphique`, `comparaison_campagnes` filtrent tous sur `Troncon.actif.is_(True)`. | Dès la campagne suivante. |
| **Validation terrain (GPX)** | `POST /terrain/import` découpe les traces sur **tous** les tronçons actifs et appariere chaque sous-trace à la mesure Google la plus proche. | Au prochain upload GPX. |
| **Exports CSV/XLSX** | Filtres par `troncon_id` exclusivement. | Immédiatement. |
| **Frontend** | Pages Indicateurs / Prédiction / Heure optimale / Carte / Administration appellent `api.troncons()` et `/carte/etat` au montage. | Au prochain rechargement de page. |

#### Garanties exposées dans la réponse d'API

`POST /administration/troncons` retourne désormais un bloc
`adoption_collecte` qui chiffre l'impact immédiat :

```json
{
  "id": 12,
  "nom": "AGL → Grand Moulin",
  ...
  "adoption_collecte": {
    "nb_troncons_actifs": 7,
    "google_requetes_par_jour": 168,
    "plafond_google": 250,
    "scheduler_redemarrage_requis": false,
    "inclusion_prochain_cycle": true,
    "avertissement_quota": null
  }
}
```

Si l'estimation dépasse `plafond_google`, `avertissement_quota` contient
le message à présenter à l'administrateur (réduction de fréquence /
plage horaire à envisager).

#### Limites connues à corriger plus tard

- **Polyline d'un tronçon créé en prod sans OSRM** : segment droit
  Haversine entre les deux extrémités (cf. § 8.5.1). Esthétique
  uniquement — la collecte et l'analyse fonctionnent. Pour le tracé
  routier réel, exposer OSRM (option B § 8.7) puis lancer
  `python -m app.complete_troncons`.
- **Graphique « Évolution pluriannuelle »** (page Indicateurs) : il
  s'appuie sur la table `evolution_indicateur` alimentée uniquement
  pour les 6 axes officiels par les imports P6.1. Un nouveau tronçon
  n'y apparaîtra pas tant qu'aucune campagne historique ne le
  couvre — c'est conforme à la **règle d'or** § 2.5 (pas d'invention
  de données). Le reste du pipeline n'est pas concerné.
- **POI markers de la carte** : seuls les 4 libellés CARENA / Toyota
  CFAO / SODECI / Palm Beach reçoivent un pin coloré (`C`, `T`, `S`,
  `P`). Les nouveaux tronçons s'affichent normalement, mais sans pin
  d'extrémité dédié — cosmétique, n'affecte pas l'analyse.

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
├── README.md                  # Documentation utilisateur (FR), grand public
├── railwaydeploy.md           # Procédures + pièges Railway (à lire avant railway up)
├── .gitignore
├── docker-compose.yml         # Orchestration des 5 services
├── backend/
│   ├── .env.example           # Modèle d'environnement backend (sans secrets)
│   ├── .env.railway           # Modèle d'environnement Railway (production)
│   ├── railway.toml           # Configuration de déploiement Railway
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/               # Migrations 0001 (initial) → 0002 (IQR) → 0003 (P6.1)
│   └── app/                   # Code FastAPI
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
- `OSRM_BASE_URL` *(optionnel — si absent, le repli OSRM est désactivé, les 2 premiers niveaux de la cascade suffisent)*
- `GOOGLE_ROUTES_API_KEY`
- `COLLECT_INTERVAL_MINUTES`, `COLLECT_START_HOUR`, `COLLECT_END_HOUR`
- `REFERENCE_SPEED_KMH` (50 par défaut)
- `TZ=Africa/Abidjan`
- `API_SECRET_KEY`, `ALLOWED_ORIGINS`

**Frontend :**
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_DEFAULT_LANG` (`fr` par défaut)

---

## 7bis. Segments terrain — précision progressive par accumulation GPX

> Section ajoutée le **2026-06-23** suite à l'import des 26 fichiers GPX
> terrain enregistrés le 2026-06-22 avec BasicAirData GPS Logger.

### Principe

Les fichiers GPX réels enregistrés sur le terrain couvrent souvent des
**sous-portions** d'un axe officiel (entre deux landmarks intermédiaires),
pas forcément le trajet complet depuis l'extrémité officielle. Le système
`segments_terrain` (migration 0010) accumule ces sous-sections et calcule
la durée de traversée complète par **somme des durées des segments**.

La précision s'améliore automatiquement à chaque nouvelle session importée :

| Sessions | Comportement |
|----------|-------------|
| 1 session | Estimation directe (somme des segments de cette session) |
| N sessions | Moyenne des N estimations par tronçon |
| Miroir aller/retour | Si un sens manque de données, utilise le sens opposé |

### Table `segments_terrain` (migration 0010)

Chaque ligne = un segment entre deux landmarks :

| Colonne | Description |
|---------|-------------|
| `nom_segment` | Libellé libre (ex. « CARENA → GMA ») |
| `troncon_id` | Tronçon officiel parent (nullable) |
| `direction` | « aller » ou « retour » |
| `lat_debut / lon_debut` | GPS premier point enregistré |
| `lat_fin / lon_fin` | GPS dernier point enregistré |
| `duree_s` | Durée mesurée (fin - début en secondes) |
| `distance_m` | Distance Haversine cumulée de la trace |
| `session_id` | Identifiant de session (ex. « 20260622_A ») |
| `source_reelle` | True = GPX téléphone réel (False = synthétique) |
| `contenu_gpx` | Contenu binaire BYTEA — source de vérité |

### Sessions du 2026-06-22 (26 fichiers importés)

| Session | Tronçon | Segments | Durée cumulée | Couverture |
|---------|---------|---------|---------------|------------|
| 20260622_A | 1 CARENA→Palm Beach | 12 | **39:37 min** | ~85 % |
| 20260622_B | 2 Palm Beach→CARENA | 8 | 30:11 min (partiel) | ~54 % |
| 20260622_C | 3 Toyota→Carrefour | 1 | 7:29 min (partiel) | ~6 % |
| 20260622_C | 4 Carrefour→Toyota | 1 | 2:22 min (partiel) | ~6 % |
| 20260622_D | 5 SODECI→Gendarmerie | 1 | 23:30 min (partiel) | ~22 % |
| 20260622_E | 2 Carrefour→GMA | 3 | 5:00 min (complément B) | +21 % |

> **Congestion observée lundi 9h** : CARENA→Palm Beach = 39:37 min vs 17:53 min
> référence = **×2,2**. Zone la plus congestionnée : Carrefour Seamen's →
> Pharmacie du port : 517 m en **11:38 min** = **2,7 km/h**.

### Miroir aller/retour (approximation initiale — Session B+E ≈ Session A)

Par instruction opérateur (*« l'aller est le même que le retour »*), les
tronçons sans couverture directe utilisent le sens opposé :

| Tronçon sans données | Utilise |
|----------------------|---------|
| Tronçon 2 (Palm Beach→CARENA) retour incomplet | Session A miroir = 39:37 min |
| Tronçon 4 (Palm Beach→Toyota) incomplet | Session C aller miroir = 7:29 min partiel |
| Tronçon 6 (Palm Beach→SODECI) absent | Session D aller miroir = 23:30 min partiel |

La précision s'améliore automatiquement dès que de nouveaux GPX couvrant
ces tronçons sont importés via `POST /terrain/segments/import`.

### Endpoints (tag « segments terrain (GPX libres) »)

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| `POST` | `/terrain/segments/import` | Importer un segment GPX |
| `GET` | `/terrain/segments` | Lister tous les segments (id + métadonnées) |
| `GET` | `/terrain/segments/{id}/gpx` | Contenu GPX brut (BYTEA) — utilisé par la carte Fiabilité pour recharger les traces au montage |
| `GET` | `/terrain/segments/resume` | Résumé temps × tronçon (tous) |
| `GET` | `/terrain/segments/resume/{id}` | Résumé pour un tronçon |

### Script d'import des 26 fichiers (session initiale 2026-06-22)

```powershell
# Depuis le dossier backend/
# Dry-run (aucune requête) :
python -m scripts.importer_segments_gpx --dry-run

# Import réel vers le backend local :
python -m scripts.importer_segments_gpx --api-url http://localhost:8000

# Import vers Railway (production) :
python -m scripts.importer_segments_gpx --api-url https://backend-production-6cbf.up.railway.app
```

Le script reconnaît les 26 fichiers par correspondance sur le nom de fichier
et les assigne automatiquement au bon tronçon + direction + session.

### Import via l'interface Fiabilité (sessions futures)

La page **Fiabilité** expose désormais un bloc dédié « Précision progressive —
parcours libres » en bas de page. L'opérateur peut y importer ses GPX sans
ligne de commande.

#### Règle fondamentale — importer **par lot par tronçon**

> **Tous les fichiers d'un même lot doivent appartenir au même tronçon.**
> Le `session_id` regroupe les segments — le système les somme pour obtenir
> un temps total. Si des fichiers de tronçons différents sont mélangés dans
> un même import sans `troncon_id`, ils atterrissent sans affectation et
> n'apparaissent dans aucun résumé.

**Procédure en 4 étapes pour une nouvelle sortie terrain :**

1. **Enregistrer** avec BasicAirData GPS Logger — démarrer le tracking dès le
   point de départ, couper à l'arrivée d'un segment intermédiaire (arrêt feu,
   carrefour, landmark). Créer un fichier GPX par tronçon intermédiaire.
2. **Ouvrir** la page Fiabilité → section « Importer des segments GPX libres ».
3. **Importer par lot** : sélectionner tous les fichiers du **même tronçon**,
   renseigner :
   - **Tronçon** : le bon id (1 CARENA→Palm Beach, 2 Palm Beach→CARENA, etc.)
   - **Direction** : Aller ou Retour (ou Auto-détecter si vous avez confiance en
     les coords GPS)
   - **Session ID** : un code unique par sortie terrain, ex. `20260630_A`.
     Tous les fichiers du même trajet partagent le **même** `session_id`.
4. **Répéter** pour chaque tronçon de la sortie (changer le `tronçon_id` et
   éventuellement la direction entre chaque lot).

**Correspondance tronçon ↔ axe officiel :**

| ID | Sens | Repères |
|----|------|---------|
| 1 | CARENA → Palm Beach | Axe 1 aller — depuis bd de Marseille |
| 2 | Palm Beach → CARENA | Axe 1 retour |
| 3 | Toyota CFAO → Palm Beach | Axe 2 aller |
| 4 | Palm Beach → Toyota CFAO | Axe 2 retour |
| 5 | SODECI → Palm Beach | Axe 3 aller |
| 6 | Palm Beach → SODECI | Axe 3 retour |

#### Comment la confiance s'améliore (formule)

```
confiance = (couverture_km / distance_totale_km) × min(nb_sessions, 8) / 8
```

Exemples concrets :

| Sessions | Couverture moy. | Confiance |
|----------|----------------|-----------|
| 1 session | 85 % | 0.11 (11 %) |
| 4 sessions | 85 % | 0.43 (43 %) |
| 8 sessions | 85 % | 0.85 (85 %) |
| 4 sessions | 100 % | 0.50 (50 %) |
| 8 sessions | 100 % | **1.00 (100 %)** |

**Cible opérationnelle** : 8 sorties terrain couvrant chacune ≥ 85 % du
tronçon → confiance ≥ 85 % pour tous les axes. 4 sorties à 100 % → 50 %.

### Procédure pour supprimer les GPX synthétiques

Les GPX synthétiques (générés par `generer_gpx_synthetiques.py`) ont
`source_reelle=False` — ils n'affectent pas la calibration mais polluent
l'historique. Les supprimer via la **Console Railway** :

```bash
# Console Railway — service backend
python -c "
from app.db.session import SessionLocal
from app.models.models import ReleveTerrain
db = SessionLocal()
n = db.query(ReleveTerrain).filter(ReleveTerrain.source_reelle == False).delete()
db.commit()
print(f'{n} releves synthetiques supprimes')
db.close()
"
```

> Note : le `DELETE` SQL brut ne fonctionne pas directement dans le shell
> Railway — il faut passer par Python comme ci-dessus.

### Page Fiabilité — comportement carte (état 2026-06-23)

La **page Fiabilité** charge automatiquement les traces GPX au montage :

1. `GET /terrain/segments` → liste de tous les segments en base
2. Pour chacun : `GET /terrain/segments/{id}/gpx` → contenu BYTEA
3. Parse côté client (`parserGpxTexte`) → trace affichée sur la carte Leaflet
4. **Marqueurs début/fin** : disque vert sur le premier point GPX, disque rouge
   sur le dernier point GPX de chaque trace — **pas besoin d'OSRM**.

Quand l'utilisateur sélectionne de nouveaux fichiers dans le picker :
- Parse immédiat côté client → traces de la sélection ajoutées à la carte
- Après clic "Importer" → traces passent en DB → `tracesSelection` effacé →
  `tracesDb` rechargé pour inclure les nouveaux segments.

### Page Temps de traversée — structure finale (état 2026-06-24)

La page est organisée en **trois zones verticales** :

#### Zone 1 — Google Maps (en haut, en avant)

Données temps réel provenant de l'API Google Routes, mises à jour à chaque
cycle de collecte (toutes les heures). Trois blocs :

| Bloc | Source | Calcul |
|------|--------|--------|
| **Temps réel (Google Maps)** | `mesures` + `predire/resume` | Mesure la plus récente ±15 min, sinon moyenne 7 j même type de jour |
| **Ce mois — Google Maps** | `mesures` filtrées sur le mois courant | min/moyen/max, séparation jours-ouvrables / week-ends, moyenne pondérée |
| **Cette semaine — Google Maps** | `mesures` filtrées sur la semaine courante | idem |

**Principe de collecte Google (cascade — `backend/app/predicteur/profils.py`) :**

- Une mesure = un appel API Google Routes stocké dans `mesures` (source=`google`),
  avec `duree_trafic_s` en secondes et `est_congestionne` (couleur Maps).
- **Temps actuel** → Niveau 1 : mesure Google dans ±15 min autour de maintenant.
  Niveau 2 : si aucune, moyenne des 7 derniers jours de même `type_jour`
  (`jour_ouvrable` ou `week_end`). Niveau 3 (repli) : distance / 50 km/h.
- **Ce mois** → toutes les mesures Google du mois courant, filtrées
  `aberrante=False`, séparées par type de jour, puis `min/fmean/max` calculés
  côté backend en Python. La moyenne mensuelle pondérée (jo + we) est
  recalculée côté frontend pour le calcul d'écart.
- **Cette semaine** → même logique mais fenêtre = lundi 00:00 local → maintenant.

#### Zone 2 — Bandeau d'écart Google ↔ Terrain (entre les deux sections)

Affiché uniquement si des données GPX **et** des données Google sont disponibles.
Calcul **entièrement côté client** (`PagePrediction.tsx`) :

```typescript
// Moyenne Google mensuelle pondérée (jours ouvrables + week-ends)
googleMoyenMn = (jo.moyen_mn × jo.nb + we.moyen_mn × we.nb) / (jo.nb + we.nb)

// Écart
deltaMn = (gpxMoyen_s / 60) - googleMoyenMn
pct     = (deltaMn / googleMoyenMn) × 100
```

Rendu visuel :
- **▲ rouge** : terrain plus long que Google → *« Google sous-estime »*
- **▼ vert** : terrain plus court que Google → *« Google surestime »*
- **≈ neutre** : écart < 30 s → données cohérentes

Le même badge `PuceEcart` est répété dans chaque colonne GPX (Toutes / Ce mois
/ Cette semaine) pour une lecture rapide par période.

#### Zone 3 — Confrontation terrain GPX (en bas, fond bleu pâle)

Temps **réellement mesurés en voiture** via les fichiers GPX importés sur la
page Fiabilité. Même découpage temporel (toutes sessions / ce mois / cette
semaine) mais calculé depuis `segments_terrain` côté client. Filtrage par
`date_session`.

| Bloc | Source | Calcul |
|------|--------|--------|
| **Toutes sessions** | `segments_terrain` (toutes dates) | min/moyen/max des `duree_totale_s` par session |
| **Ce mois** | `segments_terrain` filtrés `date_session ≥ 1er du mois` | idem |
| **Cette semaine** | `segments_terrain` filtrés `date_session ≥ lundi` | idem |

Les temps GPX sont affichés en format `mm:ss min` (ex. `39:37 min`).
Le filtrage par période est **entièrement côté client** (pas d'endpoint supplémentaire).
La section GPX affiche un message d'invitation si aucun GPX n'a encore été importé.

**Sous-titre de la page :** *« Temps réel basé sur Google Maps — confrontation
avec les temps terrain GPX en bas de page. »*

---

## 8. Déploiement

### 8.1 Architecture cible

| Composant      | Hébergement                         | Justification                                  |
|----------------|-------------------------------------|------------------------------------------------|
| `backend`      | **Railway** (service Docker)        | Plan simple, $PORT injecté, healthcheck natif. |
| `db`           | **Railway plugin PostgreSQL**       | Provisionnement 1-clic, sauvegardes auto.      |
| `redis`        | **Railway plugin Redis**            | Idem.                                          |
| `osrm`         | **Hors Railway** — voir § 8.3       | Image OSRM + extrait OSM (~ 800 Mo) trop lourds pour Railway. |
| `frontend`     | Railway ou Vercel (à venir P4)      | À décider en P4 selon coût.                   |

### 8.2 URL publique du backend

**URL de production (déployée le 2026-06-19) :**
`https://backend-production-6cbf.up.railway.app`

Endpoints critiques :
- `GET /health` → `{"status":"ok"}` ✅
- `GET /collecte/status` → scheduler actif, 6 tronçons, 216 req/jour estimées ✅
- `GET /carte/etat` → état des 6 tronçons
- `GET /docs` → Swagger interactif

### 8.2.1 Points d'attention déploiement Railway

> 📖 La procédure complète, tous les pièges rencontrés (P1 → P6.1) et la
> checklist de déploiement sont dans [`railwaydeploy.md`](railwaydeploy.md) à la racine.

Résumé des règles critiques :

- **`git add -A` + commit obligatoires avant `railway up`** — Railway utilise `git archive` et ignore les fichiers non commités. Symptôme classique : la migration ou le fichier que tu viens de créer est absent du conteneur.
- **`startCommand`** : **ne JAMAIS inclure `alembic upgrade head`** — provoque un `pg_advisory_lock` persistant qui bloque le démarrage 7 minutes puis fait échouer le healthcheck. Lancer les migrations depuis la **Console Railway** après chaque déploiement contenant une nouvelle migration.
- **`${PORT}`** : envelopper le startCommand dans `sh -c '...'` pour que la variable soit interprétée par le shell.
- **`AsyncIOScheduler.start()`** : doit être appelé depuis le contexte async uvicorn (lifespan FastAPI), **pas** depuis `asyncio.to_thread()`.
- **`UploadFile` / `Form`** : exige `python-multipart` dans `requirements.txt`.
- **`numReplicas = 1`** : APScheduler vit en mémoire — toute duplication entraînerait une double collecte.
- **Premier déploiement** : seed via la Console Railway → `python -m app.seed_troncons`.

### 8.3 OSRM : ce qui en a besoin, et options d'hébergement

#### Ce qui fonctionne SANS OSRM (état actuel en production)

| Fonctionnalité | Besoin OSRM ? | Explication |
|---|---|---|
| **Carte temps réel** (polylines des 6 tronçons) | ❌ Non | Les polylines sont déjà persistées en base Railway depuis le 2026-06-23 |
| **Collecte Google Routes** (mesures toutes les heures) | ❌ Non | API Google uniquement |
| **Page Fiabilité** (import GPX + carte + marqueurs début/fin) | ❌ Non | Traces brutes + 1er/dernier point GPX suffisent |
| **Page Temps de traversée** (terrain GPX en source principale) | ❌ Non | Calcul depuis `segments_terrain.duree_s` |
| **Rapport DEESP** (tableaux + graphiques) | ❌ Non | Base sur mesures Google uniquement |

#### Ce qui nécessite OSRM

| Fonctionnalité | Besoin OSRM ? | Explication |
|---|---|---|
| **Création de nouveaux tronçons** avec polyline routière réelle | ⚠️ Optionnel | Sans OSRM → segment droit Haversine (esthétique uniquement) |
| **`python -m app.complete_troncons`** | ✅ Oui | Recalcule les polylines en suivant les routes |
| **`confiance_matching`** dans les relevés terrain | ✅ Oui | Score OSRM Map Match — reste NULL sans OSRM |

**Conclusion : l'application complète fonctionne en production sans OSRM.**
OSRM n'est utile que ponctuellement (créer un nouveau tronçon avec un tracé
routier propre). On le lance alors localement + tunnel Cloudflare 10 min, puis
on coupe (cf. procédure § 8.5.1).

#### Peut-on déployer OSRM sur Railway ?

**Non, pas sur le tier gratuit Railway.** L'image Docker OSRM + l'extrait OSM
Côte d'Ivoire pré-indexé pèsent ~800 Mo et nécessitent ~1 Go RAM au démarrage.
Railway Pro coûte ~20 $/mois pour ce profil — non justifié pour un usage ponctuel.

**Alternatives :**

OSRM nécessite un fichier `ivory-coast-latest.osrm` (~ 200 Mo) pré-indexé qui
ne tient pas dans le tier gratuit Railway. Le backend tolère son absence.

#### Option A — OSRM local exposé via ngrok *(temporaire, démo)*

Rapide à mettre en place mais lié à votre machine allumée.

```powershell
# Pré-requis : OSRM tourne déjà localement sur :5000 (docker compose up osrm)
ngrok http 5000
# → ngrok affiche une URL https://xxxx-xxx-xxx.ngrok-free.app
railway variables set OSRM_BASE_URL='https://xxxx-xxx-xxx.ngrok-free.app'
```

**Limites** : URL ngrok change à chaque redémarrage, latence ajoutée (~ 100 ms),
plan gratuit limité à 40 connexions/min. **Acceptable pour la démo jury, pas
pour la production.**

#### Option B — OSRM sur Oracle Cloud Free Tier *(permanent, recommandé)*

Une VM Ampere A1 (4 vCPU ARM + 24 Go RAM, gratuite à vie chez Oracle) supporte
largement OSRM avec l'extrait Côte d'Ivoire. **Procédure pas à pas en 8 étapes
ci-dessous (§ 8.7) — la première mise en place prend ~60 min.**

**Coût** : 0 € (Free Tier permanent tant qu'on reste sous 4 vCPU / 24 Go RAM).
**Latence** : selon la région — choisir Marseille ou Paris pour optimiser
vers Abidjan (Africa/Abidjan = UTC+0, pas de problème de fuseau).

### 8.4 Variables d'environnement Railway

Liste exhaustive dans `backend/.env.railway`. Injection en bloc :

```bash
railway variables --set "DATABASE_URL=\${{Postgres.DATABASE_URL}}" --service backend
railway variables --set "REDIS_URL=\${{Redis.REDIS_URL}}" --service backend
railway variables --set "GOOGLE_ROUTES_API_KEY=AIza..." --service backend
railway variables --set "API_SECRET_KEY=<40+ caractères aléatoires>" --service backend
railway variables --set "ALLOWED_ORIGINS=https://<front>.up.railway.app" --service backend
railway variables --set "TZ=Africa/Abidjan" --service backend
railway variables --set "COLLECT_INTERVAL_MINUTES=20" --service backend
railway variables --set "COLLECT_START_HOUR=7" --service backend
railway variables --set "COLLECT_END_HOUR=19" --service backend
# OSRM_BASE_URL : optionnel — cf. § 8.3. Ne PAS définir si OSRM n'est pas exposé.
```

> **Quota Google :** intervalle 20 min × (19h − 7h) × 6 tronçons = **216 req/jour**
> (limite Google : 250). Passer à 15 min donne 288 req/jour → dépasse le quota.

### 8.5 Adaptations code spécifiques Railway

- **`app/db/session.py`** + **`alembic/env.py`** : un normaliseur convertit
  `postgresql://...` (forme exposée par les plugins managés) en
  `postgresql+psycopg://...` (forme exigée par psycopg v3). Transparent en local.
- **`app/core/config.py`** : `OSRM_BASE_URL` est **optionnel** (`str | None`).
  Si absent, l'endpoint `/diag/osrm/{id}` et `complete_troncons.py` lèvent une
  erreur explicite ; le reste fonctionne normalement.
- **`Dockerfile`** : la CMD utilise `${PORT}` (variable Railway), tombe sur
  `8000` par défaut (dev local).
- **`backend/railway.toml`** : `startCommand = "sh -c 'uvicorn app.main:app
  --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=*'"` —
  **sans** `alembic upgrade head`.

### 8.5.1 Polylines en production — état au 2026-06-23

> **Situation actuelle :** les polylines réelles OSRM sont **déjà persistées**
> dans la base Railway. Aucune action n'est nécessaire pour les voir — un
> hard refresh (`Ctrl+Shift+R`) suffit côté navigateur.

| Tronçon (id) | Polyline | Route suivie |
|--------------|----------|--------------|
| 1 CARENA → Palm Beach | 939 cars | Bd de Marseille + pont HB |
| 2 Palm Beach → CARENA | 1081 cars | Retour complet |
| 3 Toyota CFAO → Palm Beach | 558 cars | Av. Christiani + port |
| 4 Palm Beach → Toyota CFAO | 567 cars | Retour |
| 5 SODECI → Palm Beach | 577 cars | Zone 4 → port |
| 6 Palm Beach → SODECI | 580 cars | Retour |

Ces polylines ont été générées via `python -m app.complete_troncons` lancé
depuis la Console Railway le 2026-06-23, avec un **tunnel Cloudflare** exposant
l'OSRM local (préféré à ngrok car le port 22 SSH était bloqué et cloudflared
ne nécessite pas de compte).

**Pour rejouer `complete_troncons` (idempotent) :**

| Ingrédient | Source recommandée |
|------------|-------------------|
| OSRM local | `docker compose up osrm` (extrait Côte d'Ivoire déjà indexé localement) |
| Tunnel HTTPS | `.\cloudflared-windows-amd64.exe tunnel --url http://localhost:5000` → URL `https://xxxx.trycloudflare.com` |
| Variable Railway | `railway variable set "OSRM_BASE_URL=https://xxxx.trycloudflare.com" --service backend` |

```powershell
# Windows — cloudflared dans le dossier du projet
.\cloudflared-windows-amd64.exe tunnel --url http://localhost:5000
# → https://xxxx.trycloudflare.com

railway variable set "OSRM_BASE_URL=https://xxxx.trycloudflare.com" --service backend

# Console Railway
python -m app.complete_troncons

# Nettoyage
railway variable delete OSRM_BASE_URL --service backend
```

Tableau récapitulatif des scripts de complétion des tronçons :

| Script | Coords | Polyline | Distance | Nécessite OSRM |
|--------|--------|----------|----------|----------------|
| `seed_troncons` | ❌ NULL | ❌ NULL | distance officielle | ❌ |
| `set_coords_depuis_seed` | ✅ depuis `coordonnees.py` | inchangée | inchangée | ❌ |
| `complete_troncons` | ✅ depuis `coordonnees.py` | ✅ **suivant les routes** | recalculée par OSRM | ✅ |

> `complete_sans_osrm.py` (segments droits) a été **supprimé** le 2026-06-23 —
> jugé trop pauvre visuellement. `complete_troncons` avec tunnel Cloudflare
> ponctuel est la procédure standard désormais.

### 8.6 Première initialisation (à faire une seule fois)

Toutes les commandes se lancent depuis la **Console Railway** du service `backend`
(onglet Console — `railway run` ne fonctionne pas car les dépendances Python
ne sont pas installées localement et le DNS interne `postgres.railway.internal`
n'est pas résolu depuis ta machine) :

```bash
alembic upgrade head              # applique les migrations 0001 → 0003
python -m app.seed_troncons       # insère les 6 tronçons officiels
python -m app.complete_troncons   # (optionnel) calcule les polylines via OSRM
```

Si `OSRM_BASE_URL` n'est pas configurée, `complete_troncons` échouera — c'est
acceptable, les tronçons fonctionnent avec leurs coordonnées de seed.

---

### 8.7 Déploiement OSRM sur Oracle Cloud Free Tier — procédure complète

Cette procédure pose un OSRM accessible en HTTPS publique à partir de zéro.
Une fois en place, Railway pourra appeler `OSRM_BASE_URL=https://osrm.tondomaine.com`
et `complete_troncons` produira des polylines suivant les vraies routes.

> ⏱️  Temps de mise en place : **45-60 min** la première fois (compte
> Oracle à créer, VM à provisionner, indexation OSRM ~3-5 min).
> Coût récurrent : **0 €** tant qu'on reste sous le quota Always Free.

#### Étape 1 — Compte Oracle Cloud (10 min)

1. Aller sur <https://www.oracle.com/cloud/free/> → **Start for free**.
2. Choisir la **région la plus proche d'Abidjan** : `Paris (FR-PAR)`,
   `Marseille (FR-MRS)`, ou `Madrid (ES-MAD)`. Important : **on ne peut plus
   changer après**, et la latence vers Abidjan dépend de ce choix.
3. Remplir les infos (nom, email, téléphone vérifié par SMS, **carte bancaire
   pour vérification d'identité — pas de débit tant que tu restes en Always Free**).
4. Attendre la validation du compte (1-15 min).

#### Étape 2 — Créer la VM Ampere A1 (5 min)

Dans la console Oracle Cloud :

1. Menu hamburger → **Compute → Instances → Create instance**.
2. Configuration :
   - **Name** : `paa-osrm`
   - **Image** : `Canonical Ubuntu 22.04` (sélectionner explicitement —
     ne PAS prendre Oracle Linux par défaut)
   - **Shape** : cliquer **Change shape** → onglet **Ampere** →
     `VM.Standard.A1.Flex` avec **4 OCPU + 24 Go RAM** (les valeurs max
     du Free Tier)
   - **Boot volume** : 50 Go (suffit largement)
3. **Networking** → **Assign a public IPv4 address** : OUI (sinon pas
   joignable).
4. **Add SSH keys** → générer ou coller ta clé publique
   (ex. `cat ~/.ssh/id_ed25519.pub`).
5. **Create**. La VM démarre en ~2 min.
6. Noter l'**IP publique** affichée (ex. `141.94.x.x`).

#### Étape 3 — Ouvrir les ports 80 et 443 (3 min)

Par défaut Oracle bloque tout sauf le SSH. Pour servir OSRM en HTTPS via
Caddy :

1. Console Oracle → **Networking → Virtual Cloud Networks** → cliquer
   sur le VCN auto-créé.
2. **Security Lists** → la liste par défaut → **Add Ingress Rules** :
   - Source CIDR `0.0.0.0/0`, IP Protocol **TCP**, Destination port `80`
   - Source CIDR `0.0.0.0/0`, IP Protocol **TCP**, Destination port `443`
3. Sauvegarder.
4. SSH dans la VM puis ouvrir aussi côté iptables (Ubuntu bloque par défaut) :

```bash
ssh ubuntu@141.94.x.x
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

#### Étape 4 — Installer Docker (5 min)

Toujours en SSH dans la VM :

```bash
# Mise à jour
sudo apt update && sudo apt upgrade -y

# Docker (script officiel)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Recharger les groupes (sinon il faut se reconnecter)
newgrp docker

# Vérification
docker run --rm hello-world
```

#### Étape 5 — Télécharger et indexer l'extrait OSM Côte d'Ivoire (10 min)

```bash
# Crée le dossier de travail
mkdir -p ~/osrm-data && cd ~/osrm-data

# Télécharge l'extrait OSM (mis à jour quotidiennement par Geofabrik)
wget https://download.geofabrik.de/africa/ivory-coast-latest.osm.pbf
# → ~50 Mo en moyenne

# Indexation OSRM en 3 étapes (~3-5 min sur 4 vCPU ARM)
# Profil "car" = voiture, exactement ce qu'on veut

docker run --rm -t -v "$PWD:/data" osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/ivory-coast-latest.osm.pbf

docker run --rm -t -v "$PWD:/data" osrm/osrm-backend \
  osrm-partition /data/ivory-coast-latest.osrm

docker run --rm -t -v "$PWD:/data" osrm/osrm-backend \
  osrm-customize /data/ivory-coast-latest.osrm
```

Tu auras à la fin des fichiers `ivory-coast-latest.osrm.*` (~200 Mo).

#### Étape 6 — Lancer OSRM en service Docker persistant

```bash
# OSRM en mode MLD (multi-level Dijkstra), redémarrage automatique
docker run -d --name paa-osrm \
  --restart=always \
  -p 127.0.0.1:5000:5000 \
  -v ~/osrm-data:/data \
  osrm/osrm-backend \
  osrm-routed --algorithm mld --max-table-size 10000 \
    /data/ivory-coast-latest.osrm

# Vérification (depuis la VM elle-même)
curl -s "http://localhost:5000/route/v1/driving/-4.028563,5.328119;-3.98196,5.258705?overview=full" \
  | head -c 300
```

Réponse attendue : un JSON `{"code":"Ok","routes":[…]}` avec une polyline
encodée — c'est OSRM qui répond.

#### Étape 7 — Reverse-proxy HTTPS avec Caddy (10 min)

OSRM ne fait pas HTTPS lui-même. **Caddy auto-TLS** est le plus simple :

**Pré-requis** : un nom de domaine pointant vers l'IP publique. Soit :

- Tu en achètes un (Namecheap, OVH, ~5 €/an)
- Soit tu utilises un domaine gratuit : `osrm-paa.duckdns.org`
  (créer un compte sur <https://www.duckdns.org/>, créer un sous-domaine,
  pointer A → ton IP Oracle)

Une fois le DNS propagé (vérifier avec `dig osrm-paa.duckdns.org` ou
<https://dnschecker.org>) :

```bash
# Installer Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# Configurer Caddy
sudo tee /etc/caddy/Caddyfile <<'EOF'
osrm-paa.duckdns.org {
    reverse_proxy localhost:5000
}
EOF

# Recharger
sudo systemctl reload caddy

# Vérification depuis ta machine Windows
curl https://osrm-paa.duckdns.org/route/v1/driving/-4.028563,5.328119;-3.98196,5.258705?overview=full
```

Caddy s'occupe automatiquement de **Let's Encrypt** (certificat HTTPS gratuit
auto-renouvelé). Aucune config supplémentaire.

#### Étape 8 — Connecter Railway et regénérer les polylines

Sur ta machine Windows :

```powershell
# Pointer Railway sur le nouvel OSRM
railway variables --set "OSRM_BASE_URL=https://osrm-paa.duckdns.org" --service backend

# Redémarrer le service pour qu'il prenne la variable
# (Railway le fait automatiquement après variables set)
```

Puis sur la **Console Railway** du service backend :

```bash
# Écrase les polylines droites par les vraies polylines routières
python -m app.complete_troncons
```

Tu verras 6 lignes `[OK]` avec des polylines de **600 à 1000 caractères**
chacune (au lieu des ~20 caractères du segment droit précédent).

Hard refresh la page Accueil/Carte côté frontend → les 6 tronçons sont
maintenant tracés en suivant les vraies routes : boulevard de Marseille,
pont Houphouët-Boigny, avenue Christiani, autoroute du Nord, etc.

#### Maintenance

- **Renouvellement TLS** : Caddy le fait tout seul, rien à toucher.
- **Mise à jour des données OSM** : re-télécharger l'extrait et rejouer les
  3 commandes osrm-extract / partition / customize tous les 3-6 mois (la
  topologie d'Abidjan évolue lentement). Puis `docker restart paa-osrm`.
- **Supervision** : `docker logs --tail 50 -f paa-osrm` pour les logs OSRM,
  `journalctl -u caddy -f` pour les logs Caddy.
- **Surveillance quota Free Tier** : Console Oracle → menu Tenancy →
  vérifier que la VM reste classée "Always Free Eligible".

#### Bascule de retour vers le mode dégradé

Si OSRM tombe en panne ou n'est plus disponible :

```powershell
# Côté Railway, retirer la variable
railway variables --unset "OSRM_BASE_URL" --service backend
```

Le backend bascule automatiquement en mode best-effort (cf. § 2.5) :
- Les collectes Google continuent normalement
- Les polylines déjà stockées en base restent affichées (pas écrasées)
- L'endpoint P5 `/terrain/import` continue de fonctionner sans `confiance_matching`
- `python -m app.complete_troncons` nécessite OSRM — les polylines déjà en base restent affichées (elles ne sont pas écrasées par la bascule)

---

## 9. Règles pour les assistants IA

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
7. **Avant tout déploiement Railway**, lire `railwaydeploy.md` à la racine du dépôt.
   Ce fichier contient les procédures, pièges connus et la checklist de déploiement.
   Règle critique : **`git add -A` obligatoire avant `railway up`** — les fichiers
   non-trackés sont absents du conteneur.
