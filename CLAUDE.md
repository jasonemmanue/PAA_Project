# FLUIDIS — Contexte permanent du projet

> Ce fichier est le **contrat de contexte** du projet. Tout assistant IA, contributeur ou
> reviewer doit le lire avant d'écrire la moindre ligne de code. Il définit le besoin,
> les contraintes techniques, les conventions et la feuille de route.

> **Renommage produit (2026-07-03)** — le produit s'appelait précédemment
> **PAA-Traverse**, il s'appelle désormais **FLUIDIS**. Le renommage a été
> propagé à tout le code, l'UI, la doc et le prompt système du chatbot. Le
> **répertoire de travail local** et le **repository Git** conservent leur nom
> historique `paa-traverse` (ne pas renommer — cela casserait la config Claude
> Code, Railway CLI et les scripts existants). Le sigle **PAA** seul continue
> de désigner le **client** (Port Autonome d'Abidjan) et reste partout dans
> la doc. Cf. « Phase de renommage » en fin de fichier.

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
| **P4.1** | ✅ Terminée *(amélioré 2026-06-28)* | **Carte Accueil enrichie** — zoom intelligent au chargement vers le **point chaud** (worst classe DEESP puis worst % rouge), **4 markers POI** étiquetés `C`/`T`/`S`/`P`, **panneau latéral scrollable** avec barre couleur 3 segments rouge/orange/vert par tronçon, bandeau KPI à 3 classes DEESP. **Marqueurs début/fin au clic** : cliquer un tronçon dans le panneau affiche un CircleMarker vert (départ) + rouge (arrivée) sur la carte pour ce tronçon uniquement — dispara­ît à la déselection. **Page statique** : `document.body.overflow=hidden` au montage empêche le scroll navigateur ; seul le panneau latéral (`h-[45vh]`/`lg:h-[70vh]` + `overflow-y-auto`) défile. Cf. `CarteLeaflet.tsx` + `PageCarte.tsx` + `PanneauTroncons.tsx`. |
| **P4**| ✅ Terminée | **Frontend Next.js complet** — design system PAA, responsive 3 breakpoints (375/768/1024), i18n FR/EN sans rechargement, thème clair/sombre, splash screen HACKATONIA (laser printing 4 s), favicon multi-tailles, page Carte (Leaflet + WebSocket + heatmap + popups), page Indicateurs (Recharts : courbe + heatmap horaire + évolution pluriannuelle + KPI), sélecteur période fonctionnel **24h / 7j / 30j / 90j** (cf. § 4.1), barre de pilotage avec **pastille 3 états + libellé plage active + prochain cycle** reflétant la veille nocturne automatique (cf. § 4.2), exports CSV/XLSX. |
| **P5**| ✅ Terminée | **Validation terrain hebdomadaire** — `POST /terrain/import` (parsing GPX + OSRM Match + découpage automatique aux bornes des 6 tronçons), appariement avec la mesure Google la plus proche (fenêtre 30 min), `GET /terrain/releves` + `GET /terrain/calibration` (moyenne mobile des écarts). Frontend : page Fiabilité avec import GPX, graphique Recharts d'évolution de ε par tronçon, tableau de calibration coloré 3 niveaux. Script `app/generer_gpx_synthetiques.py` (Option A) produit des GPX placeholder à partir d'OSRM pour valider la boucle sans relevé terrain. Cf. § 4.4. |
| **P6.2** | ✅ Terminée *(refondu 2026-06-24)* | **Page « Temps de traversée par période »** — Google Maps en haut (temps actuel + ce mois + cette semaine, jours-ouvrables/week-ends), confrontation terrain GPX en bas. Cf. § 4.7. |
| **P6.3** | ❌ Retiré du périmètre (2026-06-23) | Module « Heure optimale de départ » supprimé : code, endpoints, UI. La logique restante (temps de traversée) couvre le besoin opérationnel sans le calcul d'approche géocodée. |
| **P6.4** | ⏳ À venir | **Administration + sous-tronçons codifiés** (T1A, T1B, T1C…) comme dans le rapport DEESP. Cf. [§ 6.4](PROMPTS_RESTANTS_DEESP.md). |
| **P6.5** | ⏳ Optionnel | **ML Random Forest** avec évaluation honnête vs prédicteur niveau 2. Cf. [§ 6.5](PROMPTS_RESTANTS_DEESP.md). |
| **P7.1**| ⏳ À venir | **Tests + Cache Redis + Optimisations** — pytest pour rapport_paa, cache /carte/etat et /predire, Lighthouse mobile ≥ 80. Cf. [§ 7.1](PROMPTS_RESTANTS_DEESP.md). |
| **P7.2**| ✅ Terminée (2026-06-28) | **Déploiement Railway du frontend** — service `frontend` créé sur Railway, `NEXT_PUBLIC_API_BASE_URL` configuré, `ALLOWED_ORIGINS` backend mis à jour, déploiement auto sur push `main`. Procédure complète dans `railwaydeploy.md` § « Déploiement du Frontend Next.js sur Railway ». |
| **P7.3**| ⏳ À venir | **Rapport final article 4** + **trame de pitch 5-7 min** revendiquant l'alignement DEESP. Cf. [§ 7.3](PROMPTS_RESTANTS_DEESP.md). |
| **P8.1** | ✅ Terminée | **Scraping incidents — fondations** — migration 0011 table `incidents`, scraper RSS multi-source (Fraternité Matin, Abidjan.net, Koaci), job APScheduler 30 min, endpoints `GET /incidents`, `GET /incidents/stats`. |
| **P8.2** | ✅ Terminée | **NLP légère + géocodage** — extraction lieu/type/sévérité par regex, géocodage Nominatim OSM + fallback Photon, filtre bbox portuaire, attribution `troncon_id` (Haversine 300 m). |
| **P8.3** | ✅ Terminée | **Frontend page Incidents** — `/incidents/page.tsx`, carte Leaflet markers colorés par sévérité, liste chronologique filtrée, 3 KPI, panneau latéral détail, i18n FR/EN, polling 5 min. |
| **P8.4** | ✅ Terminée | **Overlay carte principale** — incidents actifs (< 30 j) affichés en CircleMarkers sur la carte Accueil, badge rouge compteur dans la nav sidebar + drawer mobile, polling stats 5 min. |
| **P8.5** | ✅ Terminée | **Qualité & exports** — migration 0012 `fiabilite_source` (0..1) par source, déduplication cross-sources dans `enrichir_incidents()`, `GET /incidents/export` (CSV 12 colonnes), bouton Exporter CSV dans les filtres. |
| **P9.1** | ✅ Terminée (2026-06-27) | **Chatbot guide — Claude via backend** — endpoint `POST /chatbot/message` + `GET /chatbot/disponibilite`, clé `ANTHROPIC_API_KEY` côté serveur, prompt système professionnel sans markdown. Frontend simplifié : Claude uniquement, plus de sélecteur Gemini. |
| **P9.2** | ✅ Terminée (2026-06-27) | **Fix bug heure-optimale MIN=MOYEN=MAX** — requête `predire.py` corrigée : `min(ProfilHoraire.min)` / `max(ProfilHoraire.max)` + filtre `fenetre_jours=30` pour éviter le triple-comptage des 3 fenêtres. |
| **P10.1** | ✅ Terminée (2026-06-28) | **Authentification 2 niveaux** — `PasswordGate` avant splash, mode lecture (`readhackatonia`) vs lecture/écriture (`readwritehackatonia`), mots de passe stockables dans localStorage. Auth pure React state (clear à chaque refresh/onglet). Hook `useAuth()` cache les boutons d'écriture en mode lecture. Cf. § 12.1. |
| **P10.2** | ✅ Terminée (2026-06-28) | **Refonte portail d'accès** — logo PAA gauche + carte centrale + "HACKATONIA" vertical droit (bleu ciel sky-400) + toggle thème clair/sombre. Layout responsive desktop/mobile. Logo en filigrane sur fond. Thème clair par défaut (`ThemeProvider defaultTheme="light"`). |
| **P10.3** | ✅ Terminée (2026-06-28) | **Vue satellite sur toutes les cartes** — toggle "🛰 Satellite / 🗺 OSM" sur CarteLeaflet, CarteApercu, CarteIncidents. Tuiles ESRI WorldImagery gratuites (URL `{z}/{y}/{x}`). |
| **P10.4** | ✅ Terminée (2026-06-28) | **Export global indicateurs** — boutons "Tout CSV" / "Tout Excel" dans `BarrePilotage` téléchargent séquentiellement les mesures des 6+ tronçons (600 ms d'intervalle). Cf. § 12.4. |
| **P10.5** | ✅ Terminée (2026-06-28) | **Axes et tronçons** — migration **0013** ajoute `troncons.est_axe`. Chaque axe peut être découpé en tronçons codifiés (enfants). Sélecteur Indicateurs en `<optgroup>` séparés (Axes / Tronçons). Chatbot mis à jour. Cf. § 12.5. |
| **P10.6** | ✅ Terminée (2026-06-28) | **PDF Tableau 16 — téléchargement direct** — endpoint `GET /rapport/zones-congestionnees/pdf` génère PDF natif via **fpdf2** (pure Python, léger). Frontend télécharge via fetch + Blob + `<a download>` — pas de popup, pas d'aperçu. Évite jspdf et ses vulnérabilités critiques dompurify. Cf. § 12.6. |
| **P10.7** | ✅ Terminée (2026-06-28) | **Import CSV/Excel évolution pluriannuelle** — endpoint `POST /import/evolution-csv` accepte CSV ou Excel à 7 colonnes (`axe, sens, periode, type_jour, temps_min_s, temps_moyen_s, temps_max_s`). Idempotent (UPSERT par clé). Bouton dans `EvolutionPluriannuelle` (mode écriture). Cf. § 12.7. |
| **P10.8** | ✅ Terminée (2026-06-28) | **Sources scraping incidents configurables** — migration **0014** crée la table `sources_incidents`. CRUD via `/incidents/sources` (GET, POST, PATCH, DELETE). `scraper_toutes_sources()` lit la table en priorité (repli statique). Panneau "⚙ Gérer les sources" sur la page Incidents (mode écriture). Cf. § 12.8. |
| **P10.9** | ✅ Terminée (2026-06-28) | **Navigation réordonnée + filtres incidents simplifiés + accidents/mois** — ordre menu : Accueil → Rapport → Indicateurs → Temps de traversée → Heure opt → Incidents → Fiabilité → Admin. Filtres incidents réduits à Accident / Route barrée / Travaux. BarChart "Accidents par mois" ajouté. "Mn" → "Min" dans rapport. Tri chronologique Oct 2025 avant Fév 2026. |
| **P10.10** | ✅ Terminée (2026-06-29) | **Types d'incidents dynamiques + filtre zone portuaire strict** — migration **0015** convertit `type_incident` de ENUM vers VARCHAR(50) + crée la table `types_incidents` (slug, libelle, regex, actif). CRUD `/incidents/types` (GET/POST/PATCH/DELETE). Scraper : double filtre TYPE + ZONE obligatoires (un article sur « travaux à Yakassé-Feyassé » est écarté). NLP : `classifier_type()` lit les types depuis la DB. Frontend : `FiltresIncidents` charge les types depuis l'API + nouveau panneau `GestionTypes.tsx`. Cf. § 12.10. |
| **P10.11** | ✅ Terminée (2026-06-29) | **UX GestionTypes — mots-clés simples + mise à jour instantanée** — Le formulaire d'ajout de type remplace le champ regex brut par un champ **mots-clés** (virgule comme séparateur) ; la regex est générée automatiquement avec aperçu temps réel. L'état `typesIncidents` est remonté dans `PageIncidents` et partagé entre `FiltresIncidents` (prop `types`) et `GestionTypes` (callback `onTypeChange`) — ajout/suppression/toggle se reflète **instantanément** dans le dropdown du filtre sans rechargement. Type « Autre » (fallback NLP) masqué dans le tableau et dans le filtre — reste en base. Chatbot mis à jour : sait proposer des mots-clés adaptés sur demande. |
| **P10.12** | ✅ Terminée (2026-06-29) | **Évolution pluriannuelle dynamique par tronçon** — Refonte du graphique `EvolutionPluriannuelle` : accepte `tronconId` en prop, affiche les **2 campagnes historiques les plus récentes** (depuis `evolution_indicateur`, filtrées par axe+sens du tronçon sélectionné) + le **mois calendaire courant en cours de collecte** (calculé en temps réel depuis `mesures`, depuis le 1er du mois). Nouveau endpoint `GET /evolution/troncon/{id}`. Auto-refresh 5 min du mois courant. Badge « en cours » sur la barre du mois actif. Oct 2025 disparaît automatiquement dès qu'une 3e campagne historique existe. Tronçons > 6 (sans historique) : seul le mois courant est affiché. |
| **🏁 v1.0.0** | ✅ **Hackathon terminé (2026-06-29)** | Toutes les phases P1 → P10.12 livrées et déployées en production. Backend Railway + Frontend Railway opérationnels 24h/24. |
| **P10.13** | ✅ Terminée (2026-06-29) | **Nettoyage code mort post-hackathon** — suppression du panneau "Mettre à jour les données pluriannuelles" dans `EvolutionPluriannuelle.tsx` (devenu inutile). Suppression du router `/import/*` (`backend/app/api/import_data.py`) : les 3 endpoints `POST /import/base-nettoyee`, `POST /import/evolution`, `POST /import/evolution-csv` n'avaient plus de caller frontend. Les scripts CLI `app/import_evolution.py` et `app/import_base_nettoyee.py` sont conservés. Renommage `NB JO` → `NB MESURES JO` et `NB WE` → `NB MESURES WE` dans `TableauTempsTraversee.tsx`. |
| **P10.14** | ✅ Terminée (2026-06-29) | **Matrice congestion + fix PDF CORS + réordonnancement page DEESP** — Cf. § 13.1 et § 13.2. |
| **P10.15** | ✅ Terminée (2026-06-30) | **Matrice temps de traversée + fix PDF Unicode + navigation 7 jours + import Excel mesures** — Cf. § 13.3. |
| **P10.16** | ✅ Terminée (2026-07-01) | **Évolution pluriannuelle — mois passés reconstruits depuis Google** — dès qu'un mois calendaire complet totalise ≥ 50 mesures Google, il apparaît dans le graphique comme campagne historique. Fenêtre glissante 12 mois. Les imports Excel restent prioritaires en cas de doublon de période. Roulement automatique : Fév 2026 / Juin 2026 / Juil 2026 (en cours) dès le 2026-07-01 pour les 6 axes officiels. Cf. § 4.4.1. |
| **P11.1** | ✅ Terminée (2026-07-01) | **Indicateurs 6 mois / 1 an + suppression heatmap** — 2 nouvelles périodes d'analyse ajoutées (`6mois` = 180 j, `1an` = 365 j). Suppression de la heatmap horaire (composant retiré). Affichage de la valeur minimum sur le graphe courbe journée. Export matrice temps. Cf. § 14.1. |
| **P11.2** | ✅ Terminée (2026-07-01) | **Filtre créneau horaire global** — `PlageHoraireContext` + `SelecteurPlageHoraire` dans la topbar. Filtre `heure_debut` / `heure_fin` propagé sur toutes les pages (Indicateurs, Temps de traversée, Heure optimale, Rapport DEESP, Évolution pluriannuelle). Persistance `localStorage`. Cf. § 14.2. |
| **P11.3** | ✅ Terminée (2026-07-02) | **Fix bouton Appliquer invisible en mode clair** — `bg-paa-blue-600` (couleur inexistante dans la palette Tailwind) remplacé par `bg-paa-navy-700` dans `SelecteurPlageHoraire.tsx`. |
| **P11.4** | ✅ Terminée (2026-07-02) | **Incidents actifs 30 jours** — seuil passé de 6h à 30 jours (720h). Configurable via `INCIDENT_ACTIF_HEURES`. Modifié dans 8 fichiers (config, modèle, API, carte, RAG, chatbot, 2 composants frontend). Cf. § 14.4. |

### 4.1 Sélecteur de période de la page Indicateurs — contrat frontend/backend

Le backend `GET /troncons/{id}/indicateurs?periode=...` accepte le format
`Nj` (`1j`, `7j`, `30j`, `90j`, `180j`, `365j`) — son parseur (`_parse_periode`,
`backend/app/api/troncons.py`) rejette tout autre format avec un **HTTP 400**.

L'UI conserve des étiquettes lisibles, donc
[`getIndicateursTroncon`](frontend/lib/api.ts) **traduit** les codes UI avant
d'appeler l'API. Les **6 boutons** sont fonctionnels :

| Bouton UI | Envoyé au backend | Fenêtre |
|-----------|-------------------|---------|
| `24 h`    | `?periode=1j`     | 1 jour glissant |
| `7 jours` | `?periode=7j`     | 7 jours glissants |
| `30 jours`| `?periode=30j`    | 30 jours glissants |
| `90 jours`| `?periode=90j`    | 90 jours glissants |
| `6 mois`  | `?periode=180j`   | 180 jours glissants |
| `1 an`    | `?periode=365j`   | 365 jours glissants |

Les 2 016 mesures historiques `source='historique_paa_2025'` (P6.1) datent de
février 2025 et restent donc hors fenêtre même à 365 jours — elles
n'apparaissent que dans le **graphique d'évolution
pluriannuelle** qui exploite `evolution_indicateur`, indépendamment du
sélecteur. C'est conforme à la **règle d'or** du § 2.5 : on ne mélange jamais
`historique_paa_2025` avec les mesures `google` temps réel.

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

### 4.2bis Carte principale — améliorations UX (2026-06-28)

#### Marqueurs début/fin au clic sur un tronçon

**Comportement :** cliquer sur un tronçon dans le panneau latéral (`PanneauTroncons.tsx`)
appelle `onSelectionner(id)` → `selectionId` est mis à jour dans `PageCarte.tsx` →
`CarteLeaflet` reçoit `tronconSelectionneId` et réagit dans l'**effet 4**.

**Implémentation (`frontend/components/carte/CarteLeaflet.tsx`)** :

- Deux refs `markerDebutSelRef` et `markerFinSelRef` (`CircleMarker | null`) stockent les
  markers du tronçon actuellement sélectionné.
- À chaque changement de `tronconSelectionneId` : les anciens markers sont retirés
  (`marker.remove()`), puis les nouvelles coordonnées sont lues depuis
  `troncon.lat_origine ?? troncon.geometrie?.lat_origine` (et idem pour destination).
- **Marker départ** : `CircleMarker` vert foncé (`fillColor: "#16a34a"`, radius 11)
  avec tooltip `🟢 Départ : <nom_court>`.
- **Marker arrivée** : `CircleMarker` rouge foncé (`fillColor: "#dc2626"`, radius 11)
  avec tooltip `🔴 Arrivée : <nom_court>`.
- Fonctionne pour **tous** les tronçons — officiels (1-6) et créés via Administration
  (7, 8…) — dès que leurs coordonnées sont renseignées en base.
- La désélection (clic sur un autre tronçon ou navigation) retire automatiquement
  les markers via le cleanup de l'effet.

#### Page statique — seul le panneau défile

**Problème résolu :** la page Carte créait une barre de scroll navigateur car
`topbar + titre + carte (70 vh) + footer > 100 dvh`.

**Solution (`frontend/components/carte/PageCarte.tsx`)** :

```typescript
useEffect(() => {
  const prev = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  return () => { document.body.style.overflow = prev; };
}, []);
```

- `overflow: hidden` est appliqué au `<body>` au montage de la page Carte.
- Il est **automatiquement restauré** à la valeur précédente lors du démontage
  (navigation vers une autre page) — les autres pages défilent normalement.
- Le panneau latéral reçoit `h-[45vh] overflow-y-auto` (mobile) et
  `lg:h-[70vh] overflow-y-auto` (desktop) pour avoir son propre scroll interne.

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

### 4.4.1 Évolution pluriannuelle dynamique par tronçon (P10.12 — 2026-06-29, enrichi P10.16 — 2026-07-01)

**Endpoint :** `GET /evolution/troncon/{id}` — tag Swagger « évolution pluriannuelle »

#### Sources fusionnées (depuis P10.16 — 2026-07-01)

Les campagnes historiques sont désormais construites à partir de **deux sources
fusionnées** :

1. **Import Excel** (`evolution_indicateur` — feuille `SYNTHESE COMPAREE`) —
   autoritatif, disponible pour les 6 axes officiels DEESP.
   `origine="import_excel"`.
2. **Reconstruction depuis les mesures Google** — pour chaque mois calendaire
   **complètement passé** (dans les 12 derniers mois) qui totalise ≥ 50 mesures
   Google non aberrantes, un bloc `historique` est généré automatiquement
   depuis la table `mesures`. `origine="mesures_google"`.

**Règle de priorité :** si un même code période (ex. `fev_2026`) existe dans
les deux sources, l'import Excel gagne (données autoritatives issues du
protocole DEESP). Les mois reconstruits ne s'affichent donc que pour combler
les trous entre deux campagnes ou pour prolonger l'historique après le dernier
import.

**Constantes backend** (`backend/app/api/evolution.py`) :
- `_MIN_MESURES_MOIS_COMPLET = 50` — seuil de mesures Google pour qu'un mois
  passé soit reconstruit.
- `_NB_MOIS_PASSES_A_EXAMINER = 12` — fenêtre glissante des mois candidats à
  la reconstruction.

**Exemple concret (au 2026-07-01)** : avec l'import Excel `oct_2025` et
`fev_2026`, et une collecte Google active depuis mi-juin 2026, les campagnes
retournées par l'endpoint sont :
- `oct_2025` (import Excel)
- `fev_2026` (import Excel)
- `jun_2026` (**reconstruit** — mois complet, terminé le 30 juin)
- `jul_2026` (live — mois courant en cours)

Le frontend applique `slice(-2)` sur les historiques → affiche **Fév 2026,
Juin 2026, Juil 2026 (en cours)**. `Oct 2025` disparaît naturellement
puisqu'il n'est plus dans les 2 plus récents.

**Roulement automatique :** à chaque changement de mois, la roue tourne — le
mois passé le plus récent devient un historique et le plus ancien des deux
sort du graphique. Aucun code ni redéploiement n'est requis. Un cron ou une
tâche périodique n'est pas nécessaire non plus, la reconstruction est
recalculée à chaque appel de l'endpoint (`n_troncons × n_mois × 1 SELECT`,
négligeable en temps CPU/DB).

#### Réponse JSON

```json
{
  "troncon_id": 1,
  "troncon_nom": "CARENA → Pharmacie Palm Beach",
  "a_donnees_historiques": true,
  "a_import_excel": true,
  "campagnes": [
    {
      "periode": "fev_2026",
      "periode_label": "Fév 2026",
      "source": "historique",
      "origine": "import_excel",
      "jours_ouvrables": { "min_mn": 18.2, "moyen_mn": 22.5, "max_mn": 31.0 },
      "week_ends": { "min_mn": 15.0, "moyen_mn": 19.2, "max_mn": 26.0 }
    },
    {
      "periode": "jun_2026",
      "periode_label": "Juin 2026",
      "source": "historique",
      "origine": "mesures_google",
      "debut": "2026-06-01",
      "fin": "2026-06-30",
      "nb_mesures_total": 264,
      "jours_ouvrables": { "min_mn": 18.0, "moyen_mn": 21.5, "max_mn": 28.5, "nb_mesures": 190 },
      "week_ends": { "min_mn": 15.5, "moyen_mn": 17.2, "max_mn": 24.0, "nb_mesures": 74 }
    },
    {
      "periode": "jul_2026",
      "periode_label": "Juil 2026 (en cours)",
      "source": "live",
      "origine": "mesures_google",
      "debut": "2026-07-01",
      "fin": "2026-07-01",
      "nb_mesures_total": 24,
      "jours_ouvrables": { "min_mn": 18.5, "moyen_mn": 21.0, "max_mn": 26.0, "nb_mesures": 24 },
      "week_ends": null
    }
  ]
}
```

#### Mapping tronçon → axe+sens

Pour les 6 axes officiels DEESP (`backend/app/api/evolution.py`,
`_TRONCON_VERS_AXE_SENS`) :

| `troncon_id` | `axe` | `sens` |
|---|---|---|
| 1 | CARENA → Pharmacie Palm Beach | Aller |
| 2 | CARENA → Pharmacie Palm Beach | Retour |
| 3 | Toyota CFAO → Pharmacie Palm Beach | Aller |
| 4 | Toyota CFAO → Pharmacie Palm Beach | Retour |
| 5 | Agence SODECI → Pharmacie Palm Beach | Aller |
| 6 | Agence SODECI → Pharmacie Palm Beach | Retour |
| > 6 | pas d'import Excel — reconstruit uniquement depuis les mesures Google | — |

**Tronçons > 6 (créés via Administration)** : n'ont pas d'entrée dans
`evolution_indicateur`, mais bénéficient désormais de la reconstruction
automatique — dès qu'un mois calendaire complet est collecté, il apparaît
dans le graphique.

#### Comportement frontend

- **Polling** du mois courant toutes les **5 minutes** (`POLLING_MS`).
- `slice(-2)` sur `campagnes.filter(c => c.source === "historique")` — les 2
  plus récents historiques (triés chronologiquement par le backend).
- Ajout du mois courant `source="live"` en dernier → 3 barres au total.
- Badge `● en cours` sous le label de la campagne live.
- Message d'avertissement (fond ambre) si `a_donnees_historiques === false` :
  informe que les mois passés apparaîtront dès qu'un mois calendaire complet
  aura été collecté (≥ 50 mesures).

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
fluidis/
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

#### Internationalisation (état 2026-06-24)

La page est **entièrement traduite FR / EN** via le système i18n existant
(`frontend/lib/i18n.tsx` + `frontend/messages/{fr,en}.json`).

Toutes les chaînes hardcodées ont été remplacées par `t("prediction.*")`.
Les sous-composants (`BlocGpx`, `BlocTypeJour`, `PuceEcart`, `BandeauEcart`,
`BarreConfianceInline`, `BadgeSource`) reçoivent `t` ou `libelleSource` en prop
pour rester réactifs au changement de langue sans rechargement.

`LIBELLE_SOURCE` (libellés des badges source) a été déplacé **à l'intérieur
du composant** pour être recalculé à chaque changement de locale — une constante
de module ne se réévalue pas.

Clés ajoutées sous `"prediction"` dans les deux fichiers de messages :
`tempsReel`, `ceMois`, `cetteSemaine`, `joursOuvrables`, `weekEnds`,
`confrontationTitre`, `confrontationDesc`, `toutesSessionsTitre`, `ceMoisTitre`,
`cetteSemaineTitre`, `aucuneSessionMois`, `aucuneSessionSemaine`, `depuisLe`,
`ecartTitre`, `ecartLabel`, `ecartEgal`, `ecartPlusLong`, `ecartPlusCourt`,
`terrainPlusLong`, `terrainPlusCourt`, `puceEgal`, `sourceGoogle`,
`sourceProfils`, `sourceRef50`, `confiancePct`, `precisionNote`, + libellés
`labelMin/Moyen/Moy/Max`, `uniteMn`, `mesure/mesures`, `session/sessions`.

---

## 8. Déploiement

### 8.1 Architecture cible

| Composant      | Hébergement                         | Justification                                  |
|----------------|-------------------------------------|------------------------------------------------|
| `backend`      | **Railway** (service Docker)        | Plan simple, $PORT injecté, healthcheck natif. |
| `db`           | **Railway plugin PostgreSQL**       | Provisionnement 1-clic, sauvegardes auto.      |
| `redis`        | **Railway plugin Redis**            | Idem.                                          |
| `osrm`         | **Hors Railway** — voir § 8.3       | Image OSRM + extrait OSM (~ 800 Mo) trop lourds pour Railway. |
| `frontend`     | **Railway** service `frontend` (Railpack) | `https://frontend-production-599c.up.railway.app` — déployé le 2026-06-28. |

### 8.2 URLs publiques de production (état au 2026-06-28)

| Service | URL | Statut |
|---------|-----|--------|
| **Backend FastAPI** | `https://backend-production-6cbf.up.railway.app` | ✅ En ligne |
| **Frontend Next.js** | `https://frontend-production-599c.up.railway.app` | ✅ En ligne (déployé 2026-06-28) |
| **Swagger API** | `https://backend-production-6cbf.up.railway.app/docs` | ✅ |

Endpoints critiques backend :
- `GET /health` → `{"status":"ok"}` ✅
- `GET /collecte/status` → scheduler actif, 6 tronçons, 216 req/jour estimées ✅
- `GET /carte/etat` → état des 6 tronçons
- `GET /docs` → Swagger interactif

**Déploiement par terminal** : `railway up --service <nom>` depuis le dossier du service. `git push` seul ne déclenche pas de rebuild Railway de façon fiable — toujours utiliser `railway up`.

### 8.2.1 Points d'attention déploiement Railway

> 📖 La procédure complète, tous les pièges rencontrés (P1 → P7.2) et la
> checklist de déploiement sont dans [`railwaydeploy.md`](railwaydeploy.md) à la racine.

**Règles critiques backend :**

- **`git add -A` + commit obligatoires avant `railway up`** — Railway utilise `git archive` et ignore les fichiers non commités. Symptôme classique : la migration ou le fichier que tu viens de créer est absent du conteneur.
- **`startCommand`** : **ne JAMAIS inclure `alembic upgrade head`** — provoque un `pg_advisory_lock` persistant qui bloque le démarrage 7 minutes puis fait échouer le healthcheck. Lancer les migrations depuis la **Console Railway** après chaque déploiement contenant une nouvelle migration.
- **`${PORT}`** : envelopper le startCommand dans `sh -c '...'` pour que la variable soit interprétée par le shell.
- **`AsyncIOScheduler.start()`** : doit être appelé depuis le contexte async uvicorn (lifespan FastAPI), **pas** depuis `asyncio.to_thread()`.
- **`UploadFile` / `Form`** : exige `python-multipart` dans `requirements.txt`.
- **`numReplicas = 1`** : APScheduler vit en mémoire — toute duplication entraînerait une double collecte.
- **Premier déploiement** : seed via la Console Railway → `python -m app.seed_troncons`.

**Règle critique déploiement — backend ET frontend (découverte le 2026-06-29) :**

- **Les deux services se déploient via `railway up` depuis leur dossier**, PAS via `git push` seul. `git push` peut utiliser le cache Docker et omettre de nouveaux fichiers (migration Alembic, composants) :
```powershell
# Backend
cd backend  &&  railway up --service backend  &&  cd ..
# Frontend
cd frontend  &&  railway up --service frontend  &&  cd ..
```

- **Vérification locale obligatoire avant tout déploiement** : `cd frontend && npm run build` doit réussir localement avant `railway up`.
- **`startCommand = "npx next start -p $PORT"`** dans [frontend/railway.toml](frontend/railway.toml) : le frontend doit lancer Next.js sur le port dynamique fourni par Railway. Aucun port fixe ne doit être codé en dur.
- **`railway up --service frontend` depuis `frontend/`** est la **seule méthode fiable par terminal**. `git push` ne déclenche pas de rebuild Railway.
- **`NEXT_PUBLIC_*` = variables de build-time** — elles doivent être définies dans Railway **avant** le premier build. Ajouter une variable APRÈS le build déjà effectué n'a aucun effet : il faut redéclencher un déploiement complet.
- **Vulnérabilités de sécurité bloquent le build** — Railway scan `package-lock.json`. Si un CVE est détecté, le build échoue avec `SECURITY VULNERABILITIES DETECTED`. Corriger dans `package-lock.json` (via `npm install <package>@<version>`) et pousser le lock file mis à jour.
- **`builder = "RAILPACK"` dans `frontend/railway.toml`** — Railway a remplacé Nixpacks par Railpack. Utiliser `RAILPACK` (majuscules) pour que `railway.toml` soit lu entièrement (y compris `startCommand`).
- **`ALLOWED_ORIGINS` backend** : doit inclure l'URL Railway du frontend. Après chaque changement d'URL frontend, redéployer le backend.
- **Post-déploiement de vérification** : `railway status`, puis `railway logs --service frontend --deployment <id>` pour s'assurer que le service démarre et passe le healthcheck `/`.

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

### 8.5.1 Polylines en production — état au 2026-06-28

> **Situation actuelle :** les polylines réelles OSRM sont **persistées en base
> Railway** et **OSRM est hébergé en permanence** sur Google Cloud e2-micro
> (cf. § 8.8). `OSRM_BASE_URL` est configurée sur Railway → tout nouveau tronçon
> ou sous-tronçon créé via la page Administration obtient **automatiquement** sa
> vraie polyline routière sans commande manuelle.

| Tronçon (id) | Polyline | Route suivie |
|--------------|----------|--------------|
| 1 CARENA → Palm Beach | 940 cars | Bd de Marseille + pont HB |
| 2 Palm Beach → CARENA | 1083 cars | Retour complet |
| 3 Toyota CFAO → Palm Beach | 559 cars | Av. Christiani + port |
| 4 Palm Beach → Toyota CFAO | 569 cars | Retour |
| 5 SODECI → Palm Beach | 578 cars | Zone 4 → port |
| 6 Palm Beach → SODECI | 582 cars | Retour |
| 8 AGL → Grand Moulin | 92 cars | Tracé court |

Ces polylines ont été (re)générées le **2026-06-28** via `python -m app.complete_troncons`
depuis la Console Railway, avec **OSRM Google Cloud e2-micro** (cf. § 8.8) comme source.

**Automatisme à la création (depuis le 2026-06-28) :**

Les endpoints `POST /administration/troncons` et
`POST /administration/troncons/{id}/sous-troncons` appellent OSRM
**directement à la création** si `OSRM_BASE_URL` est configurée
(`backend/app/api/administration.py` lignes 137-154 et 332-359).
Plus besoin de relancer `complete_troncons` pour les nouveaux tronçons.

**`complete_troncons` reste utile pour :**
- Régénérer en masse les polylines de tronçons existants (migration, changement d'OSRM)
- Récupérer après une panne OSRM pendant une création

Tableau récapitulatif des scripts :

| Script | Coords | Polyline | Distance | Nécessite OSRM |
|--------|--------|----------|----------|----------------|
| `seed_troncons` | ❌ NULL | ❌ NULL | distance officielle | ❌ |
| `set_coords_depuis_seed` | ✅ depuis `coordonnees.py` | inchangée | inchangée | ❌ |
| `complete_troncons` | ✅ depuis `coordonnees.py` | ✅ **suivant les routes** | recalculée par OSRM | ✅ |

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

### 8.8 OSRM permanent sur Google Cloud Free Tier e2-micro *(déployé le 2026-06-28)*

> **État actuel :** OSRM tourne en permanence sur une VM Google Cloud e2-micro
> (`us-central1-f`, projet `sgk-home`). `OSRM_BASE_URL=http://<IP>:5000` est
> configuré sur Railway. **Coût : 0 €** (Free Tier permanent).

#### Spécifications de la VM

| Paramètre | Valeur |
|---|---|
| Nom | `paa-osrm` |
| Projet GCP | `sgk-home` |
| Type de machine | `e2-micro` (0.25–2 vCPU, 1 Go RAM) |
| Région / Zone | `us-central1-f` (Iowa) |
| OS | Ubuntu 22.04 LTS Minimal (x86/64) |
| Disque | 30 Go HDD standard |
| IP externe | statique (voir Console GCP) |
| Port ouvert | TCP 5000 (règle pare-feu `osrm-5000`) |

#### Données OSRM indexées

| Fichier source | Version | Taille |
|---|---|---|
| `ivory-coast-latest.osm.pbf` | 2026-06-26 (Geofabrik) | 85 Mo |
| Fichiers indexés (`*.osrm.*`) | MLD algorithm | ~600 Mo dans `~/osrm/data/` |

#### Commandes de maintenance

```bash
# Vérifier que OSRM tourne (depuis SSH ou gcloud)
docker ps | grep paa-osrm

# Tester la réponse OSRM
curl -s "http://localhost:5000/route/v1/driving/-4.028563,5.328119;-3.98196,5.258705?overview=false"

# Voir les logs
docker logs --tail 50 paa-osrm

# Redémarrer si nécessaire (--restart=always le fait automatiquement au boot)
docker restart paa-osrm
```

#### Mise à jour des données OSM (tous les 3-6 mois)

```bash
# SSH dans la VM
cd ~/osrm/data
wget -q --show-progress -O ivory-coast-latest.osm.pbf https://download.geofabrik.de/africa/ivory-coast-latest.osm.pbf

# Ré-indexation (avec swap actif)
docker stop paa-osrm
docker run --rm -v ~/osrm/data:/data osrm/osrm-backend:latest osrm-extract -p /opt/car.lua /data/ivory-coast-latest.osm.pbf
docker run --rm -v ~/osrm/data:/data osrm/osrm-backend:latest osrm-partition /data/ivory-coast-latest.osrm
docker run --rm -v ~/osrm/data:/data osrm/osrm-backend:latest osrm-customize /data/ivory-coast-latest.osrm
docker start paa-osrm
```

> **Note swap :** le e2-micro (1 Go RAM) nécessite un fichier swap de 2 Go pour
> l'indexation OSRM. Le swap est créé une fois et persiste sur le disque :
> `sudo swapon /swapfile` suffit à le réactiver après un redémarrage.
> Ajouter `/swapfile none swap sw 0 0` dans `/etc/fstab` pour l'activation automatique.

#### Connexion SSH depuis Windows (gcloud CLI)

```powershell
# Installer gcloud CLI si absent : https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project sgk-home
gcloud compute ssh paa-osrm --zone=us-central1-f
```

#### Intégration Railway

```powershell
# Variable déjà configurée depuis le 2026-06-28
railway variables set OSRM_BASE_URL=http://<IP_VM>:5000 --service backend

# Régénérer toutes les polylines (depuis Console Railway)
python -m app.complete_troncons
```

#### Automatisme à la création de tronçon/sous-tronçon

Depuis le **2026-06-28**, les endpoints de création appellent OSRM automatiquement :

```python
# backend/app/api/administration.py — creer_troncon (ligne ~137)
if settings.osrm_base_url and not payload.waypoints:
    rep = await osrm.route(origine, destination)  # polyline réelle automatique

# creer_sous_troncon (ligne ~332)
if settings.osrm_base_url:
    rep = await osrm.route(debut, fin)  # idem
```

**`complete_troncons` n'est plus nécessaire pour les nouveaux tronçons.**
Il reste utile uniquement pour régénérer en masse les polylines existantes.

---

## 10. Phase P8 — Module « Incidents & Accidents » (scraping presse ivoirienne)

> Phase ajoutée le **2026-06-24**. Objectif : recenser automatiquement en continu
> les incidents de circulation (accidents, routes barrées, embouteillages
> exceptionnels) signalés dans la zone portuaire d'Abidjan, les géolocaliser et
> les afficher sur une page dédiée ainsi qu'en overlay sur la carte principale.

### 10.1 Périmètre et sources

**Zone géographique surveillée :**
Bounding box de la zone portuaire : lat `[5.24, 5.37]` × lon `[-4.05, -3.96]`.
Un incident est retenu s'il mentionne un lieu géocodable dans cette zone
(Plateau, Treichville, Zone 4, pont Houphouët-Boigny, CARENA, Palm Beach,
Port d'Abidjan, Grand Bassam road, bd de Marseille…).

**Mots-clés de détection :**
`accident`, `collision`, `accrochage`, `carambolage`, `embouteillage`,
`bouchon`, `route barrée`, `voie coupée`, `camion renversé`, `poids lourd`,
`convoi exceptionnel`, `travaux`, `Treichville`, `Plateau`, `Zone 4`,
`Port d'Abidjan`, `CARENA`, `Palm Beach`, `pont HB`, `Houphouët`.

**Sources de scraping (toutes publiques, aucun login requis) :**

| Source | Type | URL de base | Fréquence |
|--------|------|-------------|-----------|
| **Fraternité Matin** | RSS | `https://www.fraternitematin.ci/feed/` | 30 min |
| **Abidjan.net** | RSS + HTML | `https://news.abidjan.net/rss.php` | 30 min |
| **Koaci.com** | RSS | `https://koaci.com/rss.xml` | 30 min |
| **L'Infodrome** | HTML | `https://www.linfodrome.ci/vie-pratique/` | 60 min |
| **Soir Info** | HTML | `https://www.soir-info.ci/` | 60 min |

**Règles de courtoisie :**
- Respecter `robots.txt` de chaque site.
- `User-Agent` identifié : `FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)`.
- Délai de 2 s entre les requêtes vers le même domaine.
- Résultat mis en cache 25 min — ne jamais re-scraper si la dernière collecte
  est < 20 min.

### 10.2 Modèle de données — table `incidents` (migration 0011)

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | int PK | Identifiant interne |
| `titre` | str(500) | Titre extrait de l'article |
| `resume` | text | Corps tronqué (500 premiers caractères nettoyés) |
| `source_url` | str UNIQUE | URL canonique — clé de déduplication |
| `source_nom` | str | `fraternite_matin` / `abidjan_net` / `koaci` / `linfodrome` / `soir_info` |
| `horodatage_publication` | datetime tz | Date de publication (UTC) |
| `horodatage_collecte` | datetime tz | Instant de détection par le scraper (UTC) |
| `lat` | float nullable | Latitude géocodée (Nominatim) |
| `lon` | float nullable | Longitude géocodée (Nominatim) |
| `lieu_extrait` | str nullable | Lieu tel qu'extrait du texte brut |
| `troncon_id` | int FK nullable | Tronçon officiel impacté (si détecté par bbox) |
| `type_incident` | enum | `accident` / `embouteillage` / `route_barree` / `travaux` / `autre` |
| `severite` | enum | `mineur` / `moyen` / `grave` / `inconnu` |
| `actif` | bool | `True` si l'incident est récent (seuil configurable via `INCIDENT_ACTIF_HEURES`, défaut 30 jours) — recalculé à chaque lecture |
| `verifie` | bool | `False` par défaut — validation manuelle optionnelle |

**Index :**
- `ix_incidents_horodatage (horodatage_publication DESC)` — tri chronologique
- `ix_incidents_actif (actif, horodatage_publication)` — filtre carte temps réel
- `ix_incidents_troncon (troncon_id, horodatage_publication)` — corrélation tronçon

### 10.3 Architecture backend

```
backend/app/
├── sources/
│   ├── scraper_incidents.py   # Orchestrateur multi-source
│   ├── parsers/
│   │   ├── rss_parser.py      # Lecture feedparser + filtre mots-clés
│   │   └── html_parser.py     # BeautifulSoup4 pour les sites sans RSS
├── analyse/
│   └── incidents_nlp.py       # Extraction lieu, type, sévérité
├── api/
│   └── incidents.py           # Router FastAPI /incidents
└── models/models.py           # Modèle SQLAlchemy Incident (ajout)
```

**Dépendances supplémentaires (`requirements.txt`) :**
```
feedparser>=6.0
beautifulsoup4>=4.12
lxml>=5.0        # parser HTML rapide pour BeautifulSoup
```

Pas de dépendance NLP lourde (pas de spaCy) — extraction par regex + dictionnaire
de lieux.

**Géocodage : Nominatim OSM**
```python
# Via httpx (déjà en dépendance)
GET https://nominatim.openstreetmap.org/search
  ?q=<lieu_extrait>+Abidjan
  &format=json&limit=1&countrycodes=ci
```
Mise en cache en mémoire (`dict`) : un lieu géocodé n'est pas requêté deux fois.
Délai Nominatim : 1 s entre appels (respect ToS OSM).
Résultat filtré dans la bounding box portuaire — si hors zone, `lat/lon = NULL`.

### 10.4 Feuille de route P8 détaillée

| Sous-phase | Statut | Intitulé |
|------------|--------|----------|
| **P8.1** | ✅ Terminée | **Fondations scraping** — migration 0011, modèle `Incident`, scraper RSS multi-source, job APScheduler 30 min, endpoint `GET /incidents` |
| **P8.2** | ✅ Terminée | **Extraction NLP légère + géocodage** — regex mots-clés, dictionnaire de lieux, Nominatim + fallback Photon, filtre bbox, attribution `troncon_id` |
| **P8.3** | ✅ Terminée | **Frontend page Incidents** — `/incidents/page.tsx`, carte Leaflet markers colorés par sévérité, liste chronologique, filtres type/période/tronçon, i18n FR/EN |
| **P8.4** | ✅ Terminée | **Overlay carte principale** — incidents actifs (< 30 j) affichés sur la carte Accueil, popup résumé, badge rouge compteur dans nav sidebar + drawer mobile |
| **P8.5** | ✅ Terminée | **Qualité & exports** — migration 0012 `fiabilite_source`, déduplication cross-sources dans `enrichir_incidents()`, `GET /incidents/export` CSV, bouton Exporter CSV dans les filtres |

### 10.4bis État final P8 — livré le 2026-06-24

#### Architecture backend P8

```
backend/app/
├── sources/parsers/
│   └── rss_parser.py          # Scraper RSS 3 sources, cache 20 min, User-Agent PAA
├── analyse/
│   └── incidents_nlp.py       # extraire_lieu() + classifier_type/severite() + geocoder_lieu()
│                              # enrichir_incidents() + _dedupliquer_incidents() (P8.5)
├── api/
│   └── incidents.py           # GET /incidents, /stats, /export, /{id}
│                              # POST /scraper-now, /enrichir
└── models/models.py           # Incident, TypeIncident, SeveriteIncident
```

#### Migrations liées à P8

| Migration | Table | Changement |
|-----------|-------|-----------|
| 0011 | `incidents` | Création complète (15 colonnes, 2 enums PL/pgSQL idempotents) |
| 0012 | `incidents` | Colonne `fiabilite_source` float nullable + init CASE WHEN par source |

**Commande Railway Console (à relancer si rollback nécessaire) :**
```bash
alembic upgrade head
```

#### Scores de fiabilité par source (P8.5)

| Source | `source_nom` | Score |
|--------|--------------|-------|
| Fraternité Matin | `fraternite_matin` | 0.90 |
| Abidjan.net | `abidjan_net` | 0.80 |
| Koaci | `koaci` | 0.75 |
| L'Infodrome | `linfodrome` | 0.70 |
| Soir Info | `soir_info` | 0.70 |
| Autre | (toute autre valeur) | 0.50 |

#### Déduplication cross-sources (P8.5)

La fonction `_dedupliquer_incidents()` (appelée automatiquement après chaque `enrichir_incidents()`)
marque les doublons probables selon 3 critères cumulatifs :

1. Même `troncon_id` ET même `type_incident`
2. `horodatage_publication` à ±2h
3. ≥ 3 mots de plus de 3 lettres en commun dans les titres

Le plus ancien est conservé. Les doublons reçoivent le préfixe `[DOUBLON]` sur le titre et
`type_incident='autre'` (signale le changement sans supprimer la ligne).

#### Export CSV (P8.5)

`GET /incidents/export?periode=7j&type_incident=accident&troncon_id=1`

**Colonnes** : `id`, `titre`, `source_nom`, `type_incident`, `severite`, `lieu_extrait`,
`lat`, `lon`, `troncon_nom`, `horodatage_publication`, `actif`, `fiabilite_source`

**Header** : `Content-Disposition: attachment; filename="incidents_paa_YYYYMMDD.csv"`

Le bouton **Exporter CSV** dans `FiltresIncidents.tsx` génère l'URL avec les filtres actifs
(période, type, tronçon) via un `<a href=... download>` natif — aucun JavaScript supplémentaire.

#### Bounding box portuaire (filtre géocodage)

```python
_BBOX_LAT_MIN, _BBOX_LAT_MAX = 5.24, 5.37
_BBOX_LON_MIN, _BBOX_LON_MAX = -4.05, -3.96
```
Un point géocodé hors de cette zone → `lat/lon = NULL`, troncon_id non attribué.

#### Règles de courtoisie scraping

- `User-Agent: FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)`
- Cache 20 min par source (`_CACHE_TTL = 20 * 60`)
- Délai 2 s entre requêtes vers le même domaine
- Délai 1,2 s entre appels Nominatim (respect ToS OSM 1 req/s)
- Cache mémoire Nominatim : un lieu géocodé n'est pas requêté deux fois

---

### 10.5 Prompts d'implémentation P8

> Exécuter dans l'ordre P8.1 → P8.2 → P8.3 → P8.4 → P8.5 (optionnel).
> Chaque prompt suppose que le précédent a été exécuté et commité.

---

#### PROMPT P8.1 — Fondations scraping backend

```
Contexte : FLUIDIS, backend FastAPI + SQLAlchemy + APScheduler.
Voir CLAUDE.md § 10 pour le cahier des charges complet.

Objectif : créer la couche de persistance + le scraper RSS multi-source
+ le job APScheduler + les endpoints de lecture.

ÉTAPE 1 — Migration Alembic 0011 (fichier backend/alembic/versions/0011_incidents.py)
Créer la table `incidents` avec les colonnes définies en § 10.2.
Enum Python `TypeIncident` (accident/embouteillage/route_barree/travaux/autre)
et `SeveriteIncident` (mineur/moyen/grave/inconnu).
Clé unique : source_url. Index : horodatage, actif+horodatage, troncon_id+horodatage.

ÉTAPE 2 — Modèle SQLAlchemy (ajouter dans backend/app/models/models.py)
Classe `Incident` avec tous les champs de la migration.
Propriété calculée `actif` : True si l'incident est récent (seuil configurable, défaut 30 jours).

ÉTAPE 3 — Scraper RSS (backend/app/sources/parsers/rss_parser.py)
Fonction async `scraper_rss(url: str, source_nom: str, db: Session) -> int`
(retourne le nb d'incidents insérés).
- Utilise `feedparser` pour parser le feed.
- Pour chaque entrée : titre + résumé (summary[:500]) + lien + date.
- Filtre : au moins 1 mot-clé de MOTS_CLES_INCIDENTS dans (titre + résumé).
- Déduplication : `INSERT ... ON CONFLICT (source_url) DO NOTHING`.
- User-Agent : "FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)".
- Délai 2 s entre sources du même domaine.

MOTS_CLES_INCIDENTS = [
  "accident", "collision", "accrochage", "carambolage",
  "embouteillage", "bouchon", "route barrée", "voie coupée",
  "camion renversé", "poids lourd", "convoi exceptionnel",
  "travaux", "Treichville", "Plateau", "Zone 4",
  "Port d'Abidjan", "CARENA", "Palm Beach", "pont HB",
  "Houphouët", "pont Félix", "Seamen"
]

SOURCES_RSS = [
  {"url": "https://www.fraternitematin.ci/feed/",    "nom": "fraternite_matin"},
  {"url": "https://news.abidjan.net/rss.php",         "nom": "abidjan_net"},
  {"url": "https://koaci.com/rss.xml",                "nom": "koaci"},
]

ÉTAPE 4 — Job APScheduler (ajouter dans backend/app/collecte/scheduler.py)
Nouveau job `collecte_incidents()` — CronTrigger toutes les 30 min, 24h/24.
Appelle `scraper_rss()` pour chaque source RSS. Log le nombre d'insérés.
Ne lève pas d'exception si une source est indisponible (log + continue).

ÉTAPE 5 — Router FastAPI (backend/app/api/incidents.py)
Tag Swagger : "incidents"

GET /incidents
  Paramètres : actif_seulement: bool = False, troncon_id: int = None,
               type_incident: str = None, limit: int = 50, offset: int = 0
  Retourne : liste paginée {total, items: [IncidentOut]}

GET /incidents/{id}
  Retourne : IncidentOut complet

GET /incidents/stats
  Retourne : {nb_total, nb_actifs, nb_par_type, nb_par_source,
              derniere_collecte}

IncidentOut Pydantic :
  id, titre, resume, source_url, source_nom, horodatage_publication,
  horodatage_collecte, lat, lon, lieu_extrait, troncon_id,
  type_incident, severite, actif, verifie

ÉTAPE 6 — Intégrer le router dans backend/app/main.py
  from app.api import incidents as incidents_router
  app.include_router(incidents_router.router)

ÉTAPE 7 — Ajouter feedparser + beautifulsoup4 + lxml dans requirements.txt

Conventions :
- Commentaires en français
- Noms de variables en français (sauf noms d'API)
- Pas de valeur inventée : si le scraping échoue → trou de collecte, log WARNING
- Aucune clé API — Nominatim est gratuit sans clé
```

---

#### PROMPT P8.2 — Extraction NLP légère + géocodage

```
Contexte : P8.1 terminée — la table incidents est alimentée par le scraper RSS.
Les incidents n'ont pas encore de lat/lon ni de type/sévérité classifiés.
Voir CLAUDE.md § 10.2 et § 10.3.

Objectif : ajouter l'extraction de lieu, la classification du type d'incident
et de la sévérité, puis le géocodage Nominatim.

ÉTAPE 1 — Module NLP (backend/app/analyse/incidents_nlp.py)

Fonction `extraire_lieu(texte: str) -> str | None`
- Dictionnaire ordonné de lieux de référence (du plus spécifique au plus général) :
  LIEUX_ABIDJAN = {
    "carena": "CARENA", "palm beach": "Palm Beach",
    "pont houphouët": "Pont Houphouët-Boigny",
    "pont félix": "Pont Houphouët-Boigny",
    "seamen": "Seamen's Club", "treichville": "Treichville",
    "plateau": "Plateau", "zone 4": "Zone 4", "sodeci": "Zone 4",
    "toyota cfao": "Toyota CFAO", "grand moulin": "Grand Moulin",
    "port d'abidjan": "Port d'Abidjan",
    "bd de marseille": "Boulevard de Marseille",
    "avenue christiani": "Avenue Christiani",
    "pharmacie palm beach": "Palm Beach",
    "pharmacie du port": "Port d'Abidjan",
  }
- Retourne le premier lieu trouvé (insensible à la casse) dans `texte`.

Fonction `classifier_type(texte: str) -> TypeIncident`
- Règles regex simples :
  - r"accident|collision|accrochage|carambolage" → accident
  - r"travaux|chantier|réfection" → travaux
  - r"route barr|voie coup|bloquée?" → route_barree
  - r"embouteillage|bouchon|ralentissement" → embouteillage
  - sinon → autre

Fonction `classifier_severite(texte: str) -> SeveriteIncident`
- r"mort|décès|tué|grave|grièvement" → grave
- r"blessé|hospitalisé|ambulance" → moyen
- r"léger|mineur|accrochage" → mineur
- sinon → inconnu

Fonction async `geocoder_lieu(lieu: str, cache: dict) -> tuple[float, float] | None`
- Cache `dict` en mémoire (clé = lieu normalisé).
- Appel httpx vers Nominatim OSM avec timeout 5 s.
- Filtre résultat dans la bbox [5.24, 5.37] × [-4.05, -3.96].
- Retourne (lat, lon) ou None si hors zone ou erreur.
- Délai 1 s avant chaque appel non-caché (respect ToS OSM).

Fonction async `enrichir_incidents(db: Session) -> int`
- Sélectionne les `Incident` où `lieu_extrait IS NULL` ou `lat IS NULL`.
- Pour chacun : appelle extraire_lieu(), classifier_type(), classifier_severite().
- Si lieu extrait → geocoder_lieu().
- Attribue `troncon_id` si le point (lat, lon) est à < 300 m d'une extrémité
  de tronçon (Haversine sur les coords de la table `troncons`).
- Commit par batch de 20 incidents.
- Retourne le nombre d'incidents enrichis.

ÉTAPE 2 — Chaîne dans le scheduler
Dans `collecte_incidents()` du scheduler, appeler `enrichir_incidents(db)`
après les scrapers RSS — même transaction de 30 min.

ÉTAPE 3 — Endpoint de déclenchement manuel
POST /incidents/enrichir
  Déclenche `enrichir_incidents()` en tâche de fond (BackgroundTasks FastAPI).
  Retourne : {"message": "enrichissement lancé en arrière-plan"}
  Sécurisé par le header X-API-Key (même mécanisme que /collecte/demarrer).

Conventions : idem P8.1.
```

---

#### PROMPT P8.3 — Frontend page Incidents

```
Contexte : P8.2 terminée — GET /incidents renvoie des incidents géolocalisés.
Voir CLAUDE.md § 10.3, la pile technique (Next.js 14, Leaflet, Tailwind, i18n).

Objectif : créer la page /incidents avec une carte Leaflet des incidents actifs
et une liste chronologique filtrable.

STRUCTURE DE LA PAGE (frontend/app/incidents/page.tsx) :
- Titre + sous-titre (i18n)
- 3 KPI compacts : nb incidents actifs | nb total aujourd'hui | tronçon le plus impacté
- `<CarteIncidents>` : carte Leaflet pleine largeur avec markers incidents
- `<FiltresIncidents>` : barre de filtres (type / période / tronçon)
- `<ListeIncidents>` : liste chronologique, 20 incidents par page

COMPOSANT CarteIncidents (frontend/components/incidents/CarteIncidents.tsx) :
- Markers couleurs : rouge = grave, orange = moyen, jaune = mineur, gris = inconnu
- Marker actif = opaque, marker ancien (>30j) = semi-transparent
- Popup au clic : titre, résumé (150 chars), source, heure de publication,
  tronçon impacté si renseigné
- Cluster automatique si > 10 markers visibles (leaflet.markercluster)
- Rafraîchissement toutes les 5 min via polling GET /incidents?actif_seulement=true

COMPOSANT ListeIncidents (frontend/components/incidents/ListeIncidents.tsx) :
- Chaque ligne : badge type coloré | titre | source | heure relative (ex. "il y a 2h")
- Ligne cliquable → ouvre un panneau latéral avec le résumé complet + lien source
- Pagination simple (précédent / suivant)

COMPOSANT FiltresIncidents :
- Dropdown type : Tous / Accident / Embouteillage / Route barrée / Travaux / Autre
- Dropdown période : Aujourd'hui / 24h / 7 jours
- Dropdown tronçon : Tous / liste des 6 tronçons

I18N — Ajouter sous la clé "incidents" dans fr.json ET en.json :
FR : titre="Incidents & Accidents", subtitle="Recensement automatique des incidents
signalés dans la zone portuaire (presse ivoirienne).",
nbActifs="incidents actifs", nbAujourdhui="incidents aujourd'hui",
tronconImpacte="tronçon le plus impacté", aucunIncident="Aucun incident recensé
sur cette période.", voirSource="Voir l'article source",
typeAccident="Accident", typeEmbouteillage="Embouteillage",
typeRouteBarree="Route barrée", typeTravaux="Travaux", typeAutre="Autre",
severiteGrave="Grave", severiteMoyen="Modéré", severiteMineur="Mineur",
severiteInconnu="Inconnu", filtreType="Type", filtrePeriode="Période",
filtreTroncon="Tronçon", periodAujourd="Aujourd'hui", period24h="24 h",
period7j="7 jours"

EN : title="Incidents & Accidents", subtitle="Automatic monitoring of incidents
reported in the port area (Ivorian press).",
nbActifs="active incidents", nbAujourdhui="incidents today",
tronconImpacte="most impacted segment", aucunIncident="No incident recorded
for this period.", voirSource="View source article",
typeAccident="Accident", typeEmbouteillage="Traffic jam",
typeRouteBarree="Road closed", typeTravaux="Roadworks", typeAutre="Other",
... (pattern identique)

NAVIGATION — Ajouter "incidents" dans :
- frontend/messages/fr.json nav.incidents = "Incidents"
- frontend/messages/en.json nav.incidents = "Incidents"
- frontend/components/layout/Navigation.tsx : nouveau lien /incidents

Design : respecter le design system PAA (paa-card, couleurs Tailwind existantes).
Badge rouge "ACTIF" clignotant si incident grave actif. Responsive 3 breakpoints.
```

---

#### PROMPT P8.4 — Overlay incidents sur la carte principale

```
Contexte : P8.3 terminée — la page /incidents fonctionne.
Voir CLAUDE.md § 4.8 pour la structure de CarteLeaflet.tsx.

Objectif : afficher les incidents actifs (<30j) en overlay sur la carte principale
(page Accueil) et ajouter un badge rouge dans la nav si un incident actif existe.

ÉTAPE 1 — Enrichir GET /carte/etat (backend/app/api/carte.py)
Ajouter un champ `incidents_actifs: list[IncidentCarte]` dans la réponse JSON.
IncidentCarte : {id, lat, lon, titre, type_incident, severite, troncon_id,
horodatage_publication (ISO)}
Filtrer : actif=True, lat IS NOT NULL (seulement les géolocalisés).
Limiter à 20 incidents max (les plus récents).

ÉTAPE 2 — Afficher dans CarteLeaflet.tsx
(frontend/components/carte/CarteLeaflet.tsx)
- Si `etat.incidents_actifs` existe et non vide :
  - Afficher un CircleMarker par incident (rayon 10, couleur rouge si grave /
    orange si moyen / jaune si mineur).
  - Popup : titre + type + heure relative.
  - Ne pas mélanger avec les markers POI existants (zIndexOffset différent).
- Si aucun incident actif → aucun marker incident (comportement silencieux).

ÉTAPE 3 — Badge nav
Dans le composant Navigation :
- `GET /incidents/stats` au montage (polling 5 min).
- Si `nb_actifs > 0` : afficher un badge rouge `nb_actifs` à côté du lien Incidents.
- Badge disparaît si `nb_actifs = 0`.

Conventions : idem P8.1. TypeScript strict, aucun `any`. Commentaires en français.
```

---

#### PROMPT P8.5 — Qualité & exports (optionnel)

```
Contexte : P8.4 terminée — incidents affichés sur la carte et la page dédiée.

Objectif : améliorer la qualité des données + ajouter un export CSV.

ÉTAPE 1 — Déduplication cross-sources
Dans `enrichir_incidents()` (backend/app/analyse/incidents_nlp.py) :
Après insertion, détecter les doublons probables :
- Même `troncon_id` + même `type_incident` + même `horodatage_publication` (±2h)
  + au moins 3 mots en commun dans les titres → doublon probable.
- Conserver le plus ancien (premier arrivé), marquer les autres
  `actif=False` + `type_incident='autre'` + titre préfixé "[DOUBLON] ".

ÉTAPE 2 — Score de fiabilité de la source
Ajouter colonne `fiabilite_source` (float 0..1) dans `incidents` (migration 0012).
Initialiser par source :
  fraternite_matin=0.9, abidjan_net=0.8, koaci=0.75,
  linfodrome=0.7, soir_info=0.7.
Exposer dans IncidentOut.

ÉTAPE 3 — Export CSV
GET /incidents/export?format=csv&periode=7j
Retourne un CSV avec colonnes :
  id, titre, source_nom, type_incident, severite, lieu_extrait,
  lat, lon, troncon_nom, horodatage_publication, actif
Header HTTP : Content-Disposition: attachment; filename="incidents_paa_YYYYMMDD.csv"

ÉTAPE 4 — Bouton export dans le frontend
Bouton "Exporter CSV" dans FiltresIncidents (respectant les filtres actifs).
Appelle GET /incidents/export avec les mêmes paramètres de filtre.
```

---

## 11. Phase P9 — Chatbot guide intégré (Claude via backend)

> Phase livrée le **2026-06-27**.

### 11.1 Architecture

Le chatbot est accessible via le bouton flottant **Aide** (coin bas-droit de toutes les pages).
Il utilise exclusivement l'API Claude (Anthropic) via un relais backend — la clé API ne
transite jamais dans le navigateur.

```
Navigateur (ChatbotButton.tsx)
  └── POST /chatbot/message  →  backend FastAPI  →  api.anthropic.com
                                 (ANTHROPIC_API_KEY côté serveur)
```

### 11.2 Backend — `backend/app/api/chatbot.py`

| Endpoint | Méthode | Rôle |
|---|---|---|
| `/chatbot/message` | POST | Envoie une question à Claude et retourne la réponse |
| `/chatbot/disponibilite` | GET | Indique si `ANTHROPIC_API_KEY` est configurée (`{"claude_disponible": true/false}`) |

**Modèle Claude utilisé :** `claude-sonnet-4-6`

**Schéma de la requête :**
```json
{
  "historique": [{"role": "user"|"assistant", "texte": "..."}],
  "question": "texte de la question (max 2000 caractères)"
}
```

**Schéma de la réponse :**
```json
{
  "reponse": "texte de la réponse de Claude",
  "modele": "claude-sonnet-4-6"
}
```

**Gestion des erreurs :**
- `503` si `ANTHROPIC_API_KEY` absente du serveur
- `502` si l'API Claude est injoignable ou renvoie une erreur HTTP

### 11.3 Prompt système — style professionnel

Le prompt interdit explicitement tout markdown (`#`, `*`, `-`, backticks) et impose
une rédaction en prose fluide avec paragraphes. Structure recommandée pour les réponses
longues : phrase introductive en MAJUSCULES suivie d'un point, puis le texte.

**Mise à jour 2026-06-27** : le prompt a été enrichi pour documenter avec précision
le rôle de chaque page, en utilisant les libellés exacts du menu de navigation
(`nav.*.labelKey` issus de `frontend/messages/fr.json`). Les libellés vérifiés sont :

| Page | Libellé menu exact | Route |
|------|--------------------|-------|
| Carte | `Accueil / Carte` | `/` |
| Indicateurs | `Indicateurs` | `/indicateurs` |
| Rapport DEESP | `Rapport DEESP` | `/rapport` |
| Fiabilité | `Fiabilité` | `/fiabilite` |
| Temps de traversée | `Temps de traversée` | `/prediction` |
| Heure optimale | `Heure optimale` | `/heure-optimale` |
| Incidents | `Incidents` | `/incidents` |
| Administration | `Administration` | `/administration` |

Le prompt couvre pour chaque page :
- Le libellé exact du menu et la route Next.js correspondante
- Le rôle opérationnel précis (quelle question répond cette page ?)
- Les interactions clés (filtres, exports, imports, tableaux)
- Des exemples concrets tirés du quotidien portuaire

Il couvre aussi :
- Les 3 axes surveillés et les 6 tronçons avec distances et temps de référence
- La méthode de collecte (Google Routes, 1 mesure/heure, 24h/24)
- Le critère de congestion DEESP (couleurs Google Maps : rouge / orange ≥ 50 %)
- 4 conseils opérationnels clés (planification convois, rapport mensuel,
  analyse durée, calibration GPX)

**Règle de maintenance** : si un libellé de menu est modifié dans
`frontend/messages/fr.json` ou si une page est ajoutée/supprimée dans
`frontend/components/layout/NavItems.tsx`, mettre à jour `SYSTEM_PROMPT`
dans `backend/app/api/chatbot.py` en conséquence.

### 11.3bis RAG — Retrieval-Augmented Generation (ajouté le 2026-06-27)

Le chatbot injecte automatiquement les données réelles de la base avant chaque
question nécessitant des chiffres. Le flux complet :

```
Question utilisateur
      ↓
backend/app/rag/contexte.py → detecter_intentions(question)
      ↓ (si intention détectée)
Requête DB directe (pas d'appel HTTP interne)
      ↓
Bloc texte "DONNÉES RÉELLES DE L'APPLICATION" injecté en tête du message
      ↓
Claude reçoit : contexte_rag + "\n\nQuestion de l'utilisateur : ..."
      ↓
Réponse basée sur les vraies valeurs temps réel
```

#### Intentions détectées et données injectées

| Intention | Mots-clés déclencheurs | Données injectées |
|-----------|------------------------|-------------------|
| `etat_trafic` | trafic, congestion, état, actuel, carte, fluide… | Dernière mesure < 2h par tronçon : état DEESP, % rouge/orange/vert, durée vs référence |
| `temps_traversee` | temps, durée, combien, traversée, minutes… | Dernière mesure < 90 min par tronçon avec écart % vs référence 50 km/h |
| `heure_optimale` | heure, quand, optimal, livrer, créneau, partir… | Top-3 créneaux les plus rapides (7h-19h) pour le type de jour actuel (ouvrable/week-end), basé sur `profils_horaires` 30 jours |
| `incidents` | incident, accident, route barrée, travaux… | Incidents actifs (< 30 j) dans la zone portuaire avec sévérité, lieu, source et âge |
| `statistiques` | statistique, indicateur, analyse, taux, semaine… | Min/moy/max + taux de congestion de la semaine en cours par tronçon |

**Règle anti-duplication** : si `etat_trafic` est détecté, `temps_traversee`
n'est pas ajouté en doublon (l'état inclut déjà les durées).

**Aucun appel HTTP interne** : les récupérateurs interrogent directement la
`Session` SQLAlchemy pour éviter la latence et les problèmes de routage interne.

#### Fichiers du module RAG

```
backend/app/rag/
  __init__.py       # marqueur de package
  contexte.py       # detecter_intentions() + 5 récupérateurs + construire_contexte_rag()
```

#### Fonctions exportées par `contexte.py`

| Fonction | Rôle |
|---|---|
| `detecter_intentions(question)` | Retourne un `set[str]` d'intentions par correspondance mots-clés |
| `recuperer_etat_trafic(db)` | État DEESP + couleurs Google + durée de chaque tronçon |
| `recuperer_temps_traversee(db)` | Durée actuelle + écart vs référence |
| `recuperer_heure_optimale(db)` | Top-3 créneaux par tronçon pour le type de jour courant |
| `recuperer_incidents_actifs(db)` | Incidents actifs (< 30 j) avec sévérité et source |
| `recuperer_statistiques_semaine(db)` | Min/moy/max + taux congestion depuis lundi |
| `construire_contexte_rag(question, db)` | Point d'entrée : détecte + assemble + retourne le bloc texte |

#### Modification de `POST /chatbot/message`

La signature de l'endpoint reçoit maintenant `db: Session = Depends(get_db)`.
Le contexte RAG est construit avant la construction des messages Anthropic :

```python
contexte_rag = await construire_contexte_rag(requete.question, db)
if contexte_rag:
    question_enrichie = f"{contexte_rag}\n\nQuestion de l'utilisateur : {requete.question}"
else:
    question_enrichie = requete.question
```

Le log `INFO "RAG activé pour la question"` est émis quand le contexte est injecté
(utile pour vérifier dans les logs Railway que le RAG se déclenche correctement).

### 11.4 Frontend — `frontend/components/chatbot/ChatbotButton.tsx`

- Bouton flottant fixe en bas à droite (`z-[1200]`) sur toutes les pages
- Fenêtre de chat : 70 vh max, largeur fluide `clamp(300px, 90vw, 420px)`
- 4 questions suggérées au démarrage (clic → remplit le champ de saisie)
- Envoi par `Enter` (sans Shift) ou clic sur le bouton
- Indicateur de frappe animé (`…`) pendant l'appel Claude
- Erreur affichée en rouge avec le détail renvoyé par le backend
- Historique de conversation conservé en mémoire (réinitialisé à la fermeture)

### 11.5 Variable d'environnement requise

| Variable | Côté | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | Backend Railway | Clé API Anthropic — **ne jamais exposer côté frontend** |

Injection Railway :
```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-... --service backend
```

La clé est lue au démarrage via `pydantic-settings` (`app/core/config.py`).
Un redémarrage du service est nécessaire après injection.

### 11.6 Fix bug heure optimale — MIN = MOYEN = MAX (P9.2)

**Problème :** dans `GET /predire/heure-optimale`, la requête SQL utilisait
`func.avg(ProfilHoraire.min)` et `func.avg(ProfilHoraire.max)`. En moyennant
les minimums et maximums sur 5 jours ouvrables × 3 fenêtres (30/60/90 j) = 15 lignes,
les valeurs convergeaient vers la moyenne → MIN = MOYEN = MAX dans le tableau.

**Correction appliquée (`backend/app/api/predire.py`) :**
```python
# Avant (bug)
func.avg(ProfilHoraire.min).label("p_min"),
func.avg(ProfilHoraire.max).label("p_max"),

# Après (correct)
func.min(ProfilHoraire.min).label("p_min"),   # vrai minimum global
func.max(ProfilHoraire.max).label("p_max"),   # vrai maximum global
# + filtre ProfilHoraire.fenetre_jours == 30  (évite le triple-comptage)
```

**Résultat :** les créneaux affichent maintenant des bornes réelles, par exemple
`07h-08h → min 22.9 min / moyen 23.6 min / max 24.4 min`.

---

## 13. Phase P10.15 — Matrice temps + fix PDF Unicode + navigation 7 jours (2026-06-30)

### 13.1 Fix `FPDFUnicodeEncodingException` — PDF Tableau 16

**Problème :** l'endpoint `GET /rapport/zones-congestionnees/pdf` levait une
`FPDFUnicodeEncodingException` car les noms de tronçons contiennent `→`
(ex. `CARENA (Plateau) → Pharmacie Palm Beach`). fpdf2 avec la police Helvetica
n'accepte que le jeu de caractères Latin-1 (ISO 8859-1).

**Solution (`backend/app/api/rapport.py`) :** ajout d'une fonction helper
`_sanitize_pdf(texte: str) -> str` qui :

1. Remplace explicitement les caractères Unicode courants par leurs équivalents ASCII :
   `→` → `->`, `←` → `<-`, `≥` → `>=`, `≤` → `<=`, `×` → `x`, `–`/`—` → `-`, etc.
2. Encode en Latin-1 avec `errors="replace"` pour neutraliser tout résidu.
3. Applique cette transformation à **toutes** les chaînes dynamiques avant `pdf.cell()` :
   `c.troncon_nom`, `sous_troncon_nom`, `repartition`.

```python
def _sanitize_pdf(texte: str) -> str:
    remplacements = {
        "→": "->",  "←": "<-",  "↔": "<->",
        "≥": ">=",  "≤": "<=",  "×": "x",   "÷": "/",
        "–": "-",   "—": "-",   "…": "...",
        "’": "'", "“": '"', "”": '"',
    }
    for char, repl in remplacements.items():
        texte = texte.replace(char, repl)
    return texte.encode("latin-1", errors="replace").decode("latin-1")
```

> **Règle d'or :** toute nouvelle chaîne issue de la DB passée à `pdf.cell()` ou
> `pdf.multi_cell()` doit être encapsulée dans `_sanitize_pdf()`.

### 13.2 Matrice « Temps de traversée » — création complète (P10.15)

#### Principe

Nouveau tableau identique en structure à la « Matrice congestion » (créneaux
horaires × dates) mais affichant les **durées réelles en mm:ss** au lieu des
pastilles rouge/vert.

Contrairement à `matrice_congestion` (source=`google` uniquement), cette matrice
inclut **toutes les sources** (`google`, `terrain`, `historique_paa_2025`) pour
permettre d'afficher les données importées depuis Excel aux côtés des mesures live.

#### Backend

**Nouvelle fonction `matrice_temps()` (`backend/app/analyse/rapport_paa.py`) :**

- Filtre : `duree_trafic_s IS NOT NULL`, `aberrante = False`, plage DEESP 07h-19h
- Toutes sources confondues (pas de filtre `source = google`)
- Par créneau horaire × date locale : la **dernière mesure** de l'heure gagne
  (ordre chronologique dans la requête)
- Retourne `{troncon_id, nb_mesures, dates: [...], tranches: [{heure, tranche, par_date}]}`
  où chaque cellule = `{duree_s, source}` ou `null`

**Nouvel endpoint `GET /rapport/matrice-temps`** (tag « rapport DEESP ») :

```
?campagne=AAAA-MM&troncon_id=N&debut=AAAA-MM-JJ&fin=AAAA-MM-JJ
```

Réponse enrichie avec `troncon_nom`, `distance_m`, `vitesse_ref_kmh`,
`temps_ref_s` (calculé depuis `distance_m / (vitesse_ref_kmh × 1000/3600)`).

**Nouvel endpoint `POST /rapport/import-mesures-excel`** (tag « rapport DEESP ») :

- Accepte multipart/form-data avec champ `fichier` (Excel `.xlsx`/`.xls` ou CSV `.csv`)
- Colonnes attendues : `date` (YYYY-MM-DD), `heure` (0-23), `troncon_id` (entier),
  `duree_mn` (décimal, minutes)
- Normalise les noms de colonnes (minuscules, espaces → underscore)
- Insère dans `mesures` avec `source=historique_paa_2025`
- Doublon : même `(troncon_id, source, horodatage exact)` → ignoré silencieusement
- Réponse : `{nb_inserees, nb_doublons, erreurs: [...], message: "..."}`
- Dépendances : `pandas` + `openpyxl` (déjà dans `requirements.txt`)

#### Frontend

**Nouveau composant `MatriceTemps.tsx` (`frontend/components/rapport/`) :**

| Fonctionnalité | Détail |
|---|---|
| Affichage | Cellules `mm:ss` (ex. `23:15`), — si pas de donnée |
| Code couleur | Basé sur le ratio `duree_s / temps_ref_s` : vert ≤ 1,0 / lime ≤ 1,3 / orange ≤ 1,5 / rouge > 1,5 |
| Colonne moyenne | Droite du tableau : moyenne des durées visibles de la fenêtre, colorée selon le même ratio |
| Tooltip | Au survol : durée + source (`source: google`) |
| Week-ends | Colonnes légèrement grisées, `opacity-80` |
| Bouton Import | « 📥 Importer Excel » visible en mode écriture (`peutEcrire`) — déclenche `POST /rapport/import-mesures-excel` |
| Feedback import | Message inline `✓ N insérées, M doublons` ou `Erreur : ...` |
| Sélecteur tronçon | Même composant `<select>` que MatriceCongestion, partage l'état `tronconId` |

**Intégration dans `PageRapport.tsx` :**

`<MatriceTemps>` est placé immédiatement **sous** `<MatriceCongestion>`, avant le
Tableau 16. Les deux matrices partagent les mêmes props (`campagne`, `debutRange`,
`finRange`, `tronconId`, `troncons`, `onTronconChange`).

### 13.3 Navigation 7 jours — `MatriceCongestion` et `MatriceTemps`

Les deux composants affichent désormais des boutons de navigation quand la période
sélectionnée dépasse 7 jours (ex. mois complet = 30 jours).

**Comportement :**

- État `fenetre: number` (0-indexed, reset à 0 à chaque changement de période/tronçon)
- `datesVisibles = data.dates.slice(fenetre * 7, (fenetre + 1) * 7)`
- `maxFenetre = Math.max(0, Math.ceil(data.dates.length / 7) - 1)`
- Boutons « ← 7 jours précédents » (disabled si `fenetre === 0`) et
  « 7 jours suivants → » (disabled si `fenetre >= maxFenetre`)
- Libellé « Semaine {fenetre+1} / {maxFenetre+1} »

**Règle DEESP ≥4× dans `MatriceCongestion` :**

- Badge `≥4×` basé sur **toutes** les dates de la période (`nbCongTotal`)
  — pas seulement la fenêtre visible → représentatif de la période complète
- Colonne « Total 🟥 » basée sur les **dates visibles** uniquement → cohérent
  avec ce qu'on voit dans la fenêtre
- Surlignage rouge de la ligne si `nbCong >= 4` sur la fenêtre visible

### 13.4 Format Excel attendu pour l'import

| Colonne | Type | Exemple | Notes |
|---|---|---|---|
| `date` | date | `2026-06-15` ou `15/06/2026` | `pd.to_datetime()` accepte les deux formats |
| `heure` | entier | `8` | 0-23 (heure de la mesure en heure locale Africa/Abidjan) |
| `troncon_id` | entier | `1` | Doit exister dans la table `troncons` |
| `duree_mn` | décimal | `23.5` | Minutes décimales → converti en secondes entiers |

Les noms de colonnes sont **insensibles à la casse** et les espaces sont
normalisés en `_` (ex. `Durée Mn` → `duree_mn`). Les colonnes supplémentaires
sont ignorées.

**Erreurs retournées par ligne** (les 20 premières, format `Ligne N: message`) :
- Tronçon inconnu
- Heure invalide (hors 0-23)
- Durée ≤ 0
- Erreur de parsing date/valeur

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


---

## 12. Phase P10 — Refonte UX, auth 2 niveaux, axes/tronçons, PDF direct (2026-06-28)

> Série de 9 améliorations livrées le 2026-06-28 sur les commits
> `fc680b2 → c8793d9 → 8034b1d → 21cbdd9 → 1ffd54e`. Toutes terminées et
> déployées en production sur Railway.

### 12.1 Authentification à 2 niveaux — `PasswordGate`

**Fichiers** : `frontend/contexts/AuthContext.tsx`,
`frontend/components/auth/PasswordGate.tsx`,
`frontend/components/layout/ClientLayout.tsx`.

**Principe** :
- Portail mot de passe affiché AVANT le splash screen, à chaque
  refresh / nouvel onglet (état React pur, sans `sessionStorage`).
- Deux mots de passe :
  - `readhackatonia` → niveau **lecture** : consultation uniquement
  - `readwritehackatonia` → niveau **écriture** : accès complet
- Stockés dans `localStorage` (clés `paa_mdp_lecture` / `paa_mdp_ecriture`)
  pour permettre le changement (ancien MDP exigé, nouveau ≥ 6 caractères).
  Les valeurs hardcodées ci-dessus sont les défauts si rien dans localStorage.

**Cascade d'application** :
- `app/layout.tsx` enveloppe `{children}` dans `<ClientLayout>`
- `<ClientLayout>` affiche `<PasswordGate>` tant que `niveau === null`
- Une fois authentifié, `<AuthProvider>` expose `niveau` et `peutEcrire` via
  `useAuth()` à tous les composants enfants.

**Boutons d'écriture masqués en mode lecture** :
- `BarrePilotage` — démarrer/arrêter collecte, export CSV/XLSX, Tout CSV/Excel
- `FiltresIncidents` — bouton Exporter CSV
- `EvolutionPluriannuelle` — bouton « Mettre à jour »
- `GestionSources` — panneau complet
- `OngletAxes` (Admin) — toute la page

### 12.2 Refonte du portail d'accès

**Layout 3 colonnes sur desktop** (`lg:flex`) :

1. **Gauche** — logo PAA rond 208 px (image `/logo-hackathon.jpg`),
   cerclé blanc/slate selon thème, ombre 2xl + libellé « PORT AUTONOME D'ABIDJAN »
2. **Centre** — carte de connexion (titre, input, boutons)
3. **Droite** — lettres `H-A-C-K-A-T-O-N-I-A` verticales en
   `text-sky-400 dark:text-sky-300` avec drop-shadow glow bleu
   + ligne dégradée + « 2026 » rotaté

**Mobile** : logo en haut centré + « HACKATONIA » en pied de page horizontal.

**Fond** : `bg-gradient-to-br from-slate-100 via-blue-50 to-slate-200`
en clair, `from-slate-950 via-slate-900 to-slate-950` en sombre.
Logo PAA en filigrane discret (opacity 0.07) sur fond.

**Toggle thème** : `useTheme()` de `next-themes` exposé dans le coin
supérieur droit du portail (avant authentification).
**Thème par défaut passé de `"system"` à `"light"`** dans `ThemeProvider.tsx`.

### 12.3 Vue satellite sur toutes les cartes

Toggle « 🛰 Satellite / 🗺 OSM » ajouté en bas à gauche de chaque carte Leaflet :
- `CarteLeaflet.tsx` (carte principale)
- `CarteApercu.tsx` (page Fiabilité)
- `CarteIncidents.tsx` (page Incidents)

**Tuiles satellite** : ESRI WorldImagery (gratuit, sans clé) — URL
`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
(attention à l'ordre `{z}/{y}/{x}` différent de OSM `{z}/{x}/{y}`).

**Implémentation** : la couche de tuiles est stockée dans une `useRef`,
un `useEffect([satellite])` retire l'ancienne et ajoute la nouvelle au
clic du toggle.

### 12.4 Exports globaux page Indicateurs

`BarrePilotage` accepte désormais `troncons: Troncon[]` en prop. Si
`peutEcrire && troncons.length > 1`, deux boutons supplémentaires
apparaissent à côté de Exporter CSV / XLSX :

- **Tout CSV** → boucle sur tous les tronçons et déclenche un
  téléchargement séquentiel (anchor `<a download>`) avec délai 600 ms
  entre chaque pour éviter le blocage navigateur.
- **Tout Excel** → idem pour le format XLSX.

Nom des fichiers : `mesures_troncon{id}_{AAAA-MM-JJ}.{csv|xlsx}`.

### 12.5 Axes et tronçons — migration 0013

**Migration** : ajout colonne `troncons.est_axe BOOLEAN NOT NULL DEFAULT TRUE`.

**Sémantique** :
- `est_axe = True` → axe (itinéraire de surveillance) créé via l'onglet
  « Axes principaux » de la page Admin. Les 6 axes initiaux du cahier des
  charges DEESP sont marqués `True`.
- `est_axe = False` → (legacy, plus utilisé depuis la refonte post-hackathon)

Chaque axe peut être découpé en **tronçons codifiés** (T1A, T1B, T1C…)
via l'onglet « Tronçons codifiés ». Un tronçon est toujours enfant d'un
axe parent.

**Modifications UI** :
- **Onglet « Axes principaux »** : crée des axes. Tableau en bas avec
  colonnes ID, Nom, Distance, Couleur, Actions (archiver).
- **Onglet « Tronçons codifiés »** : sélecteur d'axe parent, formulaire
  de création (code, nom, coords). Tableau affichant les tronçons codifiés
  de l'axe sélectionné.
- `SelecteurTroncon` (Indicateurs, etc.) utilise
  `<optgroup label="── Axes ──">` et `<optgroup label="── Tronçons ──">`
- Backend : `est_axe` exposé dans `/carte/etat`, `/troncons`,
  `/troncons/{id}`, `/administration/troncons`

**Chatbot** : `SYSTEM_PROMPT` enrichi d'une section « AXES ET TRONÇONS ».

### 12.6 PDF Tableau 16 — téléchargement direct

**Backend** : nouvel endpoint `GET /rapport/zones-congestionnees/pdf`
dans `backend/app/api/rapport.py` utilise **fpdf2** (pure Python, ~200 ko,
ajouté à `requirements.txt`).

**Réponse** :

```python
return Response(
    content=bytes(pdf.output()),
    media_type="application/pdf",
    headers={"Content-Disposition": 'attachment; filename="tableau16_AAAA-MM.pdf"'},
)
```

**Frontend** : `TableauZonesCongestionnees.tsx` :

```typescript
const rep = await fetch(`${API_BASE}/rapport/zones-congestionnees/pdf?campagne=${camp}`);
const blob = await rep.blob();
const a = document.createElement("a");
a.href = URL.createObjectURL(blob);
a.download = `tableau16_${camp}.pdf`;
a.click();
```

Pas de popup, pas d'aperçu, pas de fenêtre `print()` — téléchargement immédiat
dans le dossier Téléchargements du navigateur.

**Pourquoi pas jsPDF côté client** : `npm install jspdf jspdf-autotable` apporte
12 CVE **critiques** sur `dompurify` (Railway bloque le build, cf. § 8.2.1).
`fpdf2` côté serveur évite ce problème sans dépendance OS.

### 12.7 Import CSV/Excel évolution pluriannuelle

**Backend** : `POST /import/evolution-csv` dans `backend/app/api/import_data.py`.

**Format attendu** (7 colonnes, insensible à la casse, espaces → underscore) :

```
axe,sens,periode,type_jour,temps_min_s,temps_moyen_s,temps_max_s
"CARENA → Palm Beach",Aller,oct_2025,jour_ouvrable,720,950,1320
```

**Comportement** : UPSERT sur la clé unique
`(axe, sens, periode, type_jour)` — un second import ne duplique pas, il
remplace. Réponse JSON : `{ "nb_ajoutees": N, "nb_majs": M, "message": "…" }`.

**Frontend** : bandeau bleu pâle dans `EvolutionPluriannuelle.tsx`
(mode écriture uniquement) avec `<input type="file" accept=".csv,.xlsx,.xls">`.
Rechargement automatique du graphique après import réussi.

### 12.8 Sources scraping incidents — migration 0014

**Migration** : table `sources_incidents` (id, nom, libelle, url, type,
actif, fiabilite, ajoute_le). Seed initial = 3 sources historiques
(fraternite_matin, abidjan_net, koaci) avec leurs fiabilités respectives.

**Modèle SQLAlchemy** : `SourceIncident` ajouté dans `models.py`.

**Endpoints** (tag « incidents ») :
- `GET    /incidents/sources`            → liste
- `POST   /incidents/sources`            → création (409 si nom déjà pris)
- `PATCH  /incidents/sources/{id}`       → mise à jour (notamment toggle actif)
- `DELETE /incidents/sources/{id}`       → suppression définitive

**Lecture par le scheduler** : `scraper_toutes_sources()` dans
`rss_parser.py` interroge la table en priorité (`actif=True AND type='rss'`).
**Repli silencieux** sur la constante `SOURCES_RSS` historique si la table
est inaccessible.

**UI** : composant `GestionSources.tsx` ajouté en bas de la page Incidents,
visible en mode écriture uniquement. Panneau dépliable
« ⚙ Gérer les sources de scraping (N) » avec tableau (toggle ON/OFF,
supprimer) + formulaire d'ajout. Indication : « La source est utilisée au
prochain cycle de scraping (toutes les 30 min) ».

### 12.9 Améliorations diverses

| Modification | Fichier(s) |
|---|---|
| Navigation réordonnée (Rapport avant Indicateurs) | `NavItems.tsx` |
| Filtres incidents : Accident / Route barrée / Travaux seulement | `FiltresIncidents.tsx` |
| Graphique « Accidents par mois » (BarChart rouge) | `PageIncidents.tsx` |
| Tri chronologique Oct 2025 avant Fév 2026 (parseur `oct_2025 → 202510`) | `EvolutionPluriannuelle.tsx` |
| Tous les « Mn » remplacés par « Min » dans le rapport DEESP | `TableauTempsTraversee.tsx`, `GraphiquesParAxe.tsx` |
| Bloc temps réel simplifié → une seule valeur « Temps récent » | `PagePrediction.tsx` |
| Admin : onglet « Sous-tronçons codifiés » renommé « Tronçons codifiés » | `PageAdministration.tsx` |
| Titre Admin : « axes & tronçons » au lieu de « tronçons & sous-tronçons » | `PageAdministration.tsx` |

### 12.10 Types d'incidents dynamiques + filtre zone portuaire strict (P10.10 — 2026-06-29)

#### Problème résolu

Le scraper insérait des articles sans rapport avec la zone portuaire d'Abidjan quand
un mot-clé générique comme « travaux » apparaissait dans le titre (ex. : un article
sur la sous-préfecture de Yakassé-Feyassé). De plus, les types d'incidents étaient
figés dans un ENUM PostgreSQL — impossible d'en ajouter sans migration Alembic.

#### Double filtre scraper (rss_parser.py)

Avant : `MOTS_CLES_INCIDENTS` = une seule liste OR — un seul mot suffit.

Après : deux listes séparées, les deux sont obligatoires :

```python
MOTS_CLES_TYPE = ["accident", "collision", "travaux", "embouteillage", …]
MOTS_CLES_ZONE = ["Treichville", "CARENA", "Palm Beach", "pont HB", "Houphouët", …]

def _contient_mot_cle(titre, resume):
    texte = titre + " " + resume
    return bool(_RE_TYPE.search(texte)) and bool(_RE_ZONE.search(texte))
```

Un article « travaux à Yakassé-Feyassé » → RE_TYPE matche « travaux » MAIS RE_ZONE
ne matche aucun lieu portuaire → **rejeté**.

#### Migration 0015 — VARCHAR + table types_incidents

```sql
-- 1. Convertit la colonne ENUM en VARCHAR libre
ALTER TABLE incidents ALTER COLUMN type_incident TYPE VARCHAR(50) USING type_incident::text;
DROP TYPE IF EXISTS typeincident;

-- 2. Nouvelle table configurable
CREATE TABLE types_incidents (
    id       SERIAL PRIMARY KEY,
    slug     VARCHAR(50) UNIQUE NOT NULL,
    libelle  VARCHAR(200) NOT NULL,
    regex    TEXT NOT NULL,
    actif    BOOLEAN NOT NULL DEFAULT true,
    cree_le  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Seed (4 types de base + 'autre')
INSERT INTO types_incidents (slug, libelle, regex, actif) VALUES
  ('accident',      'Accident',      'accident|collision|accrochage|…', true),
  ('route_barree',  'Route barrée',  'route barr|voie coup|…',          true),
  ('travaux',       'Travaux',       'travaux|chantier|réfection|…',    true),
  ('embouteillage', 'Embouteillage', 'embouteillage|bouchon|…',         true),
  ('autre',         'Autre',         '(?!)',                             true)
ON CONFLICT (slug) DO NOTHING;
```

#### Classificateur NLP dynamique (incidents_nlp.py)

`classifier_type()` accepte désormais un paramètre optionnel `types_config :
list[tuple[str, str]]` (liste de `(slug, regex_str)` chargée depuis la DB).

`enrichir_incidents()` charge les types actifs en début de fonction et les passe
au classificateur. Si la table est vide ou inaccessible → repli sur `_RE_TYPE_DEFAUT`
hardcodé (même comportement qu'avant).

#### Endpoints CRUD /incidents/types

```
GET    /incidents/types          → liste tous les types (actifs et inactifs)
POST   /incidents/types          → crée un type (valide la regex avant insertion)
PATCH  /incidents/types/{id}     → modifie libellé / regex / actif
DELETE /incidents/types/{id}     → supprime (interdit pour slug='autre')
```

Validation de la regex Python avant insertion (HTTP 422 si invalide).

#### Modèle SQLAlchemy TypesIncident

Nouvelle classe `TypesIncident` dans `app/models/models.py`.
La colonne `Incident.type_incident` passe de `postgresql.ENUM(…)` à `String(50)`.
L'enum Python `TypeIncident` est conservée pour la compatibilité ascendante des
importations existantes (elle n'est plus mappée à la DB).

#### Frontend (état final — P10.11)

**Architecture état partagé** : `PageIncidents` est le seul propriétaire de
`typesIncidents: TypeIncidentApi[]`. Il charge les types via `chargerTypes()`
au montage et passe :
- `types={typesIncidents}` à `FiltresIncidents` → dropdown toujours synchronisé
- `onTypeChange={chargerTypes}` à `GestionTypes` → callback appelé après chaque
  mutation (ajout / toggle / suppression) → filtre mis à jour **instantanément**
  sans rechargement de page.

**`FiltresIncidents.tsx`** : reçoit `types` en prop (plus de `useEffect` interne).
Filtre appliqué : `actif && slug !== 'autre'` — le type « Autre » est invisible
dans le dropdown.

**`GestionTypes.tsx`** : panneau dépliable « 🏷 Gérer les types d'incidents (N) »
visible en mode écriture. Fonctionnalités :
- Tableau des types (hors `autre`) : badges mots-clés, toggle ON/OFF, Supprimer
- Formulaire d'ajout **simplifié** : libellé + **mots-clés** séparés par virgule
  (la regex est générée automatiquement via `motsVersRegex()`, aperçu en temps réel)
- Suggestion d'interroger le chatbot PAA pour trouver des mots-clés adaptés
- Validation : libellé ≥ 2 chars, au moins 1 mot-clé non vide
- Erreurs affichées avec auto-effacement après 6 s

**Type « Autre »** : masqué dans le tableau de gestion et dans le filtre dropdown.
Il reste en base comme fallback silencieux du classificateur NLP.

**Chatbot** : `SYSTEM_PROMPT` enrichi d'une section « AIDE À LA CRÉATION DE TYPES
D'INCIDENTS » — le LLM répond directement avec une liste de mots-clés prêts à
copier-coller si on lui demande quels mots utiliser pour un type donné.

**`PageIncidents.tsx`** : importe et affiche `<GestionTypes onTypeChange={chargerTypes} />`
sous `<GestionSources />`.

#### Commandes Railway Console — nettoyage des incidents hors zone

```bash
# 1. Supprimer les incidents avec un titre contenant un lieu hors zone (ex. Yakassé)
python -c "
from app.db.session import SessionLocal
from app.models.models import Incident
db = SessionLocal()
n = db.query(Incident).filter(Incident.titre.ilike('%Yakass%')).delete(synchronize_session=False)
db.commit()
print(f'{n} incident(s) supprimé(s)')
db.close()
"

# 2. Supprimer TOUS les incidents sans coordonnées GPS (non géolocalisés = hors zone)
python -c "
from app.db.session import SessionLocal
from app.models.models import Incident
db = SessionLocal()
n = db.query(Incident).filter(Incident.lat.is_(None)).delete(synchronize_session=False)
db.commit()
print(f'{n} incident(s) hors zone (lat=NULL) supprimé(s)')
db.close()
"
```

### 12.11 Récapitulatif des migrations Alembic

| Migration | Objet |
|-----------|-------|
| `0013_troncon_est_axe.py` | Ajoute `troncons.est_axe` |
| `0014_sources_incidents.py` | Crée la table `sources_incidents` + seed 3 sources |
| `0015_types_incidents.py` | VARCHAR `type_incident` + table `types_incidents` + seed 5 types |

À appliquer après tout déploiement contenant ces migrations :

```bash
# Console Railway service backend
alembic upgrade head
```

### 12.12 Vérification post-déploiement

```bash
# 1. Migrations à jour
alembic current && alembic heads

# 2. Colonne est_axe + tables sources/types incidents
python -c "
from sqlalchemy import text
from app.db.session import SessionLocal
db = SessionLocal()
for r in db.execute(text('SELECT id, nom, est_axe FROM troncons ORDER BY id')).all():
    print(r.id, r.est_axe, r.nom)
for r in db.execute(text('SELECT nom, libelle, actif FROM sources_incidents')).all():
    print(r.nom, r.libelle, r.actif)
for r in db.execute(text('SELECT slug, libelle, actif FROM types_incidents ORDER BY id')).all():
    print(r.slug, r.libelle, r.actif)
db.close()
"

# 3. fpdf2 installé
python -c "import fpdf; print('fpdf2', fpdf.__version__)"

# 4. Endpoint PDF
python -c "
import httpx
r = httpx.get('http://localhost:8000/rapport/zones-congestionnees/pdf?campagne=2026-06', timeout=15)
print(r.status_code, r.headers.get('content-type'), len(r.content))
assert r.content[:4] == b'%PDF'
"

# 5. Endpoints incidents sources + types
python -c "
import httpx
print('/incidents/sources :', httpx.get('http://localhost:8000/incidents/sources', timeout=10).status_code)
print('/incidents/types   :', httpx.get('http://localhost:8000/incidents/types', timeout=10).status_code)
"
```

---

## 14. Phase P11 — Indicateurs étendus et filtre créneau horaire global (2026-07-01 → 2026-07-02)

### 14.1 Indicateurs 6 mois / 1 an + suppression heatmap (P11.1 — 2026-07-01)

**Modifications :**

- **2 nouvelles périodes** ajoutées au sélecteur (`SelecteurPeriode`) :
  `6mois` (180 j) et `1an` (365 j). Le backend accepte `?periode=180j` et
  `?periode=365j` via le parseur `_parse_periode` dans `backend/app/api/troncons.py`.
- **Suppression de la heatmap horaire** — le composant heatmap a été retiré de la
  page Indicateurs. L'affichage est désormais entièrement vertical : KPI + courbe
  journée + évolution pluriannuelle.
- **Courbe journée enrichie** (`CourbeJournee.tsx`) : la valeur **minimum** est
  désormais affichée sur le graphe Recharts en plus de la moyenne et du max.
- **Export matrice temps** : bouton d'export ajouté dans `MatriceTemps.tsx`.

**Clés i18n ajoutées** (`frontend/messages/{fr,en}.json`) :
- `indicateurs.periode6mois` : « 6 mois » / « 6 months »
- `indicateurs.periode1an` : « 1 an » / « 1 year »

### 14.2 Filtre créneau horaire global (P11.2 — 2026-07-01)

**Principe** : un sélecteur de plage horaire dans la topbar (`Topbar.tsx`)
permet de restreindre toutes les analyses à un créneau horaire donné
(ex. 07h–19h pour la plage DEESP). Par défaut : 24h/24 (pas de filtre).

**Architecture :**

```
frontend/contexts/PlageHoraireContext.tsx
  └── PlageHoraireProvider (enveloppe l'app dans ClientLayout.tsx)
      ├── heureDebut: number (0-23)
      ├── heureFin: number (1-24)
      ├── setPlage(debut, fin): void
      ├── plageLabel: string (ex. "07h – 19h")
      └── est24h: boolean

frontend/components/layout/SelecteurPlageHoraire.tsx
  └── Dropdown avec 2 sélecteurs (début + fin) + boutons Appliquer / Réinitialiser
      Affiché dans la topbar, à côté du sélecteur de langue
```

**Persistance** : `localStorage` (clés `paa_plage_h_debut` / `paa_plage_h_fin`).

**Propagation backend** : les endpoints suivants acceptent désormais
`?heure_debut=N&heure_fin=M` (paramètres Query optionnels, défaut 0/24) :

| Endpoint | Fichier backend | Effet |
|----------|-----------------|-------|
| `GET /troncons/{id}/indicateurs` | `backend/app/api/troncons.py` | Filtre les mesures sur le créneau horaire local |
| `GET /indicateurs/{id}` | `backend/app/api/indicateurs.py` | Idem via `indicateurs_par_jour()` |
| `GET /evolution/troncon/{id}` | `backend/app/api/evolution.py` | Filtre les mois reconstruits et le mois courant |
| `GET /predire/resume` | `backend/app/api/predire.py` | Filtre les stats mois/semaine |
| `GET /predire/heure-optimale` | `backend/app/api/predire.py` | Filtre les créneaux analysés |
| `GET /rapport/zones-congestionnees` | `backend/app/api/rapport.py` | Filtre le Tableau 16 |

**Filtrage côté backend** : le filtre s'applique sur l'**heure locale
Africa/Abidjan** de chaque mesure (conversion UTC → local via
`datetime.astimezone(ZoneInfo("Africa/Abidjan"))`), pas sur l'heure UTC.
Condition : `heure_debut <= heure_locale < heure_fin`.

**Pages frontend impactées** :

| Page | Composant | Hook utilisé |
|------|-----------|-------------|
| Indicateurs | `PageIndicateurs.tsx` | `usePlageHoraire()` → passe `heureDebut`, `heureFin` à `getIndicateursTroncon()` |
| Temps de traversée | `PagePrediction.tsx` | `usePlageHoraire()` → passe aux appels API `predire/resume` |
| Heure optimale | `PageHeureOptimale.tsx` | `usePlageHoraire()` → filtre les créneaux |
| Rapport DEESP | `PageRapport.tsx` | `usePlageHoraire()` → passe au Tableau 16 |
| Évolution pluriannuelle | `EvolutionPluriannuelle.tsx` | `usePlageHoraire()` → passe à `GET /evolution/troncon/{id}` |

**Indicateur visuel** : quand le filtre est actif (≠ 24h/24), le bouton du
sélecteur dans la topbar passe en **fond ambre** (`bg-amber-500/20
text-amber-200 border-amber-400/60`) pour signaler que les données sont
filtrées. Les titres et sous-titres des pages affichent dynamiquement
le créneau actif (ex. « Créneau : 07h–19h »).

### 14.3 Fix bouton Appliquer invisible en mode clair (P11.3 — 2026-07-02)

**Problème** : dans `SelecteurPlageHoraire.tsx`, le bouton « ✓ Appliquer »
utilisait `bg-paa-blue-600` — une couleur **inexistante** dans la palette
Tailwind (`paa.blue` s'arrête à 500). En mode clair, aucun fond ne s'appliquait,
rendant le texte blanc invisible sur fond blanc.

**Correction** : `bg-paa-blue-600` → `bg-paa-navy-700` et
`hover:bg-paa-blue-700` → `hover:bg-paa-navy-800`, cohérent avec la classe
`btn-primary` utilisée partout ailleurs dans l'application.

### 14.4 Incidents actifs pendant 30 jours au lieu de 6 heures (P11.4 — 2026-07-02)

**Motivation** : le seuil de 6 heures faisait disparaître les incidents trop vite
pour une démo ou un suivi opérationnel. Un incident de type « travaux » ou
« route barrée » peut durer plusieurs semaines.

**Implémentation** : nouveau paramètre `INCIDENT_ACTIF_HEURES` (défaut `720` = 30 jours)
dans `backend/app/core/config.py`. Le seuil est lu dynamiquement partout où il
était auparavant codé en dur à `6 * 3600`.

**Fichiers modifiés** :

| Fichier | Modification |
|---------|-------------|
| `backend/app/core/config.py` | Ajout `incident_actif_heures: int = 720` (alias `INCIDENT_ACTIF_HEURES`) |
| `backend/app/models/models.py` | Propriété `Incident.actif` lit `get_settings().incident_actif_heures` |
| `backend/app/api/incidents.py` | 4 occurrences `6 * 3600` → `get_settings().incident_actif_heures * 3600` |
| `backend/app/etat/carte.py` | `timedelta(hours=6)` → `timedelta(hours=settings.incident_actif_heures)` |
| `backend/app/rag/contexte.py` | Fenêtre RAG incidents dynamique + textes « 30 derniers jours » |
| `backend/app/api/chatbot.py` | Prompt système : « 6 heures » → « dernier mois » + mention du seuil configurable |
| `frontend/components/incidents/CarteIncidents.tsx` | `6 * 3600 * 1000` → `30 * 24 * 3600 * 1000` |
| `frontend/components/carte/CarteLeaflet.tsx` | `6 * 60 * 60 * 1000` → `30 * 24 * 60 * 60 * 1000` |

**Variable Railway** (optionnelle — le défaut 720h convient) :
```bash
railway variables set INCIDENT_ACTIF_HEURES=720 --service backend
```

**Scraping automatique des vrais incidents** : le job APScheduler `collecte_incidents`
tourne toutes les **30 minutes**, 24h/24. Il scrape les flux RSS de Fraternité Matin,
Abidjan.net et Koaci avec un **double filtre** obligatoire :
1. **Filtre TYPE** — l'article doit contenir un mot-clé de type (accident, travaux, embouteillage…)
2. **Filtre ZONE** — l'article doit mentionner un lieu de la zone portuaire (CARENA, Treichville, Palm Beach, pont HB…)

Les deux filtres doivent matcher simultanément — un article hors zone portuaire est
automatiquement écarté. Chaque incident retenu est géocodé via Nominatim OSM et
attribué au tronçon le plus proche (Haversine < 300 m). Les incidents réels
s'accumulent donc automatiquement dans la base au fil du temps.

---

## 15. Renommage produit PAA-Traverse → FLUIDIS (2026-07-03)

### 15.1 Décision et périmètre

Le 2026-07-03, le produit a été renommé **PAA-Traverse → FLUIDIS**. Le sigle
**PAA** seul reste utilisé partout pour désigner le **Port Autonome d'Abidjan**
(client), la **méthodologie DEESP/PAA**, et le service PAA en général — seul
le composé « PAA-Traverse » (nom historique de l'application) a été remplacé
par « FLUIDIS ».

### 15.2 Ce qui a été renommé

| Zone | Détail |
|------|--------|
| Code backend | Docstrings, commentaires, `SYSTEM_PROMPT` du chatbot, `User-Agent` scraper RSS + Nominatim, User-Agent client OSRM, seed scripts, générateur GPX, migration 0001 (docstring), `alembic.ini` |
| Code frontend | `frontend/app/layout.tsx` (title / OG / applicationName), `frontend/messages/{fr,en}.json` (`appName`, tagline, titre chatbot), `PasswordGate.tsx` (titre portail), `ChatbotButton.tsx` (message d'accueil), `GestionSources.tsx` (aide contextuelle), `frontend/lib/api.ts`, `frontend/tailwind.config.ts` (commentaire design-system) |
| Configs | `docker-compose.yml`, `railway.toml`, `deploy.sh`, `backend/Dockerfile`, `backend/requirements.txt`, `frontend/package.json` (`name: fluidis-frontend`), `frontend/package-lock.json`, `osrm-render/render.yaml`, `frontend/.env.example` |
| Docs | `CLAUDE.md`, `README.md`, `railwaydeploy.md`, `generer_procedure_gpx.py` (Word template) |
| Données | Champ `<creator>` des 6 GPX synthétiques (`backend/data/gpx_synth/*.gpx`) |
| Mémoire assistant | `MEMORY.md` + `user_profile.md` + `project_state.md` + nouveau `renommage_fluidis.md` |

### 15.3 Ce qui n'a PAS été renommé (volontaire)

- **Répertoire local** `C:\Users\hp\StudioProjects\paa-traverse` — renommer casserait Git, la config Claude Code, Railway CLI et les scripts existants.
- **Repository Git** distant — même raison.
- **Services Railway** (`backend`, `frontend`) et **URLs Railway** générées (`backend-production-6cbf.up.railway.app`, `frontend-production-599c.up.railway.app`) — indépendants du nom produit.
- **Containers Docker locaux** (`paa_db`, `paa_redis`, `paa_backend`, `paa_osrm`, `paa_frontend`) — préservent les volumes existants sur les postes de dev.
- **Sigle PAA seul** — désigne le client (Port Autonome d'Abidjan) partout dans le code, la doc, et le prompt système.

### 15.4 Méthode

Script Python one-shot en 5 substitutions ordonnées :

1. `paa-traverse-frontend` → `fluidis-frontend`
2. `paa-traverse` → `fluidis`
3. `paa_traverse` → `fluidis`
4. `PAA-Traverse` → `FLUIDIS`
5. `PAA Traverse` → `FLUIDIS`

Le script itère `git ls-files`, filtre par extension texte, applique les
substitutions et réécrit UTF-8. 43 fichiers modifiés. Vérification finale
`grep` → **0 occurrence résiduelle** de `PAA-Traverse` ou `paa-traverse`.

### 15.5 Post-renommage

Après ce commit, toute nouvelle chaîne d'interface, prompt système, doc utilisateur
ou log doit utiliser **FLUIDIS**. Le sigle **PAA** seul continue d'être utilisé
pour le client et la méthodologie DEESP.

---

## 16. Comptage dynamique axes / tronçons et effets de l'archivage (2026-07-04)

### 16.1 Compteur « N axes et M tronçons » sur la carte

Le panneau latéral de la page **Accueil / Carte** affiche un bandeau d'état :

> **État : 6 axes et 2 tronçons (couleurs Google Maps)**

Ce libellé est **entièrement calculé côté frontend** dans
[PanneauTroncons.tsx](frontend/components/carte/PanneauTroncons.tsx) à partir du
payload `GET /carte/etat`. Il n'y a aucun compteur figé côté backend :

- `nbAxes` = nombre d'entrées de `etat.troncons` avec `est_axe !== false`
- `nbTroncons` = somme des `tr.sous_troncons.length` sur ces mêmes axes

**Conséquence concrète — auto-incrémentation garantie :**

| Action opérateur | Effet sur le compteur |
|------------------|-----------------------|
| Créer un **axe** via `POST /administration/troncons` (`est_axe=true`) | `nbAxes +1` au **prochain refresh** de la carte (polling 30 s ou push WebSocket) |
| Créer un **sous-tronçon** via `POST /administration/troncons/{id}/sous-troncons` | `nbTroncons +1` idem |
| **Archiver** un axe ou sous-tronçon via `DELETE /administration/...` | Compteur **décrémenté** immédiatement au refresh (l'entrée disparaît de `/carte/etat`) |

Aucun redémarrage du scheduler ni de la carte n'est nécessaire. Le compteur
reflète **exactement** le contenu vivant de la base de données à chaque cycle.

### 16.2 Effets de l'archivage (suppression logique)

`DELETE /administration/troncons/{id}` et `DELETE /administration/sous-troncons/{id}`
posent `actif = false`. Aucune ligne n'est physiquement supprimée — les mesures
et l'historique sont préservés (règle d'or § 5.3).

**Ce que bloque l'archivage** — filtres `actif=True` appliqués partout :

| Système | Fichier | Comportement post-archivage |
|---------|---------|-----------------------------|
| Carte temps réel (`/carte/etat`) | [backend/app/etat/carte.py:72,95](backend/app/etat/carte.py) | L'axe/tronçon **disparaît** de la carte et du panneau latéral |
| Compteur bandeau « N axes et M tronçons » | [frontend/components/carte/PanneauTroncons.tsx](frontend/components/carte/PanneauTroncons.tsx) | **Décrémenté** au prochain refresh |
| Collecte Google Routes | [backend/app/collecte/scheduler.py:324,334](backend/app/collecte/scheduler.py) | **Plus aucun cycle Google** sur cet axe/tronçon |
| Estimation quota Google | [backend/app/api/administration.py:474](backend/app/api/administration.py) | Recalculée automatiquement à la baisse |
| Page Indicateurs / dropdowns tronçons | `GET /troncons` | L'entrée archivée **n'apparaît plus** dans les sélecteurs |
| Rapport DEESP | [backend/app/analyse/rapport_paa.py](backend/app/analyse/rapport_paa.py) | Exclu des Tableaux 3-16 |
| Overlay incidents | [backend/app/etat/carte.py](backend/app/etat/carte.py) | Les incidents rattachés restent en base mais ne s'affichent plus sur l'axe archivé |

**Ce qui n'est pas bloqué** (volontaire) :

- L'**historique des mesures** de l'axe/tronçon archivé reste consultable via
  `GET /troncons/{id}/mesures` (utile pour analyse rétrospective).
- Les **relevés terrain GPX** déjà associés restent en base.
- Un axe archivé peut être **réactivé** en base (`UPDATE troncons SET actif = true`).
  Il n'y a pas encore d'endpoint dédié — à faire depuis la Console Railway.

### 16.3 Migration 2026-07-04 des orphelins vers `sous_troncons`

Le refactor du 2026-06-30 (commit `2458aff`) a supprimé la notion de
« tronçon supplémentaire ». Deux entrées historiques étaient restées avec
`est_axe=false` dans la table `troncons` :

| id | Nom | Distance | Nouveau statut |
|----|-----|----------|----------------|
| 8 | AGL-Grand Moulin | 1466 m | Sous-tronçon **T1A** de l'axe 1 (CARENA → Palm Beach) |
| 9 | Palmbeach - Outillage Port | 6523 m | Sous-tronçon **T2A** de l'axe 2 (Palm Beach → CARENA) |

**Script utilitaire** : [`backend/scripts/migrer_orphelins_vers_sous_troncons.py`](backend/scripts/migrer_orphelins_vers_sous_troncons.py).
Idempotent (relançable sans effet secondaire), lancé une fois depuis la Console
Railway du service backend :

```bash
python -m scripts.migrer_orphelins_vers_sous_troncons
```

Il :
1. Récupère tous les tronçons `est_axe=false AND actif=true`.
2. Pour chacun figurant dans le mapping `MAPPING_ORPHELINS`, crée un
   `SousTroncon` sur l'axe parent (avec code DEESP, ordre auto, copie
   polyline + distance).
3. Archive l'entrée d'origine (`actif=false`).

**Après cette migration** :
- Le bandeau carte affiche « 6 axes et 2 tronçons ».
- Chaque nouveau sous-tronçon créé via l'onglet Administration → « Tronçons
  codifiés » s'ajoute à la suite (ordre incrémenté), incrémente le compteur
  et rejoint la collecte au prochain cycle Google.

### 16.4 Rendu des polylines mixtes axe / sous-tronçon (2026-07-04)

Avant le fix du 2026-07-04, [CarteLeaflet.tsx](frontend/components/carte/CarteLeaflet.tsx)
appliquait la règle suivante : dès qu'un axe portait au moins un sous-tronçon,
le tracé du parent basculait en pointillé `weight 3, opacity 0.35, dashArray "6 8"`.
Cette règle vient de l'hypothèse que l'axe est **entièrement décomposé** en
sous-tronçons couvrant toute sa polyline (cf. § 4.8) — dans ce cas le pointillé
sert juste à situer l'axe, tandis que les enfants opaques occupent tout l'espace.

Le cas réel post-migration 2026-07-04 est différent : l'axe 1 (11,9 km) possède
un unique sous-tronçon T1A (1,5 km). En pointillé opacity 0,35, les 10,4 km
restants (dont toute la portion allant vers CARENA) devenaient invisibles.

**Fix appliqué** — le parent reste **toujours tracé en trait plein** sur toute
sa longueur :

| Cas | Style parent | Style sous-tronçon |
|-----|--------------|--------------------|
| Axe sans sous-tronçon | `weight 5, opacity 0.85`  | — |
| Axe avec sous-tronçon(s) | `weight 4, opacity 0.6` (adouci mais visible) | `weight 6, opacity 0.95` par-dessus |

L'effet visuel : le parcours complet reste lisible, et la portion couverte par
un sous-tronçon apparaît légèrement plus épaisse et opaque pour signaler la
granularité fine. Convient aux deux cas d'usage — décomposition partielle
(T1A seul) et décomposition complète (T1A + T1B + T1C…).

### 16.5 Sous-tronçons cliquables + zoom fin (2026-07-04)

Le panneau latéral de la page **Accueil / Carte**
([PanneauTroncons.tsx](frontend/components/carte/PanneauTroncons.tsx))
affiche désormais chaque sous-tronçon codifié comme une entrée cliquable
sous son axe parent, avec :

- **Badge coloré** portant le code DEESP (T1A, T2A…) — la couleur reflète la
  classe DEESP live du sous-tronçon
- **Nom court** (`sous.nom_court`, ex. « AGL-Grand Moulin »)
- **Distance** en km avec 2 décimales
- **Temps actuel** de la dernière mesure du sous-tronçon (mm:ss)

**Contrat de sélection** — [PageCarte.tsx](frontend/components/carte/PageCarte.tsx)
gère deux états parallèles :

| État | Signification |
|------|---------------|
| `selectionId: number \| null` | ID de l'axe surligné dans le panneau |
| `selectionSousId: number \| null` | ID du sous-tronçon activé pour le zoom fin |

- **Clic sur un axe** → `handleSelectionner(id)` : `selectionSousId` remis à
  `null`, `selectionId` mis à jour, zoom sur la polyline complète de l'axe.
- **Clic sur un sous-tronçon** → `handleSelectionnerSous(sousId, parentId)` :
  `selectionId` = parent (pour la surbrillance visuelle de l'axe parent),
  `selectionSousId` = sous. Le zoom passe en **priorité au sous-tronçon**.

**Effet zoom** (`CarteLeaflet.tsx` effet 4) — nouvelle prop
`sousTronconSelectionneId?: number | null` :

1. Si `sousTronconSelectionneId !== null` → le code cherche le sous-tronçon
   correspondant dans `etat.troncons[].sous_troncons[]`. Il utilise les coords
   `sous.geometrie.{lat_debut, lon_debut, lat_fin, lon_fin}` pour :
   - Calculer les bounds et appeler `map.flyToBounds({ padding: [60,60],
     maxZoom: 17 })` — zoom **plus rapproché** que sur un axe complet
     (`maxZoom: 16`).
   - Poser deux `CircleMarker` : disque vert « 🟢 Début T1A : AGL-Grand Moulin »
     au point de départ, disque rouge « 🔴 Fin T1A : … » au point d'arrivée.
   - Ouvrir la popup du sous-tronçon (`lignesSousRef.current.get(cle)`).
2. Sinon si `tronconSelectionneId !== null` → comportement historique (zoom
   sur la polyline complète du parent).

L'effet dépend de `[tronconSelectionneId, sousTronconSelectionneId, etat]` —
il rejoue automatiquement dès qu'une des trois valeurs change.

**Compatibilité rétroactive** — la prop `sousTronconSelectionneId` est
optionnelle avec défaut `null`. Tout code qui utilisait `CarteLeaflet`
sans passer cette prop conserve le comportement historique (zoom uniquement
sur axes parents).


## 17. Phase P12 — Admin intelligente + Chatbot exhaustif (2026-07-04)

Livrée le 2026-07-04. Trois évolutions majeures pour rendre la page
Administration nettement plus utilisable au quotidien et donner au chatbot
une connaissance totale de l'application.

### 17.1 Chatbot — connaissance exhaustive de chaque page (P12.1)

Le `SYSTEM_PROMPT` de `backend/app/api/chatbot.py` a été enrichi pour :

- Détailler explicitement le **contenu de la page Incidents** (filtres
  Accident/Route barrée/Travaux, overlay carte principale, seuil 30 j,
  gestion des sources et des types configurables).
- Ajouter une section **COORDONNÉES GPS DES LIEUX DE RÉFÉRENCE** listant
  les principaux landmarks portuaires avec leurs coordonnées (CARENA,
  Palm Beach, Toyota CFAO, SODECI, Pont Houphouët-Boigny, Seamen's Club,
  bd de Marseille, AGL, Grand Moulin, etc.), au format `LAT: X, LON: Y`
  prêt à coller dans les champs de la page Administration.
- Documenter la nouvelle **fonctionnalité multi-parent** (§ 17.2) et la
  **saisie par nom d'endroit avec autocomplétion** (§ 17.3).

Sur les questions du type « quelles sont les coordonnées de X », le
chatbot répond directement avec le format `LAT: 5.xxxxx, LON: -4.xxxxx`.
Sur « que contient la page Incidents », il décrit maintenant la page
en détail. Fin des « Failed to fetch » liés à l'ignorance du contenu.

### 17.2 Multi-parent — un même tronçon codifié sur plusieurs axes

**Motivation :** un tronçon partagé physiquement par plusieurs axes (typ.
un pont, un carrefour d'entrée du port) était auparavant dupliqué en
plusieurs `SousTroncon` séparés — redondance, double collecte Google,
statistiques divergentes.

**Migration 0016** — table de jonction pure :

```sql
CREATE TABLE axe_sous_troncons (
    axe_id INT NOT NULL REFERENCES troncons(id) ON DELETE CASCADE,
    sous_troncon_id INT NOT NULL REFERENCES sous_troncons(id) ON DELETE CASCADE,
    ordre INT NOT NULL DEFAULT 1,
    PRIMARY KEY (axe_id, sous_troncon_id)
);
CREATE INDEX ix_axe_sous_troncons_axe ON axe_sous_troncons(axe_id, ordre);
```

**Backfill idempotent** : chaque `sous_troncons.troncon_id` existant est
reporté comme lien M2M (parent principal historique). La colonne
`sous_troncons.troncon_id` reste NOT NULL — elle représente désormais le
**parent principal** (routing URL, rétro-compat). La table de jonction
peut lister ce parent principal **plus** d'autres axes secondaires.

**Modèle SQLAlchemy :** la relation `SousTroncon.axes` (M2M via
`secondary=axe_sous_troncons`) donne la liste des axes parents en un seul
`selectinload`. La rétro-compat `Troncon.sous_troncons` (parent principal
uniquement) est préservée.

**Endpoints** (`backend/app/api/administration.py`) :

- `POST /administration/troncons/{axe_id}/sous-troncons` accepte un
  nouveau champ optionnel `axe_ids: list[int]`. L'`axe_id` de l'URL est
  toujours ajouté en parent principal ; les ids fournis dans `axe_ids`
  sont ajoutés en parents secondaires. Validation : chaque id doit
  correspondre à un axe actif avec `est_axe=True` — sinon HTTP 400.
- `PATCH /administration/sous-troncons/{id}` accepte `axe_ids` pour
  **remplacer** la liste des parents (le parent principal reste toujours
  inclus). Anciens liens supprimés, nouveaux insérés.
- `GET /administration/troncons/{axe_id}/sous-troncons` renvoie pour
  chaque sous-tronçon un tableau `axe_ids: number[]` avec tous les
  parents actuels.

**Scheduler et collecte** — inchangés. La règle DEESP « on ne mesure pas
l'axe parent si au moins un sous-tronçon actif existe » reste appliquée
sur le **parent principal**. Un sous-tronçon partagé est donc mesuré
**une seule fois** (via son parent principal), et son état colore
**tous les axes** auxquels il est rattaché sur la carte.

**Carte temps réel** (`backend/app/etat/carte.py`) — chaque sous-tronçon
est ajouté à la liste `sous_troncons[]` de **chacun** de ses axes parents
grâce à l'eager-load `selectinload(SousTroncon.axes)`. Repli sur le
parent principal historique si la M2M est vide (données antérieures à
la migration 0016).

**Frontend** (`OngletSousTroncons.tsx`) — panneau ambre « Axes parents
supplémentaires » avec cases à cocher. Coché ⇒ le tronçon apparaît dans
`axe_ids` de la requête POST. Le libellé de succès indique combien
d'axes le tronçon rejoint (« rattaché à 3 axes parents »).

### 17.3 Saisie par nom d'endroit — autocomplétion Nominatim OSM (P12.3)

**Objectif :** plus de clic-sur-carte pénible pour ajouter un axe ou un
tronçon codifié. L'opérateur saisit le nom d'un endroit (ex. « Pharmacie
Palm Beach »), une liste de suggestions OpenStreetMap s'affiche en temps
réel, un clic remplit automatiquement les 4 champs lat/lon.

**Backend** — nouvel endpoint `GET /administration/geocoder?q=<texte>&limit=5`
(tag Swagger *administration*) :

- Proxy Nominatim OSM (mêmes règles ToS que le géocodage des incidents).
- Biais géographique fort sur Abidjan via `viewbox=-4.15,5.10,-3.85,5.55` +
  `countrycodes=ci` + `accept-language=fr`.
- **Cache mémoire process** — 1 h par requête (clé = texte + limit).
- **Rate limit sortant** — 1,1 s minimum entre 2 appels Nominatim.
- **User-Agent** — `FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)`.
- Réponse : `{q, resultats: [{nom_affiche, lat, lon, type, importance}], cache}`.
- Erreur Nominatim → `resultats: []` + champ `erreur` explicite (jamais
  d'exception 5xx renvoyée au navigateur).

**Frontend** — composant `AutocompleteLieu.tsx`
(`frontend/components/administration/`) réutilisable :

- Debounce 350 ms côté client, longueur minimale 3 caractères.
- Discard automatique des réponses obsolètes (protection contre les
  courses lorsque l'utilisateur tape vite).
- Dropdown de suggestions accessible (`role="listbox"`), sélection au
  clavier possible, fermeture au clic extérieur.
- Callback `onSelect(nom, lat, lon)` → le parent stocke lat/lon en état.
- Callback `onEffacer()` invoqué quand la saisie repasse sous 3 chars.

**Refonte `OngletAxes.tsx` et `OngletSousTroncons.tsx`** :

- Nouveau bloc bleu pâle « 📍 Saisie par nom d'endroit (recommandé) »
  contenant les 2 champs Début/Fin avec autocomplétion.
- Le clic-sur-carte legacy est basculé en **mode avancé** replié
  (bouton « ▼ Mode avancé »). Cohabite avec l'autocomplétion :
  l'opérateur peut mixer les deux (autocompléter un point, cliquer
  l'autre).
- Sous-titre revu : « Saisissez le nom des endroits de départ et
  d'arrivée : l'application propose des suggestions OpenStreetMap et
  remplit automatiquement les coordonnées GPS. »
- Note discrète : « Vous pouvez aussi demander les coordonnées d'un
  lieu au chatbot en bas à droite. »

### 17.4 Récapitulatif des changements

| Fichier | Nature | Rôle |
|---------|--------|------|
| `backend/alembic/versions/0016_axe_sous_troncons_m2m.py` | Nouveau | Table M2M + backfill |
| `backend/app/models/models.py` | Modif | Relation `SousTroncon.axes` + Table `axe_sous_troncons` |
| `backend/app/etat/carte.py` | Modif | Iter M2M pour projeter chaque sous sur ses N parents |
| `backend/app/api/administration.py` | Modif | `axe_ids` sur POST/PATCH + endpoint `/geocoder` |
| `backend/app/api/chatbot.py` | Modif | SYSTEM_PROMPT enrichi (Incidents détaillée + landmarks GPS + multi-parent + autocomplete) |
| `frontend/lib/types.ts` | Modif | `axe_ids?` sur `SousTroncon` + `SuggestionLieu` + `ReponseGeocoder` |
| `frontend/lib/api.ts` | Modif | `getGeocoderLieu(q, limit)` exposé sur `api.geocoderLieu` |
| `frontend/components/administration/AutocompleteLieu.tsx` | Nouveau | Composant réutilisable de saisie autocomplétée |
| `frontend/components/administration/OngletAxes.tsx` | Modif | Autocomplete Début/Fin + mode avancé replié |
| `frontend/components/administration/OngletSousTroncons.tsx` | Modif | Autocomplete + panneau ambre multi-parent + mode avancé replié |

### 17.5 Vérification post-déploiement

Console Railway service backend :

```bash
alembic upgrade head
alembic current  # doit afficher 0016 (head)
```

Vérifier la table :

```python
from sqlalchemy import text
from app.db.session import SessionLocal
db = SessionLocal()
n = db.execute(text("SELECT COUNT(*) FROM axe_sous_troncons")).scalar_one()
print(f"{n} liaisons axe-sous-troncon (backfill)")
db.close()
```

Tester le géocodage :

```bash
curl 'https://backend-production-6cbf.up.railway.app/administration/geocoder?q=palm+beach&limit=3'
```

---

## 18. Réordonnancement automatique + sens par axe des sous-tronçons (2026-07-05)

Livré le 2026-07-05. Complète la P12 (multi-parent) en rendant la mécanique
allée/retour **automatique** : un même sous-tronçon codifié (T1A, T1B, pont
partagé…) n'est saisi qu'**une seule fois** dans l'UI, et le système en déduit
sa position et son sens propres à chaque axe parent auquel il est rattaché.

### 18.1 Principe métier

Un axe est un itinéraire orienté (ex. « CARENA → Palm Beach » vs « Palm Beach
→ CARENA »). Un sous-tronçon codifié possède des extrémités fixes
`(lat_debut, lon_debut)` / `(lat_fin, lon_fin)`. Rattaché à plusieurs axes via
la table M2M `axe_sous_troncons` (§ 17.2), il peut être parcouru :

- **dans le sens direct** (lat_debut → lat_fin) pour un axe qui va dans ce
  sens géographique,
- **dans le sens inverse** (lat_fin → lat_debut) pour un axe qui va dans le
  sens opposé.

Le sens est calculé automatiquement en comparant à quelle extrémité l'origine
de l'axe parent est la plus proche (formule Haversine).

### 18.2 Helper partagé — `calculer_sens_par_axe`

Placé dans [backend/app/sources/polyline.py](backend/app/sources/polyline.py)
(module neutre partagé par `administration`, `scheduler` et `etat/carte`, ce
qui évite l'import circulaire) :

```python
def calculer_sens_par_axe(
    axe_lat_origine, axe_lon_origine,
    sous_lat_debut, sous_lon_debut,
    sous_lat_fin, sous_lon_fin,
) -> str:
    """Retourne 'direct' ou 'inverse' selon l'orientation de l'axe."""
```

### 18.3 Réordonnancement automatique par position GPS

Fonction `_reordonner_sous_troncons_par_axe(db, axe_id)` dans
[backend/app/api/administration.py](backend/app/api/administration.py) —
recalcule l'`ordre` de chaque sous-tronçon actif rattaché à un axe, en
utilisant :

1. Le **sens propre à cet axe** (via `calculer_sens_par_axe`)
2. La **distance depuis l'origine de l'axe** au **point d'entrée** du sous
   (donc `lat_debut` si direct, `lat_fin` si inverse)
3. Un tri ascendant → ordre chronologique de traversée dans le sens de l'axe

L'ordre par axe vit dans `axe_sous_troncons.ordre` (colonne existante de la
M2M). L'`ordre` sur `SousTroncon` reste synchronisé avec l'axe principal
(rétro-compat).

**Wiring** — appelé automatiquement dans :
- `POST /administration/troncons/{axe_id}/sous-troncons` : pour tous les axes
  finaux (parent principal + axes secondaires listés dans `axe_ids`).
- `PATCH /administration/sous-troncons/{id}` : pour tous les axes concernés
  (anciens rattachements + nouveaux) si `axe_ids` est modifié.

Résultat : peu importe l'ordre d'ajout des sous-tronçons, chacun apparaît
dans le bon ordre géographique dans chaque axe où il figure — **y compris
un axe inverse** où l'ordre est le miroir de celui du parent principal.

### 18.4 Collecte par (axe, sous, sens) — une seule saisie, deux mesures

**Refonte du scheduler** — [backend/app/collecte/scheduler.py:305](backend/app/collecte/scheduler.py) :

Avant, un sous-tronçon donnait **une seule** requête Google Routes par cycle
(source = `sous.troncon_id`, direction fixée à `lat_debut → lat_fin`).

Après, on itère sur les **paires (axe, sous)** via la table M2M et on
calcule le sens pour chacune :

```python
for sous in sous_troncons_actifs:
    for axe_id in axes_par_sous.get(sous.id, [sous.troncon_id]):
        axe = axes_par_id[axe_id]
        sens = calculer_sens_par_axe(axe.lat_origine, axe.lon_origine, …)
        # → 1 tâche Google par paire, orientée dans le bon sens
        taches.append(_collecter_google_pour_sous_troncon(
            sous, axe_id_contexte=axe_id, sens=sens,
        ))
```

`_collecter_google_pour_sous_troncon` accepte désormais `axe_id_contexte`
et `sens` — quand `sens="inverse"`, origine et destination Google sont
échangées. `Mesure.troncon_id` reçoit l'`axe_id_contexte`, ce qui permet à
chaque axe d'avoir sa propre série de mesures pour un sous partagé.

**Cas concret** — un pont T1X rattaché à l'axe 1 (CARENA→Palm Beach) et à
l'axe 2 (Palm Beach→CARENA) : chaque cycle produit 2 lignes dans `mesures`,
`sous_troncon_id` identique, `troncon_id` différent (1 vs 2), sens Google
opposé. Trafic asymétrique correctement capturé sans duplication de saisie
côté opérateur.

**Impact quota Google** — recalculé dans `_resume_adoption_collecte` :
compte les **liens M2M** actifs (pas juste les sous distincts). Un sous
partagé pèse 2 requêtes/cycle, remonté dans l'estimation temps réel affichée
au moment de la création du sous.

### 18.5 Exposition du sens dans `/carte/etat`

[backend/app/etat/carte.py](backend/app/etat/carte.py) enrichit chaque
entrée `sous_troncons[]` d'un axe parent avec :

- `sens` : "direct" | "inverse"
- `sens_symbole` : "⇢" | "⇠"

Le tri de la liste `sous_troncons[]` par axe utilise l'`ordre` M2M
(recalculé par distance GPS), pas l'`ordre` global du sous — un sous
partagé peut être 3e sur l'axe A et 1er sur l'axe B.

Le sérialiseur admin renvoie aussi un champ `axes: [{id, nom, sens}, …]`
sur chaque sous — utile pour l'UI d'administration.

### 18.6 Frontend — sélecteur repensé

[frontend/components/indicateurs/Selecteurs.tsx](frontend/components/indicateurs/Selecteurs.tsx)
distingue visuellement les 3 catégories via des `optgroup` :

```
━━━ AXES ━━━
🛣️  CARENA → Pharmacie Palm Beach
🛣️  Palm Beach → CARENA
…
━━━ TRONÇONS CODIFIÉS ━━━
   ⇢  [T1A] AGL-Grand Moulin  —  CARENA → Palm Beach
   ⇠  [T1A] AGL-Grand Moulin  —  Palm Beach → CARENA
   ⇢  [T2A] Pont HB  —  CARENA → Palm Beach
━━━ AUTRES ━━━
```

Les types TS `EtatSousTronconCarte.sens/sens_symbole` et
`TronconSousResume.sens` propagent le champ dans toute l'app.

### 18.7 Pas de migration Alembic nécessaire

Toute la logique s'appuie sur des colonnes existantes :
- `axe_sous_troncons(axe_id, sous_troncon_id, ordre)` — migration 0016
- `SousTroncon(lat_debut, lon_debut, lat_fin, lon_fin, ordre)` — migration 0006

`alembic current` reste à `0016` (head).

### 18.8 Vérification post-déploiement

```bash
# Après un cycle de collecte, un sous partagé (ex. sous_troncon_id=42
# rattaché aux axes 1 et 2 dans axe_sous_troncons) doit donner :
SELECT troncon_id, sous_troncon_id, count(*)
FROM mesures
WHERE horodatage > now() - interval '2 hours' AND sous_troncon_id = 42
GROUP BY troncon_id, sous_troncon_id;
-- attendu : 2 lignes (troncon_id=1 et troncon_id=2)
```

Sur la carte, cliquer un tronçon codifié partagé montre le symbole ⇢ ou ⇠
en cohérence avec l'axe sélectionné.

---

## 19. CRUD Admin complet + preview OSRM en direct (2026-07-05)

Livré le 2026-07-05, en complément direct du § 18. Trois blocs
indissociables : listing correct par axe secondaire, édition inline, et
prévisualisation du vrai tracé routier avant validation.

### 19.1 Fix listing — un axe secondaire remonte SES sous-tronçons

Avant : `GET /administration/troncons/{axe_id}/sous-troncons` filtrait
uniquement `WHERE SousTroncon.troncon_id == axe_id` (parent principal).
Conséquence — dans la page Administration, sélectionner l'axe retour
d'un axe partagé affichait « Aucun tronçon défini pour cet axe ».

Correction dans `lister_sous_troncons()`
([backend/app/api/administration.py](backend/app/api/administration.py)) :

```python
ids_via_m2m = db.execute(
    select(axe_sous_troncons.c.sous_troncon_id)
    .where(axe_sous_troncons.c.axe_id == troncon_id)
).scalars().all()
requete = select(SousTroncon).where(or_(
    SousTroncon.troncon_id == troncon_id,   # parent principal (rétro-compat)
    SousTroncon.id.in_(ids_via_m2m),        # axe secondaire via M2M
))
```

Le tri utilise l'`ordre` propre à CET axe stocké dans
`axe_sous_troncons.ordre` (recalculé par distance GPS + sens à chaque
ajout — cf. § 18.3), pas l'`ordre` global du sous-tronçon. Résultat :
l'axe aller et l'axe retour affichent chacun leur liste dans le bon
ordre chronologique de traversée.

### 19.2 PATCH étendu — édition complète des coordonnées

**Backend** — `TronconMaj` et `SousTronconMaj` acceptent désormais les
coordonnées + le passage à/de `est_axe` :

| Endpoint | Champs modifiables |
|----------|--------------------|
| `PATCH /administration/troncons/{id}` | `nom`, `couleur`, `vitesse_ref_kmh`, `est_axe`, `lat_origine`, `lon_origine`, `lat_destination`, `lon_destination`, `distance_m` |
| `PATCH /administration/sous-troncons/{id}` | `code`, `nom_court`, `lat_debut`, `lon_debut`, `lat_fin`, `lon_fin`, `axe_ids` |

Règle appliquée automatiquement quand une coordonnée change :

1. **Polyline recalculée** — OSRM si `settings.osrm_base_url` est défini
   (VM Google Cloud e2-micro § 8.8, en prod permanente), sinon segment
   droit + `distance_haversine_m`.
2. **Distance recalculée** — même règle. Peut être surchargée par
   `distance_m` explicite si fourni.
3. **Réordonnancement automatique** — via
   `_reordonner_sous_troncons_par_axe` (§ 18.3) sur :
   - l'axe modifié quand `PATCH /troncons/{id}` déplace son origine,
   - **tous les axes parents** du sous quand `PATCH /sous-troncons/{id}`
     déplace un endpoint (ordre par-axe conservé cohérent).

**Frontend** — chaque ligne du tableau reçoit un bouton **✏️ Modifier**
qui ouvre un panneau inline avec formulaire pré-rempli. `OngletAxes`
édite nom + couleur + vitesse + 4 coordonnées ; `OngletSousTroncons`
édite code + nom court + 4 coordonnées + cases à cocher des axes
parents (multi-parent live). API calls :
`api.majTroncon(id, payload)` / `api.majSousTroncon(id, payload)` dans
[frontend/lib/api.ts](frontend/lib/api.ts).

### 19.3 Preview OSRM en direct — endpoint dédié

**Endpoint** : `GET /administration/preview-route?lat1&lon1&lat2&lon2`
(tag *administration*).

- Retourne `{polyline, distance_m, distance_km, source}` où
  `source ∈ {"osrm", "haversine"}`.
- Utilise `settings.osrm_base_url` en priorité, repli silencieux
  Haversine si OSRM échoue ou est absent.
- Cache mémoire process 10 min par paire de points (clé arrondie 5
  décimales) — deux points identiques ne re-taperont pas OSRM pendant
  la même session.

**Frontend** — état + fetch **debouncé 350 ms** dans OngletAxes et
OngletSousTroncons dès que `debut && fin` sont posés (via
autocomplétion Nominatim OU clic-carte OU édition inline) :

```typescript
useEffect(() => {
  if (!debut || !fin) return;
  const timer = setTimeout(async () => {
    const r = await api.previewRoute(debut.lat, debut.lon, fin.lat, fin.lon);
    setPreviewPolyline(r.polyline);
    setPreviewSource(r.source);
  }, 350);
  return () => clearTimeout(timer);
}, [debut, fin]);
```

**Composant carte** — `CarteAdmin` accepte deux nouvelles props :
`previewPolyline?: string | null` et
`previewSource?: "osrm" | "haversine" | null`.

- Si `previewSource === "osrm"` → dessine la polyline décodée en trait
  **plein** violet, épaisseur 5, opacité 0.85. Tooltip *« Aperçu du
  tracé routier réel (OSRM) »*.
- Sinon → segment droit **pointillé** violet (comportement historique).
  Tooltip *« Aperçu linéaire (segment droit) »*.

### 19.4 Carte toujours visible dans la page Administration

Avant : le composant `<CarteAdmin>` n'était monté que dans le bloc
`{modeAvance && ...}` — donc invisible pour la méthode par
autocomplétion (celle recommandée pour les opérateurs). Après :
la carte est **toujours affichée** dans les deux onglets, avec :

- Le libellé de description qui reflète l'état :
  *« Placez début + fin pour voir l'aperçu »* → *« Calcul du tracé
  routier en cours… »* → *« Tracé routier OSRM (X.YZ km). Il sera le
  tracé définitif après création »*.
- Le repli linéaire quand OSRM est indisponible : *« Aperçu linéaire
  (X.YZ km à vol d'oiseau) — OSRM indisponible, le tracé final sera
  calculé côté serveur »*.
- Les axes existants affichés en fond (polylines colorées) pour
  situer visuellement le nouveau tronçon dans son contexte.

### 19.5 Propagation aux cartes tierces après création

`PageAdministration` passe désormais son callback `charger` à
`OngletSousTroncons` (prop `onChange`). Après création, modification
ou archivage d'un sous-tronçon :

1. Le sous-tronçon apparaît (ou disparaît) instantanément dans la liste
   locale via `chargerSousTroncons()`.
2. `onChange()` est invoqué → `PageAdministration` recharge
   `api.troncons()` → le state `troncons` remonte au niveau top de la
   page, incluant les nouvelles polylines OSRM déjà persistées en base.
3. Les autres pages (Carte principale, Fiabilité, Incidents) ne
   dépendent PAS de ce callback : elles rechargent leur propre état via
   polling `/carte/etat` (30 s) et push WebSocket au prochain cycle de
   collecte. La nouvelle polyline OSRM y apparaît naturellement.

### 19.6 Récapitulatif fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `backend/app/api/administration.py` | Fix listing M2M + PATCH étendu + endpoint `/preview-route` |
| `frontend/lib/api.ts` | `patchTroncon`, `patchSousTroncon`, `getPreviewRoute` |
| `frontend/components/administration/CarteAdmin.tsx` | Props `previewPolyline`, `previewSource` |
| `frontend/components/administration/OngletAxes.tsx` | Édition inline + carte toujours visible + fetch preview OSRM |
| `frontend/components/administration/OngletSousTroncons.tsx` | Édition inline + prop `onChange` + carte toujours visible + fetch preview OSRM |
| `frontend/components/administration/PageAdministration.tsx` | Passe `onChange={charger}` aux 2 onglets |

Pas de migration Alembic. `alembic current` reste à `0016`.

---

## 20. Autocomplétion cascade — Landmarks PAA → Google Places → Nominatim (2026-07-05)

Livré le 2026-07-05, en réponse au constat que Nominatim OSM ne
retourne pas les points d'intérêt spécifiques du rapport DEESP
(GMA, CIMIVOIRE, ATC Comafrique, SGBCI, DGI, Gare SOTRA Terminus 19,
Libya Oil CI, Pharmacie du port, etc.). Résultat : les opérateurs ne
pouvaient pas placer précisément les bornes de sous-tronçons T1A →
T11 malgré leur nomenclature officielle.

### 20.1 Cascade à 3 niveaux

`GET /administration/geocoder?q=<texte>&limit=5` :

1. **Landmarks PAA** ([backend/app/sources/landmarks_paa.py](backend/app/sources/landmarks_paa.py))
   — dictionnaire curé de 18 points d'intérêt de la zone portuaire
   avec coordonnées relevées manuellement sur Google Maps. Match
   fuzzy sur `nom_canonique` + `alias` (normalisation NFKD + lower).
   Réponse instantanée, aucun appel réseau, aucun coût quota.
2. **Google Places API (New)** (si `GOOGLE_ROUTES_API_KEY` est
   configurée et couvre l'API Places) — même clé que Routes.
   Endpoints utilisés :
   - `POST https://places.googleapis.com/v1/places:autocomplete`
     avec `locationBias.circle` centré Abidjan (rayon 25 km) +
     `regionCode: CI` + `languageCode: fr`.
   - `GET  https://places.googleapis.com/v1/places/{placeId}` avec
     `X-Goog-FieldMask: location,displayName,formattedAddress` pour
     récupérer les coordonnées d'une suggestion.
   Filtre géographique côté serveur : rejette tout résultat hors bbox
   Abidjan élargie (lat 4.9-5.55, lon -4.25 -3.7).
3. **Nominatim OSM** — appelé UNIQUEMENT si les deux premiers niveaux
   n'ont rien renvoyé (aucun coût, aucun bruit). Rate limit sortant
   inchangé (1 req/s ToS OSM).

### 20.2 Landmarks pré-chargés (§ 4.2 du rapport DEESP)

Ordre = sens de traversée de l'axe CARENA → Pharmacie Palm Beach :

| Code | Landmark | Alias fréquents |
|------|----------|-----------------|
| — | CARENA (Chantier Naval, Plateau) | carena, chantier naval carena |
| T1A | Grands Moulins d'Abidjan (GMA) | gma, grand moulin abidjan |
| T2 | Commissariat spécial du port | commissariat special, commissariat 4e |
| T3 | CIMIVOIRE (Ciments de Côte d'Ivoire) | cimivoire, ciments cote d'ivoire |
| T4 | Carrefour Seamen's Club | seamen, seamens club |
| T5 | Pharmacie du port | — |
| T6 | Unilever Côte d'Ivoire | unilever, unilever ci |
| T7 | ATC Comafrique | atc, comafrique |
| T8 | SGBCI (Société Générale — Port) | sgbci, societe generale port |
| T9 | DGI (Direction Générale des Impôts) | dgi, direction generale impots |
| T10 | Gare SOTRA — Terminus 19 | sotra 19, gare sotra 19 |
| T11 | Siège social Libya Oil CI | libya oil, lybia oil |
| — | Pharmacie Palm Beach | palm beach, palmbeach |
| T1B | TOYOTA CFAO (Treichville) | cfao motors, toyota cfao |
| T1D | Agence SODECI (Zone 4) | sodeci, sodeci vridi |
| — | Pont Houphouët-Boigny | pont hb, pont houphouet |
| — | AGL Terminal (ex-Bolloré) | agl, agl terminal |
| — | Outillage Port d'Abidjan | outillage port |

Pour ajouter un landmark : éditer la liste `LANDMARKS_PAA` dans
`landmarks_paa.py`. Aucune migration nécessaire — la liste est
chargée en mémoire au démarrage.

### 20.3 Frontend — badges de provenance

[AutocompleteLieu.tsx](frontend/components/administration/AutocompleteLieu.tsx)
affiche pour chaque suggestion un badge de couleur indiquant la
source :

- **★ PAA** (fond navy) — landmark curé, coord validée Google Maps.
- **G** (fond bleu Google) — Google Places API.
- **OSM** (fond gris) — Nominatim (repli).

`SuggestionLieu.source` est désormais typé
(`"landmark_paa" | "google_places" | "nominatim"`) dans
[frontend/lib/types.ts](frontend/lib/types.ts).

### 20.4 Activation de Google Places API

Pour bénéficier du niveau 2 en production, il faut activer l'**API
Places (New)** dans la Google Cloud Console du projet qui héberge la
clé `GOOGLE_ROUTES_API_KEY`. Aucun changement de variable
d'environnement Railway n'est nécessaire — la même clé est réutilisée.

**Vérification** :

```bash
# Doit renvoyer au moins un résultat avec source=google_places
# (en plus des landmarks curés)
curl 'https://backend-production-6cbf.up.railway.app/administration/geocoder?q=treichville+marche&limit=5'
```

Sans activation de Places API, le service se contentera des 2 autres
niveaux (Landmarks PAA + Nominatim) — la cascade dégrade gracieusement.

### 20.5 Impact quota Google

Chaque suggestion Google Places = 2 appels facturés :
`Autocomplete (Session)` + `Place Details`.

Ordre de grandeur : ~5 suggestions × 2 = 10 appels par recherche
opérateur. Cache mémoire 1 h par `(q, limit)` → un opérateur qui
retape la même requête ne fait pas d'appel supplémentaire.

Ce budget est **complètement séparé** du quota Routes (250 req/jour)
pour la collecte scheduler — ces deux APIs partagent la clé mais ont
des compteurs indépendants côté Google.

---

## 21. Recalibrage GPS depuis fichiers GPX terrain (2026-07-05)

### 21.1 Contexte

Les coordonnées des landmarks, axes principaux et sous-tronçons codifiés
étaient initialement relevées sur **Google Maps** (position du bâtiment ou
du trottoir). Les 26 fichiers GPX enregistrés le **2026-06-22** avec
BasicAirData GPS Logger fournissent les positions réelles **sur la route**.

Le recalibrage a deux effets :
1. Les **polylines OSRM** suivent le vrai chemin routier (pas un décalage
   de 20-50 m sur le trottoir d'en face).
2. Les **futures recherches** via l'autocomplétion retournent des points
   alignés sur la chaussée.

### 21.2 Source de vérité — 26 fichiers GPX

| Direction | Fichiers | Segments couverts |
|-----------|----------|-------------------|
| Aller (CARENA → Palm Beach) | 12 fichiers | T1C → T11 complet |
| Retour (Palm Beach → CARENA) | 11 fichiers | T11 → T1A complet |
| Axe 2 (Toyota CFAO ↔ Seamen's) | 2 fichiers | T1B aller + retour |
| Axe 3 (SODECI → Gendarmerie) | 1 fichier | T1D aller |

Chaque point de jonction (landmark) est la **moyenne** des coordonnées
de fin du segment N (aller) et de début du segment N+1 (aller), plus les
données retour quand disponibles (2 à 4 mesures par point).

### 21.3 Coordonnées recalibrées

| Landmark | Lat (ancien) | Lon (ancien) | Lat (GPX) | Lon (GPX) |
|----------|-------------|-------------|-----------|-----------|
| CARENA | 5.310540 | -4.019180 | **5.317375** | **-4.024489** |
| GMA | 5.302870 | -4.014980 | **5.306613** | **-4.021423** |
| Commissariat | 5.298830 | -4.013220 | **5.303883** | **-4.023036** |
| CIMIVOIRE | 5.294810 | -4.010580 | **5.298595** | **-4.015156** |
| Seamen's Club | 5.291470 | -4.005190 | **5.293656** | **-4.008266** |
| Pharmacie du port | 5.288820 | -4.001040 | **5.289099** | **-4.008330** |
| Unilever | 5.284120 | -3.998720 | **5.282904** | **-4.008375** |
| ATC Comafrique | 5.279830 | -3.996650 | **5.275854** | **-4.008499** |
| SGBCI | 5.276680 | -3.995280 | **5.268585** | **-4.004069** |
| DGI | 5.273420 | -3.993710 | **5.264824** | **-3.999947** |
| Terminus 19 | 5.269660 | -3.991470 | **5.256348** | **-3.997206** |
| Libya Oil | 5.264780 | -3.988030 | **5.257508** | **-3.986315** |
| Palm Beach | 5.259040 | -3.984020 | **5.258348** | **-3.981822** |
| Toyota CFAO | 5.294070 | -4.017190 | **5.294394** | **-4.006206** |
| SODECI | 5.286370 | -3.997900 | **5.293730** | **-4.000654** |

### 21.4 Fichiers modifiés

| Fichier | Rôle |
|---------|------|
| `backend/app/sources/landmarks_paa.py` | 19 landmarks recalibrés + ajout Gendarmerie du port |
| `backend/app/sources/coordonnees.py` | 4 points d'extrémité des axes recalibrés |
| `backend/scripts/recalibrer_coords_gpx.py` | Script Railway Console (MAJ coords + suppression mesures + OSRM) |

### 21.5 Procédure de déploiement

```powershell
# 1. Commit et deploy backend
cd backend && railway up --service backend && cd ..

# 2. Console Railway — exécuter le script de recalibrage
python -m scripts.recalibrer_coords_gpx

# 3. Vérifier les polylines
python -m app.complete_troncons
```

Le script `recalibrer_coords_gpx.py` effectue en une seule commande :
1. MAJ des coordonnées des 14 sous-tronçons (T1C→T11, T1B, T1D)
2. MAJ des coordonnées des 6 axes principaux
3. Suppression des mesures collectées avec les anciennes coordonnées
4. Régénération des polylines OSRM (si OSRM_BASE_URL est configurée)

### 21.6 Règle pour les futurs ajouts de tronçons

Les fichiers GPX terrain sont désormais la **source de vérité** pour les
coordonnées des landmarks de la zone portuaire. Pour ajouter un nouveau
sous-tronçon :

1. Utiliser l'autocomplétion dans la page Administration (les landmarks
   PAA retournent les coordonnées GPS recalibrées).
2. Si le landmark n'existe pas dans la liste, enregistrer un GPX terrain
   avec BasicAirData GPS Logger et extraire les premier/dernier points.
3. Ajouter le nouveau landmark dans `backend/app/sources/landmarks_paa.py`.

---

## 22. Isolation mesures axe / sous-tronçon (2026-07-05)

### 22.1 Problème

Quand un axe possède des sous-tronçons actifs, le scheduler ne mesure
**que** les sous-tronçons (§ 4.8). Chaque mesure est stockée avec
`Mesure.troncon_id = axe_id_contexte` ET `Mesure.sous_troncon_id = sous.id`.

Les requêtes SQL d'indicateurs filtraient sur `troncon_id` sans exclure
les mesures de sous-tronçons → les durées courtes (ex. 49 s pour 0,6 km)
polluaient les stats de l'axe complet (ex. 24 min pour 14,9 km), tirant
les minimums vers des valeurs absurdes.

### 22.2 Règle appliquée

Toute requête visant les **indicateurs au niveau axe** (min/moyen/max,
taux congestion, séries, matrices, RAG chatbot) doit inclure :

```python
Mesure.sous_troncon_id.is_(None)
```

sauf si un `sous_troncon_id` explicite est fourni, auquel cas :

```python
Mesure.sous_troncon_id == sous_troncon_id
```

### 22.3 Fichiers corrigés (12 requêtes)

| Fichier | Fonction(s) | Nature du fix |
|---------|-------------|---------------|
| `backend/app/analyse/indicateurs.py` | `calcul_indicateurs()`, `serie_temporelle()` | `else: .where(sous_troncon_id.is_(None))` |
| `backend/app/analyse/rapport_paa.py` | `temps_traversee_par_troncon()`, `matrice_congestion()`, `matrice_temps()`, `serie_graphique()` | `.where(sous_troncon_id.is_(None))` ajouté |
| `backend/app/api/evolution.py` | `_stats_periode_par_troncon()` | `.where(sous_troncon_id.is_(None))` dans la clause WHERE |
| `backend/app/api/predire.py` | source 2 mesures 30 j (heure optimale) | `else: conds_m.append(…is_(None))` |
| `backend/app/predicteur/profils.py` | Google ±15 min, mesures jour_type 7 j, `_stats_periode()` | 3 occurrences corrigées |
| `backend/app/rag/contexte.py` | `recuperer_etat_trafic()`, `recuperer_temps_traversee()`, `recuperer_statistiques_semaine()` | `.where(sous_troncon_id.is_(None))` |

### 22.4 Fichier déjà correct

`backend/app/etat/carte.py` (ligne 84) filtrait déjà
`Mesure.sous_troncon_id.is_(None)` pour l'état carte — aucune
modification nécessaire.

### 22.5 Règle pour les futurs développements

Toute nouvelle requête sur la table `mesures` qui agrège au niveau axe
**doit** inclure `Mesure.sous_troncon_id.is_(None)` dans sa clause WHERE.
Seules les requêtes ciblant explicitement un sous-tronçon utilisent
`Mesure.sous_troncon_id == id`.

---

## 23. Ordre d'affichage officiel DEESP des sous-tronçons (2026-07-05)

### 23.1 Contexte

L'ancien algorithme de `_reordonner_sous_troncons_par_axe` calculait l'ordre
par **distance Haversine** depuis l'origine de l'axe. Cette méthode échouait
quand des sous-tronçons sont proches de l'origine à vol d'oiseau mais
distants le long de la route (ex. T1C et T1A proches en latitude, mais T1C
est traversé en premier sur l'axe 1 CARENA → Palm Beach).

### 23.2 Ordre officiel DEESP par axe

L'ordre a été fixé selon le rapport DEESP et les traces GPX terrain :

| Axe (id) | Sens | Séquence |
|----------|------|----------|
| 1 | CARENA → Palm Beach (aller) | T1C → T1A → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 |
| 2 | Palm Beach → CARENA (retour) | T11 → T10 → T9 → T8 → T7 → T6 → T5 → T4 → T3 → T2 → T1A → T1C |
| 3 | Toyota CFAO → Palm Beach (aller) | T1B → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 |
| 4 | Palm Beach → Toyota CFAO (retour) | T11 → T10 → T9 → T8 → T7 → T6 → T5 → T4 → T1B |
| 5 | SODECI → Palm Beach (aller) | T1D → T7 → T8 → T9 → T10 → T11 |
| 6 | Palm Beach → SODECI (retour) | T11 → T10 → T9 → T8 → T7 → T1D |

### 23.3 Implémentation

**Dictionnaire `_ORDRE_DEESP_PAR_AXE`** dans
[backend/app/api/administration.py](backend/app/api/administration.py) —
pour chaque axe officiel (id 1-6), la liste ordonnée des codes de
sous-tronçons dans le sens de circulation.

**`_reordonner_sous_troncons_par_axe()`** — refonte :
- **Axes 1-6** : tri par position dans la séquence DEESP officielle.
  Un code absent de la séquence est placé à la fin (ordre 999).
- **Axes > 6** (créés via Administration) : tri par distance GPS
  Haversine depuis l'origine (comportement précédent conservé).

**Script de déploiement** :
```bash
# Console Railway — appliquer l'ordre DEESP sur les données existantes
python -m scripts.reordonner_sous_troncons_deesp
```

### 23.4 Effet sur l'affichage

Le panneau latéral de la page **Accueil / Carte** affiche désormais les
sous-tronçons dans l'ordre de traversée DEESP officiel pour chaque axe.
L'axe aller et l'axe retour affichent la même liste de sous-tronçons
mais dans l'ordre inverse (sens de circulation).

---

## 24. Agrégation axe = somme des sous-tronçons (2026-07-06)

### 24.1 Problème

Quand un axe possède des sous-tronçons actifs, le scheduler mesure
**uniquement** les sous-tronçons (§ 4.8). Chaque mesure porte
`Mesure.sous_troncon_id = sous.id`. Toutes les requêtes d'indicateurs
au niveau axe filtraient `Mesure.sous_troncon_id.is_(None)` (§ 22),
ce qui retournait **0 mesures** pour les axes décomposés → KPI vides,
courbes vides, matrices vides.

### 24.2 Solution — module `backend/app/analyse/aggregation.py`

Nouveau module central qui fournit les fonctions d'agrégation :

| Fonction | Rôle |
|----------|------|
| `get_sous_ids_pour_axe(db, axe_id)` | IDs des sous-tronçons actifs via M2M + repli parent principal |
| `axe_a_sous_troncons(db, axe_id)` | Booléen — l'axe a-t-il des sous-tronçons actifs ? |
| `distance_ref_sous_troncons(db, axe_id)` | Somme des distances des sous-tronçons (pour T_ref) |
| `agreger_mesures_axe(db, axe_id, debut, fin, ...)` | Agrège les mesures par créneau (date, heure) → `MesureAgregee` |
| `agreger_durees_par_creneau(db, axe_id, debut, fin, ...)` | Version légère → tuples `(horodatage, duree_s, source)` |

**Dataclass `MesureAgregee`** — compatible avec les attributs de `Mesure` :
`horodatage`, `duree_trafic_s`, `est_congestionne`, `pourcentage_rouge/orange/vert`,
`aberrante`, `source`, `nb_sous_presents`, `nb_sous_attendus`.

### 24.3 Règles d'agrégation

| Indicateur | Règle |
|------------|-------|
| **Durée axe** | `SUM(duree_trafic_s)` des sous-tronçons présents dans le créneau |
| **Congestion** | `ANY(est_congestionne=True)` → axe congestionné ; `ALL(est_congestionne=False)` → axe fluide |
| **% rouge/orange/vert** | Moyenne pondérée par la distance de chaque sous-tronçon |
| **Distance de référence** | `SUM(sous_troncon.distance_m)` |
| **T_ref 50 km/h** | Calculé depuis la distance agrégée |

### 24.4 Fichiers modifiés (7 fichiers backend)

Chaque fichier détecte `axe_a_sous_troncons(db, id)` et branche vers
l'agrégation si vrai, sinon conserve le comportement original.

| Fichier | Fonctions modifiées |
|---------|---------------------|
| `backend/app/analyse/indicateurs.py` | `calcul_indicateurs()`, `serie_temporelle()` |
| `backend/app/analyse/rapport_paa.py` | `matrice_congestion()`, `matrice_temps()` |
| `backend/app/api/evolution.py` | `_stats_periode_par_troncon()` |
| `backend/app/api/predire.py` | `get_heure_optimale()` (source 2 + ref_dist) |
| `backend/app/predicteur/profils.py` | `_prediction_google()`, `_prediction_jour_type()`, `_stats_mesures_periode()` |
| `backend/app/rag/contexte.py` | `recuperer_etat_trafic()`, `recuperer_temps_traversee()`, `recuperer_statistiques_semaine()` |
| `backend/app/api/chatbot.py` | Section SYSTEM_PROMPT « AGRÉGATION AXE = SOMME DES TRONÇONS » |

### 24.5 Effet sur les pages

| Page | Avant | Après |
|------|-------|-------|
| **Indicateurs** | KPI vides pour les axes décomposés | Temps moyen/min/max = somme des sous-tronçons |
| **Rapport DEESP — Matrice congestion** | Toutes cellules vides | Pastilles rouge/vert agrégées (rouge = ≥ 1 sous congestionné) |
| **Rapport DEESP — Matrice temps** | Toutes cellules vides | Durées `mm:ss` = somme des durées sous-tronçons |
| **Heure optimale** | Créneaux vides | Durées par créneau = somme des sous-tronçons |
| **Temps de traversée** | Estimation vide | Cascade Google/profils avec agrégation |
| **Chatbot RAG** | Données manquantes | Valeurs agrégées temps réel injectées |

### 24.6 Corrections UX mobile

| Fix | Fichier | Détail |
|-----|---------|--------|
| Overflow multi-parent admin | `OngletSousTroncons.tsx` | `max-h-[40vh] overflow-y-auto` sur le grid des axes parents |
| Scroll carte insuffisant | `PageCarte.tsx` | `h-[45vh]` → `h-[55vh]` pour le panneau latéral mobile |

### 24.7 Règle pour les futurs développements

Toute nouvelle requête agrégant des mesures au niveau axe **doit** vérifier
`axe_a_sous_troncons(db, axe_id)`. Si vrai, utiliser
`agreger_mesures_axe()` ou `agreger_durees_par_creneau()` au lieu de
requêter directement `Mesure` avec `sous_troncon_id.is_(None)`.

---

## 25. Rapport DEESP — Tableau 16 et MatriceCongestion limités aux tronçons codifiés (2026-07-07)

### 25.1 Motivation

Conformément à la méthodologie DEESP, la **congestion s'évalue à la granularité
des tronçons codifiés** (T1A, T1B, T1C…), jamais au niveau des axes parents.
Avant cette correction :

- Le **Tableau 16** affichait deux sections : « Congestion par axe » (injectée
  par la « Passe 1 » du backend) + « Congestion par tronçon codifié ». Les axes
  parents ne devaient pas y figurer.
- La **MatriceCongestion** proposait axes ET sous-tronçons dans son sélecteur.
  L'analyse fine n'a de sens qu'au niveau sous-tronçon.
- Les fonctions `temps_traversee_par_troncon()` et `serie_graphique()` filtraient
  `sous_troncon_id.is_(None)` pour tous les tronçons → retournaient 0 résultats
  pour les axes décomposés (dont toutes les mesures portent un `sous_troncon_id`).

### 25.2 Changements backend

**`backend/app/analyse/rapport_paa.py`** :

1. **Suppression de la Passe 1** dans `troncons_congestionnes()` — le bloc de
   ~24 lignes qui construisait `axes_avec_sous` et `creneaux_axe` pour injecter
   des entrées axe-level dans le résultat a été entièrement retiré. La fonction
   ne retourne plus que des entrées sous-tronçon.

2. **`temps_traversee_par_troncon()`** — branche sur `axe_a_sous_troncons()` :
   - Axes sans sous-tronçons actifs → lecture directe `Mesure` avec
     `sous_troncon_id.is_(None)` (comportement historique).
   - Axes avec sous-tronçons actifs → `agreger_durees_par_creneau()` qui somme
     les mesures sous-tronçon par créneau `(date_locale, heure_locale)`.

3. **`serie_graphique()`** — même branchement. Axes décomposés → agrégation SUM
   depuis les mesures sous-tronçon via `agreger_durees_par_creneau()`.

### 25.3 Changements frontend

**`frontend/components/rapport/TableauZonesCongestionnees.tsx`** :

- Suppression de la fonction `LigneAxe` et du bloc « Congestion par axe »
  (table HTML + h3).
- Suppression de la variable `entreesAxes` (filtre sur `sous_troncon_id === null`).
- La variable `entrees` filtre désormais **uniquement** les entrées avec
  `sous_troncon_id !== null` (tronçons codifiés uniquement).
- Card renommée : « Tableau 16 — Tronçons congestionnés (règles DEESP) ».
- Description mise à jour sans référence aux axes.
- L'export CSV et le bouton PDF portent uniquement sur `entrees`.

**`frontend/components/rapport/MatriceCongestion.tsx`** :

- Le sélecteur `<select>` ne liste plus les axes parents : uniquement les
  sous-tronçons via `troncons.flatMap((a) => a.sous_troncons ?? [])`.
- Label changé de « Tronçon » à « Tronçon codifié ».
- Ajout d'un `useEffect` d'auto-sélection : au premier chargement, sélectionne
  automatiquement le premier sous-tronçon disponible.
- Guard dans `charger()` : si des sous-tronçons existent mais qu'aucun n'est
  sélectionné (pendant l'auto-sélection), `charger` retourne immédiatement pour
  éviter une requête avec `troncon_id` sans `sous_troncon_id`.

### 25.4 Chatbot

Le `SYSTEM_PROMPT` de `backend/app/api/chatbot.py` a été complété : le Tableau 16
et la matrice des congestions n'affichent QUE les tronçons codifiés — jamais les
axes parents.

### 25.5 Règle pour les futurs développements

- `troncons_congestionnes()` ne doit jamais produire d'entrées pour les axes
  parents (`sous_troncon_id = null`). Toute congestion s'évalue au niveau du
  sous-tronçon qui porte les mesures.
- `temps_traversee_par_troncon()` et `serie_graphique()` **doivent** toujours
  brancher sur `axe_a_sous_troncons()` avant de lire `Mesure` directement.
- `MatriceCongestion` ne doit proposer que des sous-tronçons dans son sélecteur.

---

## 26. Fix MatriceCongestion multi-parent + pourcentages + précision popup (2026-07-07)

### 26.1 Problèmes identifiés

Trois bugs interconnectés empêchaient l'affichage correct des données de congestion
pour les sous-tronçons multi-parents (migration 0016) :

1. **Validation multi-parent défaillante** — Les endpoints `/rapport/matrice-congestion`
   et `/rapport/matrice-temps` vérifiaient uniquement `sous.troncon_id == troncon_id`
   (parent principal). Quand un sous-tronçon était rattaché à un axe secondaire via la
   table M2M `axe_sous_troncons`, la validation échouait avec HTTP 404.

2. **Double multiplication des pourcentages** — La fonction `matrice_congestion()`
   multipliait par 100 les pourcentages (`pct_rouge * 100`), mais les valeurs étaient
   déjà stockées en base comme 0-100 (et non 0-1). Résultat : 50% s'affichait comme
   5000%.

3. **Perte de précision des temps courts** — La fonction `construirePopupSousTroncon()`
   utilisait `Math.round(duree_s / 60)` pour afficher les temps, arrondissant 49 s à
   "1 min" au lieu d'utiliser `formaterDuree()` qui affiche "49 s".

### 26.2 Corrections backend

#### `backend/app/api/rapport.py` — Validation multi-parent (2 endpoints)

**Lignes ~420-442** (`GET /rapport/matrice-congestion`) et **lignes ~850-872**
(`GET /rapport/matrice-temps`) :

```python
# AVANT (bug) — rejetait les axes secondaires
sous = db.query(SousTroncon).filter_by(id=sous_troncon_id, actif=True).first()
if not sous or sous.troncon_id != troncon_id:
    raise HTTPException(404, "Sous-tronçon introuvable ou ne correspond pas à l'axe")

# APRÈS (fix) — vérifie aussi la table M2M
from sqlalchemy import select
from app.models.models import axe_sous_troncons as m2m

sous = db.query(SousTroncon).filter_by(id=sous_troncon_id, actif=True).first()
if not sous:
    raise HTTPException(404, "Sous-tronçon introuvable")

# Vérifie parent principal OU lien M2M
if sous.troncon_id != troncon_id:
    lien_m2m = db.execute(
        select(m2m.c.axe_id).where(
            m2m.c.axe_id == troncon_id,
            m2m.c.sous_troncon_id == sous_troncon_id,
        )
    ).first()
    if not lien_m2m:
        raise HTTPException(404, "Sous-tronçon ne correspond pas à cet axe")
```

#### `backend/app/analyse/rapport_paa.py` — Fix pourcentages (fonction `matrice_congestion()`)

**Deux chemins de calcul corrigés :**

1. **Axes décomposés** (agrégation via `aggregation.py`, ligne ~472) :
   ```python
   # AVANT
   pct_rouge = round(agg.pourcentage_rouge * 100) if agg.pourcentage_rouge is not None else None
   
   # APRÈS
   pct_rouge = round(agg.pourcentage_rouge, 1) if agg.pourcentage_rouge is not None else None
   ```

2. **Axes simples** (requête directe, ligne ~517) :
   ```python
   # AVANT
   pct_rouge = round(m.pourcentage_rouge * 100) if m.pourcentage_rouge is not None else None
   
   # APRÈS
   pct_rouge = round(m.pourcentage_rouge, 1) if m.pourcentage_rouge is not None else None
   ```

**Raison :** Les pourcentages sont stockés en base comme **0-100** (calculés dans
`backend/app/sources/google_routes.py` ligne ~115 : `pct_rouge = round(distance_rouge * 100.0 / distance_totale, 2)`).
Multiplier à nouveau par 100 donnait des valeurs absurdes (5000% au lieu de 50%).

### 26.3 Corrections frontend

#### `frontend/components/carte/CarteLeaflet.tsx` — Précision popup (lignes 838-865)

**Fonction `construirePopupSousTroncon()` :**

```typescript
// AVANT (bug) — arrondissait les temps courts
const tempsRef = s.temps_reference_50kmh_s
  ? Math.round(s.temps_reference_50kmh_s / 60)
  : null;
const tempsObs = s.derniere_mesure?.duree_trafic_s
  ? Math.round(s.derniere_mesure.duree_trafic_s / 60)
  : null;

// HTML avec suffixe hardcodé
${tempsRef !== null ? `${labelTempsRef} : ${tempsRef} min` : ""}
${tempsObs !== null ? `<div>${labelTempsObs} : <strong>${tempsObs} min</strong></div>` : ""}

// APRÈS (fix) — utilise formaterDuree() pour la précision
const tempsRef = formaterDuree(s.temps_reference_50kmh_s);
const tempsObs = formaterDuree(s.derniere_mesure?.duree_trafic_s);

// HTML sans suffixe (formaterDuree inclut l'unité)
${tempsRef ? `${labelTempsRef} : ${tempsRef}` : ""}
${tempsObs ? `<div>${labelTempsObs} : <strong>${tempsObs}</strong></div>` : ""}
```

**Bénéfice :** Les segments courts comme T1A (49 s) affichent désormais "49 s" au
lieu de "1 min". Pour les segments longs, `formaterDuree()` affiche "3 min 45 s"
ou "1 h 23" (si ≥ 60 min).

#### Ajout symbole de sens (⇢ / ⇠) — amélioration UX

**Popup carte** (ligne 848) :

```typescript
const sensSymbole = s.sens_symbole ? ` ${s.sens_symbole}` : "";
return `<div class="font-bold text-base">${sensSymbole} ${s.code} — ${s.nom_court}</div>`;
```

**Panneau latéral** (`frontend/components/carte/PanneauTroncons.tsx`, ligne ~298) :

```typescript
{sous.sens_symbole && (
  <span className="shrink-0 text-base text-paa-navy-600 dark:text-paa-blue-300">
    {sous.sens_symbole}
  </span>
)}
```

Les sous-tronçons multi-parents affichent désormais leur sens de circulation
(⇢ direct, ⇠ inverse) dans le contexte de chaque axe parent.

### 26.4 Impact utilisateur

| Problème | Avant | Après |
|----------|-------|-------|
| **Matrice sous-tronçon secondaire** | HTTP 404 → matrice vide | ✅ Données affichées correctement |
| **Pourcentage congestion** | 5000% (50% × 100) | ✅ 50% (valeur correcte) |
| **Temps T1A (49 s)** | "1 min" (arrondi) | ✅ "49 s" (précision conservée) |
| **Sens multi-parent** | Pas affiché | ✅ Symbole ⇢/⇠ visible |

### 26.5 Fichiers modifiés

| Fichier | Lignes | Nature du fix |
|---------|--------|---------------|
| `backend/app/api/rapport.py` | ~420-442, ~850-872 | Validation M2M multi-parent (2 endpoints) |
| `backend/app/analyse/rapport_paa.py` | ~472, ~517 | Suppression *100 (2 chemins de calcul) |
| `frontend/components/carte/CarteLeaflet.tsx` | ~838-865 | formaterDuree() + sens_symbole popup |
| `frontend/components/carte/PanneauTroncons.tsx` | ~285-340 | sens_symbole panneau latéral |

### 26.6 Tests de vérification

```bash
# 1. Backend local — tester validation multi-parent
curl -s "http://localhost:8000/rapport/matrice-congestion?campagne=2026-07&troncon_id=2&sous_troncon_id=8" | jq '.troncon_id, .sous_troncon_id'
# Doit retourner : 2, 8 (plus de 404)

# 2. Vérifier pourcentages dans la réponse
curl -s "http://localhost:8000/rapport/matrice-congestion?campagne=2026-07&troncon_id=1&sous_troncon_id=8" \
  | jq '.tranches[0].par_date[0] | {pct_rouge, pct_orange}'
# pct_rouge doit être entre 0-100, pas 0-10000

# 3. Frontend — ouvrir http://localhost:3000 et cliquer un sous-tronçon court (T1A)
# Le popup doit afficher "49 s" au lieu de "1 min"
# Le panneau latéral doit afficher le symbole ⇢ ou ⇠
```

### 26.7 Règle pour les futurs développements

- **Validation sous-tronçon** : tout endpoint acceptant `sous_troncon_id` +
  `troncon_id` **doit** vérifier le lien M2M `axe_sous_troncons` si le parent
  principal ne correspond pas. Ne jamais assumer que `sous.troncon_id == troncon_id`.
  
- **Pourcentages Google Maps** : les colonnes `Mesure.pourcentage_rouge/orange/vert`
  sont déjà en **0-100**. Ne jamais multiplier par 100 lors de l'affichage.
  
- **Temps courts** : utiliser systématiquement `formaterDuree()` au lieu de
  `Math.round(s / 60)` pour préserver la précision des segments < 60 secondes.
  
- **Multi-parent UX** : tout affichage de sous-tronçon devrait inclure
  `sens_symbole` quand disponible pour clarifier le sens de circulation.

---

## 27. Fix seuils congestion mois partiel + click aller/retour carte (2026-07-07)

### 27.1 Seuils congestion inatteignables en début de mois

**Problème :** `seuils_congestion()` dans `rapport_paa.py` calculait les seuils
sur toute la plage demandée (ex. juillet complet = 31 jours) alors qu'on n'avait
que 7 jours de données réelles. Résultat : `seuil_jour=3` (≥ 3 occurrences sur un
même jour de la semaine) — impossible quand il n'y a eu qu'un seul lundi.

**Fix :** `fin_utc` est cappée à `min(fin_utc, now())` — les seuils sont calculés
sur la durée effective des données, pas sur le futur. Au 7 juillet : `nb_jours=7`,
`facteur=0.25`, `seuil_jour=1`, `seuil_semaine=2` — le Tableau 16 affiche les
résultats dès la première semaine de collecte.

**Fichier :** `backend/app/analyse/rapport_paa.py` — fonction `seuils_congestion()`.

### 27.2 Click aller/retour indépendant sur la carte

**Problème :** cliquer un tronçon aller puis le retour du même axe semblait ne
rien faire visuellement car :
1. `openPopup()` était appelé pendant l'animation `flyToBounds` (0.8 s) → le
   popup ne s'affichait pas ou se fermait immédiatement.
2. Cliquer le même tronçon deux fois ne re-déclenchait pas l'effet React
   (même valeur de `selectionId`).

**Fix :**
- Ajout d'un **compteur de séquence** `selectionSeq` incrémenté à chaque clic,
  ajouté aux dépendances de l'effet 4 de `CarteLeaflet`. Chaque clic force le
  re-trigger même si le tronçon ne change pas.
- **Délai de 850 ms** avant `openPopup()` pour attendre la fin de `flyToBounds`.

**Fichiers modifiés :**

| Fichier | Modification |
|---------|-------------|
| `frontend/components/carte/PageCarte.tsx` | `selectionSeq` (state + ref), incrémenté à chaque clic, passé à `CarteLeaflet` |
| `frontend/components/carte/CarteLeaflet.tsx` | Prop `selectionSeq`, ajoutée aux deps de l'effet 4, `setTimeout(openPopup, 850)` |

---

## 28. Temps axe = somme des sous-tronçons — suppression de l'état de congestion propre aux axes (2026-07-07)

### 28.1 Motivation

Quand un axe (ex. « CARENA → Palm Beach ») est décomposé en sous-tronçons codifiés
(T1C, T1A, T2, T3…), le scheduler ne mesure **plus l'axe parent** — il mesure chaque
sous-tronçon individuellement (§ 4.8). Afficher un état de congestion et une source
Google au niveau de l'axe parent dans le panneau latéral et dans les popups était donc
**trompeur** : ces valeurs étaient soit nulles (aucune mesure récente), soit incohérentes
avec la granularité fine.

### 28.2 Changements backend — `backend/app/etat/carte.py`

Pour les axes **avec au moins un sous-tronçon actif** (branche `if sous_serialises`),
le backend ne remonte plus de classe de congestion ni de pourcentages de couleur au
niveau de l'axe :

```python
# Axe avec sous-tronçons :
"classe_congestion": None,   # pas de congestion propre à l'axe
"libelle_classe": None,
"motif_congestion": None,
"couleur_google": {
    "pourcentage_rouge": None,
    "pourcentage_orange": None,
    "pourcentage_vert": None,
},
```

Le champ `derniere_mesure.duree_trafic_s` de l'axe parent devient la **somme des durées**
des sous-tronçons disponibles :

```python
somme_duree_s = sum(sous.duree_trafic_s for sous in sous_mesures_disponibles)
"source": "somme_troncons"  # distingue clairement l'agrégation de la mesure directe
```

Le champ `couleur_etat` est fixé à `troncon.couleur` (couleur de base de l'axe), plus de
code couleur DEESP à ce niveau.

### 28.3 Changements TypeScript — `frontend/lib/types.ts`

`EtatTronconCarte.classe_congestion` accepte désormais `ClasseCongestion | null`
(ligne 137) — les axes avec sous-tronçons reçoivent `null` depuis l'API.

### 28.4 Changements frontend — `frontend/components/carte/PanneauTroncons.tsx`

**Affichage par axe selon la présence de sous-tronçons :**

| Cas | Avant | Après |
|-----|-------|-------|
| Axe **avec** sous-tronçons | Badge "Congestionné/Fluide" + barre couleur rouge/orange/vert + "Google Routes · HH:MM" | "Temps total : mm:ss (somme des tronçons)" uniquement |
| Axe **sans** sous-tronçons | (inchangé) | Badge état + barre couleur + source + heure |

**KPI compteurs** : les compteurs fluide / congestionné / indéterminé n'incluent **plus**
les axes parents — ils comptent uniquement les **sous-tronçons codifiés**. Un axe sans
sous-tronçons continue d'incrémenter son compteur.

**Point chaud** : le `pointChaud` provient maintenant exclusivement des sous-tronçons
(`tousLesSous`). Plus aucun axe parent n'est candidat.

**Fix TypeScript** : l'appel `libelleClasseCongestion(tr.classe_congestion, locale)` dans
la branche axe sans sous-tronçons utilise `tr.classe_congestion ?? "indetermine"` pour
accepter `null`.

### 28.5 Changements frontend — `frontend/components/carte/CarteLeaflet.tsx`

**Polyline des axes avec sous-tronçons** : couleur `troncon.couleur_etat` (couleur de base,
`#1F4E79` par défaut) au lieu d'une couleur dépendant de `classe_congestion`. Le trait reste
plein et visible (weight 6, opacity 0.95).

**Popup axe avec sous-tronçons** (`construirePopup`) : version simplifiée qui n'affiche plus
ni badge de classe ni couleurs Google ni source. Uniquement :
- Nom de l'axe
- Temps total (somme des sous-tronçons)
- Distance
- Note "Somme des tronçons codifiés (N tronçons)"
- Lien "Voir la fiche détaillée →"

**Heatmap** : le filtre `troncon.classe_congestion !== "congestionne"` continue de fonctionner
car les axes avec sous-tronçons reçoivent `null` — ils sont exclus de la heatmap (seuls les
sous-tronçons congestionnés y contribueraient si la heatmap les intégrait à l'avenir).

**Zoom intelligent** : le tri initial par gravité évalue `a.classe_congestion ?
ORDRE_GRAVITE[…] : 0` — les axes avec `null` sont traités comme gravité 0 (neutre),
seuls les sous-tronçons ou axes sans sous-tronçons peuvent devenir le "point chaud" du zoom.

### 28.6 Règle pour les futurs développements

- Tout composant affichant l'état d'un tronçon **doit** brancher sur
  `(tr.sous_troncons ?? []).length > 0` pour décider s'il affiche la congestion
  propre de l'axe ou la somme des sous-tronçons.
- `tr.classe_congestion === null` signifie « axe décomposé en sous-tronçons » —
  ne jamais afficher de badge de congestion dans ce cas.
- La source `"somme_troncons"` dans `derniere_mesure.source` identifie une
  durée agrégée — ne pas l'afficher avec `libelleSource()` (conçu pour les
  sources API Google/interne/terrain).

---

## 29. Panneau axes en cadre unifié + Page Temps de traversée — mesure créneau courant (2026-07-07)

Deux améliorations UX livrées le 2026-07-07.

### 29.1 PanneauTroncons — cadre unifié par axe

**Fichier :** `frontend/components/carte/PanneauTroncons.tsx`

Chaque axe et l'ensemble de ses sous-tronçons codifiés sont désormais enveloppés
dans un **cadre visuel unique** (`rounded-xl border bg-paa-navy-800/40`) au lieu
d'être des entrées plates empilées. La hiérarchie axe → sous-tronçons est
immédiatement lisible :

- **En-tête du cadre** : nom de l'axe + badge état + distance + temps total
- **Corps** : liste indentée des sous-tronçons (code DEESP + symbole ⇢/⇠ + nom + durée)
- **Séparation visuelle** claire entre les axes sans avoir à deviner les frontières

Ce changement est purement cosmétique — aucune logique métier n'est modifiée.

### 29.2 Fix `_prediction_google` — NameError sur les axes décomposés

**Fichier :** `backend/app/predicteur/profils.py`

**Problème :** dans le chemin `if axe_a_sous_troncons(db, troncon.id)` de
`_prediction_google()`, la variable `duree_s_raw` était utilisée dans le `return
Prediction(...)` commun aux deux branches mais n'était définie que dans le chemin
`else`. Un tronçon avec sous-tronçons actifs déclenchait un `NameError` à chaque
appel de la cascade prédicteur.

**Correction :** ajout de `duree_s_raw = best.duree_trafic_s` immédiatement après
`best = min(mesures_agg, ...)` dans le chemin agrégation.

### 29.3 Page Temps de traversée — bande créneau courant vs MIN/MOY/MAX

**Fichiers :** `backend/app/api/predire.py`, `frontend/components/prediction/PagePrediction.tsx`,
`frontend/lib/types.ts`

#### Principe

La page « Temps de traversée » expose deux niveaux de temporalité différents :

| Bloc UI | Source | Principe |
|---------|--------|---------|
| **Bande « Temps actuel — Xh–Yh »** | `mesure_creneau_actuel` | Mesure Google brute du créneau courant — identique à la cellule de la MatriceCongestion pour cette heure |
| **Cartes MIN / MOY / MAX** | `bornes_7j` → semaine → mois | 7 derniers jours du même type de jour (jour ouvrable / week-end) |

Les deux blocs sont **indépendants** — la bande n'utilise jamais la moyenne 7 jours,
et les cartes n'utilisent jamais la mesure Google instantanée.

#### Nouveau champ backend — `mesure_creneau_actuel`

`GET /predire/resume` retourne désormais un champ `courante.mesure_creneau_actuel` :

```json
{
  "courante": {
    ...
    "mesure_creneau_actuel": {
      "duree_s": 1447,
      "duree_mn": 24
    }
  }
}
```

**Implémentation (`backend/app/api/predire.py`)** : appel séparé à
`_prediction_google(db, troncon, maintenant_utc, fenetre_minutes=65)` — la
fenêtre de 65 min (vs 15 min pour la cascade principale) couvre toute l'heure
courante plus une marge de 5 min pour le jitter du scheduler. Si le scheduler
a tourné à 23h00 et qu'il est 23h50, la mesure de 23h00 (50 min d'écart) est
retrouvée et retournée. C'est exactement la valeur affichée dans la MatriceCongestion
pour le créneau 23h-24h.

Ce champ vaut `null` quand aucune mesure Google n'existe dans les 65 dernières minutes
(démarrage à froid, panne API, hors plage de collecte) — jamais de valeur inventée.

#### Comportement frontend de la bande

| État de `mesure_creneau_actuel` | Affichage |
|----------------------------------|-----------|
| Non null | Durée en `mm:ss`, bordure verte, pastille Google verte pulsante |
| `null` | Texte gris « En attente de mesure Google Maps » — pas de valeur de repli |

#### Cascade de repli MIN / MOY / MAX (conservée)

```typescript
// Cascade: bornes_7j → semaine (même type_jour) → mois (même type_jour)
const minS = bornes?.min_s
  ?? prediction.min_s
  ?? fallbackJo?.min_s ?? fallbackMois?.min_s ?? null;
```

La note source s'adapte dynamiquement : « 7 derniers jours ouvrables » /
« semaine en cours » / « mois en cours » / « référence 50 km/h ».

#### Règle pour les futurs développements

- Ne **jamais** utiliser `bornes_7j` ou les stats semaine/mois pour la bande
  « Temps actuel » — elle représente la valeur instantanée, pas une tendance.
- `mesure_creneau_actuel` est toujours recalculé côté backend à chaque appel
  (pas de cache) — c'est intentionnel pour rester aligné avec la MatriceCongestion.
- Si `mesure_creneau_actuel` est `null`, l'UI préfère un message explicite à
  une valeur de substitution (règle d'or § 5.3 : aucune donnée inventée).

