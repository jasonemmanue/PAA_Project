# FLUIDIS

> Application web qui mesure **combien de temps il faut aujourd'hui** pour relier
> les trois axes routiers stratégiques du Port Autonome d'Abidjan, et qui en garde
> l'historique pour aider les gestionnaires à anticiper les bouchons.

*Projet réalisé pour un hackathon — client : Port Autonome d'Abidjan (PAA).*

---

## Sommaire

- [Carnet d'exécution du hackathon](#-carnet-dexécution-du-hackathon)
- [Refonte critère congestion — couleurs Google Maps DEESP (2026-06-22)](#-refonte-critère-congestion--couleurs-google-maps-deesp-2026-06-22)
0. [Audit de conformité aux 5 étapes du brief jury](#0--audit-de-conformité-aux-5-étapes-du-brief-jury)
   - [0ter. Pourquoi un modèle ML serait un vrai gain (P6.5)](#0ter--pourquoi-un-modèle-de-machine-learning-serait-un-vrai-gain-p65)
   - [0bis. Polylines des tronçons : 2 niveaux de rendu](#0bis--polylines-des-tronçons--2-niveaux-de-rendu)
1. [À quoi ça sert ?](#1--à-quoi-ça-sert-)
2. [Comment ça marche en images](#2--comment-ça-marche-en-images)
3. [Ce qui est livré dans la phase P1](#3--ce-qui-est-livré-dans-la-phase-p1)
4. [Ce qui est livré dans la phase P2](#4--ce-qui-est-livré-dans-la-phase-p2)
5. [Ce qui est livré dans la phase P3](#5--ce-qui-est-livré-dans-la-phase-p3)
6. [Ce qui est livré dans la phase P6.1](#6--ce-qui-est-livré-dans-la-phase-p61)
7. [Déploiement Railway (production)](#7--déploiement-railway-production)
8. [Ce qui est livré dans la phase P4 (frontend)](#8--ce-qui-est-livré-dans-la-phase-p4-frontend)
   - [8bis. Phase P5 — validation terrain](#8bis--ce-qui-est-livré-dans-la-phase-p5-validation-terrain)
9. [**La page Rapport DEESP** — alignement méthodologique PAA](#9--la-page-rapport-deesp--alignement-méthodologique-paa)
10. [Démarrer le projet sur ma machine](#10--démarrer-le-projet-sur-ma-machine)
11. [Vérifier que tout fonctionne (tests)](#11--vérifier-que-tout-fonctionne-tests)
12. [Comprendre les fichiers du projet](#12--comprendre-les-fichiers-du-projet)
13. [Petit glossaire technique](#13--petit-glossaire-technique)
14. [Problèmes fréquents et solutions](#14--problèmes-fréquents-et-solutions)
15. [La suite du projet](#15--la-suite-du-projet)

---

## 🗺️ Carnet d'exécution du hackathon

Le projet suit un découpage en phases. À jour au **2026-06-27** :

| Phase | Statut | Description rapide |
|-------|--------|--------------------|
| P1 → P5 | ✅ Livrées | Fondations, collecte, indicateurs DEESP, frontend complet, validation terrain GPX |
| P6.1 | ✅ Livrée | Import historique fév 2025 + comparatif pluriannuel |
| **§ 4.5 DEESP** | ✅ Livré | **Méthodologie DEESP/DEEF appliquée** (collecte horaire 24h/24, page Rapport, 17 tableaux + 12 BarCharts) |
| **P6.2** | ✅ Livré (2026-06-23) | **Page Temps de traversée** — 3 blocs (temps actuel, ce mois, cette semaine), cascade Google → mesures 7j → 50 km/h, calibration GPX |
| ~~P6.3~~ | ❌ Retiré | ~~Heure optimale de départ~~ — module supprimé (code + UI) |
| **P6.4** | ✅ Livré | **Administration** — ajout de tronçons sans redéploiement |
| **P6.4bis** | ✅ Livré (2026-06-23) | **Mesure sous-tronçons** (T1A, T1B, T1C…) — scheduler, migration 0009, carte Accueil + Fiabilité, Tableau 16 ventilé |
| **Polylines réelles** | ✅ En prod | Tracés routiers OSRM persistés en Railway via tunnel Cloudflare (2026-06-23) |
| **P6.9** | ✅ Livré (2026-06-23) | **Segments GPX libres — précision progressive** — import de sous-portions de parcours, accumulation par session, indice de confiance, miroir aller/retour |
| P6.5 → P7.3 | ⏳ À faire | ML Random Forest (optionnel), tests, déploiement Vercel, rapport final |
| **P8.1 → P8.5** | ✅ Livrées (2026-06-24) | **Module Incidents & Accidents** — scraping automatique presse ivoirienne, NLP légère, géolocalisation, page dédiée + overlay carte, export CSV |
| **P9.1** | ✅ Livré (2026-06-27) | **Chatbot guide — Claude (Anthropic)** — bouton Aide flottant sur toutes les pages, relais backend sécurisé (`POST /chatbot/message`), prompt professionnel sans markdown. Prompt enrichi avec le rôle précis des 8 pages : libellés exacts du menu (`Accueil / Carte`, `Indicateurs`, `Rapport DEESP`, `Fiabilité`, `Temps de traversée`, `Heure optimale`, `Incidents`, `Administration`), exemples d'usage portuaire et 4 conseils opérationnels clés. |
| **P9.2** | ✅ Livré (2026-06-27) | **Fix heure optimale** — correction du bug MIN = MOYEN = MAX dans le tableau des créneaux horaires (`min(ProfilHoraire.min)` / `max(ProfilHoraire.max)` + filtre `fenetre_jours=30`) |
| **P9.3** | ✅ Livré (2026-06-27) | **RAG chatbot** — injection automatique des données réelles (trafic, temps de traversée, heures optimales, incidents actifs, stats semaine) avant chaque appel Claude. Module `backend/app/rag/contexte.py` : 5 récupérateurs DB + détection d'intention par mots-clés. Zéro appel HTTP interne — requêtes SQLAlchemy directes. |
| **P10.1 → P10.9** | ✅ Livrées (2026-06-28) | **Refonte UX** — Auth 2 niveaux (lecture/écriture), portail redesigné, vue satellite, export global CSV/XLSX, axes/tronçons, PDF Tableau 16, import CSV évolution, sources incidents configurables, navigation réordonnée |
| **P10.10** | ✅ Livré (2026-06-29) | **Types d'incidents dynamiques + filtre zone portuaire strict** — Migration 0015 (VARCHAR + table `types_incidents`). Double filtre scraper : un article doit contenir à la fois un mot-clé de type (accident, travaux…) ET un mot-clé de lieu portuaire (CARENA, Treichville, Palm Beach…). Panneau « Gérer les types d'incidents » (mode écriture) : saisie par **mots-clés simples séparés par virgule** (la regex est générée automatiquement, avec aperçu temps réel). Ajout d'un type → dropdown du filtre mis à jour **instantanément** sans rechargement. Type « Autre » (fallback NLP) masqué partout dans l'UI. Classificateur NLP lit les types depuis la DB. |
| **v1.0.0** | 🏁 **Terminé (2026-06-29)** | **Version hackathon complète** — toutes les phases P1 → P10 livrées et déployées en production sur Railway. Backend FastAPI + Frontend Next.js opérationnels 24h/24. |

> Les polylines des 6 tronçons suivent maintenant les vraies routes
> (boulevard de Marseille, pont Houphouët-Boigny, avenue Christiani…) —
> persistées en base Railway via un tunnel Cloudflare ponctuel le 2026-06-23.

---

## 🎨 Refonte critère congestion — couleurs Google Maps DEESP (2026-06-22)

> **TL;DR** — Avant cette date, on classait un tronçon « congestionné » via un
> ratio approximatif `duree_trafic / T_ref ≥ 1.5`. Depuis le 2026-06-22, on
> applique **à la lettre** le critère du rapport DEESP : on lit la couleur
> Google Maps de chaque segment du tracé et on en déduit le verdict. La règle
> n'est plus inventée, elle vient de Google directement.

### Citation exacte du rapport (`rapport_oct2025.docx`, section METHODOLOGIE)

> *« Avec l'application « GOOGLE MAPS », ont été considérés comme tronçons
> embouteillés, les tronçons tracés en **ROUGE** et ceux tracés en **ORANGE
> sur une longue distance (moitié du tronçon concerné)**. Il a été constaté,
> après que les équipes aient parcouru les différents axes, que les tronçons
> tracés en orange sur une courte distance ne sont pas liés à des
> embouteillages mais à des arrêts dus aux feux tricolores ou à certaines
> manœuvres. »*

### Implémentation

| Couche | Avant | Après |
|---|---|---|
| **Source Google** | `duration` + `staticDuration` | + `routes.travelAdvisory.speedReadingIntervals` (segments colorés NORMAL / SLOW / TRAFFIC_JAM) |
| **Verdict mesure** | ratio `duree_trafic / T_ref ≥ 1.5` | rouge présent OU orange ≥ 50 % du tracé → congestionné |
| **Classes** | fluide / dense / congestionne / indetermine | fluide / congestionne / **indetermine** (plus de "dense" car le rapport ne le distingue pas) |
| **Indicateurs publiés** | TTI / PTI / BTI + min/moyen/max | **min / moyen / max** + **taux de congestion** + **% rouge moyen** + **% orange moyen** |
| **Stockage** | `duree_trafic_s`, `duree_sans_trafic_s` | + 4 colonnes : `pourcentage_rouge`, `pourcentage_orange`, `pourcentage_vert`, `est_congestionne` (migration 0008) |

### Cas indéterminé

Si Google ne renvoie pas `speedReadingIntervals` pour un tronçon (zone sans
données trafic), les 4 colonnes restent NULL, le tronçon s'affiche en **gris**
sur la carte avec le libellé « Indéterminé » et **aucun verdict n'est
inventé** (conformément à la règle d'or « ne jamais fabriquer de donnée »).

### Ce qui est conservé : les temps

`duree_trafic_s` reste alimenté à chaque cycle et alimente les Tableaux 3-15
du rapport DEESP : **temps minimal / temps moyen / temps maximal** par axe ×
sens × type-jour, par jour / semaine / mois (cf. § 4.5.4 de CLAUDE.md).
`duree_sans_trafic_s` reste en base mais n'est plus exposé publiquement —
il servait au TTI, qui n'est plus calculé.

### Fichiers concernés

**Backend** :
- `backend/app/sources/google_routes.py` — étend le FieldMask + parse les couleurs
- `backend/app/sources/polyline.py` — nouveau : décodeur polyline + distances cumulées
- `backend/app/analyse/congestion.py` — **nouveau** : module central, fonction `classer_congestion(pct_rouge, pct_orange, pct_vert)`
- `backend/app/analyse/indicateurs.py` — refonte : `IndicateursTroncon` n'a plus de TTI / PTI / BTI
- `backend/app/analyse/rapport_paa.py` — Tableau 16 filtre sur `est_congestionne IS TRUE`
- `backend/app/etat/carte.py` — `/carte/etat` renvoie 3 couleurs + motif humain
- `backend/app/collecte/scheduler.py` — persiste les 4 nouvelles colonnes à chaque cycle
- `backend/app/models/models.py` — `Mesure` reçoit 4 colonnes
- `backend/alembic/versions/0008_couleurs_congestion.py` — **nouvelle migration**

**Frontend** :
- `frontend/lib/types.ts` — `ClasseCongestion = "fluide" | "congestionne" | "indetermine"`
- `frontend/components/carte/{CarteLeaflet,PanneauTroncons,LegendeCarte}.tsx` — popups + KPI 3 classes + barre couleur 3 segments
- `frontend/components/indicateurs/{KpiCards,CourbeJournee}.tsx` — KPI temps + couleur, plus de TTI
- `frontend/messages/{fr,en}.json`, `frontend/components/ui/StatutBadge.tsx`, `frontend/tailwind.config.ts` — nettoyés
- `frontend/components/{rapport,fiabilite}/*.tsx` — adaptations des classes Tailwind résiduelles

### Procédure de bascule (déjà exécutée)

```bash
# 1. Local — commit + déploiement
git add backend/ frontend/
git commit -m "Refonte critere congestion : couleurs Google Maps DEESP"
railway up --service backend

# 2. Console Railway — migration + vidage des données legacy
alembic upgrade head

# Vide les mesures legacy (pourcentage_rouge IS NULL) pour qu'elles ne
# polluent pas le taux de congestion sur les 7/30/90 prochains jours.
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

# 3. Vérification — un tronçon doit avoir les nouveaux champs renseignés
curl -s 'https://backend-production-6cbf.up.railway.app/troncons/1/mesures?limite=1' | python -m json.tool

# 4. Frontend — build + démarrage
cd frontend
npm run build && npm start
```

> 📚 Détails complets côté backend : [CLAUDE.md § 4.5.2bis](CLAUDE.md).

---

## 0 · Audit de conformité aux 5 étapes du brief jury

> Tableau croisé entre chaque livrable demandé et son implémentation actuelle.
> Statuts : ✅ livré · 🟡 livré partiellement / avec nuance · ❌ non livré.

### Étape 1 — Analyse des besoins et définition du système

| Exigence du brief | Statut | Implémentation |
|-------------------|--------|----------------|
| Identifier les besoins opérationnels du PAA | ✅ | Documenté dans [CLAUDE.md § 1](CLAUDE.md) — 6 résultats attendus de l'article 4 du cahier des charges, indicateurs cibles, exigences (confrontation hebdomadaire terrain, ajout de parcours sans redéploiement, etc.) |
| Déterminer les axes stratégiques | ✅ | 3 axes officiels × 2 sens = **6 tronçons dirigés** seedés dans la DB et documentés ([CLAUDE.md § 1.1](CLAUDE.md), `backend/app/seed_troncons.py`) |
| Identifier les données nécessaires | ✅ | Modèle de données 5 tables ([CLAUDE.md § 3](CLAUDE.md)) : `troncons`, `mesures`, `profils_horaires`, `evolution_indicateur`, `releves_terrain` |
| Définir les fonctionnalités attendues | ✅ | Feuille de route 7 phases ([CLAUDE.md § 4](CLAUDE.md)) — P1 fondations → P7 pitch |

### Étape 2 — Conception de l'architecture

| Exigence du brief | Statut | Implémentation |
|-------------------|--------|----------------|
| Architecture technique web | ✅ | Backend FastAPI + Frontend Next.js + Postgres + Redis + OSRM, orchestrés via Docker Compose ([CLAUDE.md § 2](CLAUDE.md)) |
| Structure des données | ✅ | 5 modèles SQLAlchemy + 4 migrations Alembic (0001 → 0004) |
| Intégration cartographique | ✅ | Leaflet + OpenStreetMap (tuiles standard) + plugin `leaflet.heat` pour la heatmap |
| APIs de trafic | ✅ | Google Routes API (`TRAFFIC_AWARE_OPTIMAL`) + cascade gracieuse → profils horaires 60 j → 50 km/h |
| Système de stockage local | ✅ | PostgreSQL (mesures, agrégats), Redis (cache léger), volume disque (`GPX_STORAGE_DIR` pour les fichiers GPX terrain) |
| **Sous-livrables architecture** : | | |
| ↳ Une carte interactive | ✅ | [`PageCarte.tsx`](frontend/components/carte/PageCarte.tsx) + [`CarteLeaflet.tsx`](frontend/components/carte/CarteLeaflet.tsx) |
| ↳ Affichage réel des zones | ✅ | Tuiles OSM live + polylines colorées par classe de congestion + heatmap |
| ↳ Système de zoom avancé | ✅ | Zoom intelligent au chargement vers le point chaud + `flyToBounds` au clic sur un tronçon |
| ↳ Marqueurs intelligents | ✅ | 4 markers POI (`C`/`T`/`S`/`P`) sur la page Carte + markers début/fin sur la page Fiabilité dédupés par libellé |
| ↳ Tableau de bord analytique | ✅ | Page Indicateurs alignée DEESP : 4 compteurs (temps moyen / min / max / nb mesures) + 3 cartes couleur (taux de congestion / % rouge moyen / % orange moyen) + sélecteurs tronçon et période |
| ↳ Graphiques dynamiques | ✅ | Recharts : courbe série temporelle, heatmap horaire 7×24, évolution pluriannuelle, écart Fiabilité |

### Étape 3 — Développement de l'interface interactive

| Exigence du brief | Statut | Implémentation |
|-------------------|--------|----------------|
| Interface moderne style dashboard | ✅ | Design system PAA ([README.md § 8](README.md)) — palette navy/sky, fluides via `clamp()`, 3 breakpoints, FR/EN, clair/sombre |
| Carte temps réel | ✅ | WebSocket `/ws/etat` qui pousse l'état à chaque cycle de collecte (60 min) |
| Choix dynamique des tronçons | ✅ | Dropdown sur la page Indicateurs + panneau latéral cliquable sur la page Carte |
| Zoom sur les zones critiques | ✅ | Au chargement (worst classe) + au clic (`flyToBounds`) — cf. § P4.1 |
| Affichage des temps de parcours | ✅ | 3 endroits : popup carte au clic, panneau latéral avec « Temps actuel », KPI page Indicateurs |
| Statistiques de congestion | ✅ | Indicateurs DEESP : temps min / moyen / max, taux de congestion couleur, % rouge moyen, % orange moyen. Classification fluide / congestionné lue depuis Google Maps. |
| Tableaux de données exportables | ✅ | Boutons **Export CSV** et **Export Excel** dans la barre de pilotage de la page Indicateurs |
| Observation visuelle de la circulation | ✅ | Couleur des polylines temps réel + heatmap géographique |

### Étape 4 — Intégration des APIs cartographiques et données temps réel

| Exigence du brief | Statut | Implémentation |
|-------------------|--------|----------------|
| Connexion APIs cartographiques | ✅ | OpenStreetMap (tuiles) + OSRM (auto-hébergé, routage) + Google Routes (trafic) |
| Récupération **temps de parcours** | ✅ | Scheduler APScheduler **toutes les heures (60 min), 24h/24** Africa/Abidjan — 1296 req/jour |
| Récupération **distances** | ✅ | Stockées en base via `seed_troncons` (officielles) + OSRM (réelles routière) |
| Récupération **niveaux de congestion** | ✅ | Couleur Google Maps (`speedReadingIntervals`) lue à chaque cycle → classification fluide / congestionné (critère DEESP officiel — cf. § Refonte ci-dessus). |
| Récupération **itinéraires** | ✅ | Polylines OSRM réelles persistées en Railway (558–1081 cars/tronçon). Tracé routier complet : boulevard de Marseille, pont Houphouët-Boigny, avenue Christiani. Cf. § 0bis. |
| Récupération **données de circulation** | ✅ | **Collecte 24h/24 toutes les heures** (144 req/jour ≪ 250 quota Google), persistée et accessible via `/mesures`, `/troncons/{id}/mesures`, etc. Le filtre DEESP officiel (7h-19h) est appliqué côté analyse pour les Tableaux 3-15 et le Tableau 16. |
| Zoom dynamique | ✅ | `flyToBounds` animé, niveau adaptatif `maxZoom 15` |
| Recentrage automatique | ✅ | `fitBounds` global au chargement si tout est fluide, sinon centré sur le point chaud |
| Visualisation réelle de la zone sélectionnée | ✅ | Polylines OSRM réelles en base Railway depuis le 2026-06-23 (cf. § 0bis). Hard refresh suffit pour les voir. |

### Étape 5 — Tests, optimisation et déploiement

| Exigence du brief | Statut | Implémentation |
|-------------------|--------|----------------|
| Tests fonctionnels | 🟡 | Tests d'intégration partiels (P7 prévue). Validation manuelle systématique des endpoints via Swagger `/docs`. Validation P5 démontrée bout-en-bout avec 6 GPX synthétiques. |
| Optimisation performances | ✅ | DISTINCT ON pour la dernière mesure (1 requête au lieu de 6), `DISTINCT ON` Postgres, index composite `(troncon_id, horodatage)`, échantillonnage 1/5 pour la heatmap |
| Précision des temps mesurés | ✅ | Source Google `TRAFFIC_AWARE_OPTIMAL`. Cross-check terrain via P5 (page Fiabilité) — moyenne mobile des écarts. |
| Fluidité de la carte | ✅ | Leaflet natif, pas de framework lourd. 6 polylines + tuiles OSM = < 100 ms render. Heatmap échantillonnée pour rester légère. |
| Système de zoom | ✅ | `flyToBounds` avec `duration: 0.8 s`. Cf. tableau Étape 4. |
| Ergonomie tableau de bord | ✅ | Responsive 3 breakpoints, bilingue, thème clair/sombre, tooltips, badges colorés |
| Exportation des données | ✅ | CSV et XLSX via `/export/mesures` et `/export/profils` |
| Stabilité globale | 🟡 | Backend Railway en production depuis 2026-06-19. **180 mesures/jour collectées sans trou** depuis le déploiement. Frontend encore en local (`npm start`) — déploiement Vercel/Railway prévu en P7. Pas de monitoring/alerting de prod en place. |

---

### Ce qui n'est PAS encore livré

> **Carnet d'exécution restant** : [PROMPTS_RESTANTS_DEESP.md](PROMPTS_RESTANTS_DEESP.md)
> contient les 7 prompts restants (6.2 → 7.3) entièrement réalignés avec la
> méthodologie DEESP/DEEF du rapport octobre 2025.

- ✅ **Page Temps de traversée** (P6.2 refondu 2026-06-23) — `GET /predire/resume?troncon_id=` + UI 3 blocs (temps actuel, ce mois, cette semaine), précision calibrée par les GPX terrain. Cf. CLAUDE.md § 4.7.
- ❌ ~~**Module Heure optimale de départ**~~ (P6.3) — **retiré du périmètre le 2026-06-23** (code backend + UI supprimés)
- ✅ **Page Administration** (P6.4) — ajout/édition de tronçons via UI + **sous-tronçons codifiés** (T1A, T1B, T1C…) comme dans le rapport DEESP
- ✅ **Mesure au niveau sous-tronçon** (P6.4bis, 2026-06-23) — chaque T1A/T1B/T1C a sa propre mesure Google ; scheduler étendu, migration 0009 (`mesures.sous_troncon_id`), carte Accueil + Fiabilité dessinent chaque sous-tronçon avec sa couleur DEESP, Tableau 16 ventilé par sous-tronçon. Cf. CLAUDE.md § 4.8.
- ❌ **ML niveau 3** (P6.5, optionnel) — Random Forest avec évaluation honnête vs profils horaires
- ❌ **Frontend déployé sur Vercel** — actuellement servi par `npm start` local
- ❌ **OSRM exposé en production** — nécessaire pour `confiance_matching` (P5) et vraies polylines (procédure complète CLAUDE.md § 8.7 Oracle Cloud)
- ❌ **Vrais GPX terrain** — la démo P5 tourne sur GPX synthétiques (cf. CLAUDE.md § 4.3.1)
- ❌ **Suite de tests automatisés** — pytest backend pour `rapport_paa` + endpoints critiques (P7.1)
- ❌ **Cache Redis** — wrapper avec TTL pour `/carte/etat`, `/rapport/*`, `/predire/resume` (P7.1)
- ❌ **Rapport final article 4 + Pitch** (P7.3) — document docs/rapport-final.md + docs/pitch.md à produire

### Synthèse pour le pitch jury

- **8 / 9 sous-exigences livrées** à 100 % sur les Étapes 1-4
- **1 nuance importante** : « visualisation réelle de la zone » dépend d'OSRM en prod (script `complete_troncons` à lancer ponctuellement avec un tunnel OSRM)
- **Étape 5** : 5/7 livrés à 100 %, 2 partiels (tests + stabilité) — couverture suffisante pour un prototype hackathon
- **6 manquants** identifiés, tous déjà planifiés dans la feuille de route P6 / P7

---

## 0ter · Pourquoi un modèle de Machine Learning serait un vrai gain (P6.5)

> **Cette section met en avant l'apport potentiel d'un modèle ML — non
> livré dans le périmètre actuel mais identifié comme la prochaine étape
> à fort impact si le projet se poursuit après le hackathon.**

### Limites du prédicteur actuel (niveau 2 de la cascade)

Le niveau 2 (`mesures_jour_type_7j`) calcule **min / moyen / max des mesures
Google des 7 derniers jours** sur le même type de jour (jour_ouvrable ou
week_end). C'est une statistique descriptive — pas un modèle prédictif.
Conséquences :

| Capacité                                                            | Cascade actuelle | Modèle ML (Random Forest / Gradient Boosting) |
|---------------------------------------------------------------------|------------------|------------------------------------------------|
| Biais constant par tronçon (calibration GPX)                        | ✅ Oui           | ✅ Oui (et plus fin)                           |
| Variations **par heure de la journée** (rush 7h–9h vs creux 14h)    | ❌ Tout est moyenné | ✅ Feature `heure` discrète                    |
| Variations **par jour de la semaine** (lundi rentrée vs vendredi soir) | ❌ On agrège juste jour_ouvrable | ✅ Feature `weekday` |
| Effet **saison des pluies** (juin–octobre → +20 à +40 % de temps)   | ❌                | ✅ Feature `mois` + précipitations             |
| Effet **événements** (rentrée scolaire, jours fériés ivoiriens, fêtes locales) | ❌ | ✅ Avec un calendrier injecté |
| Effet **propagation de congestion** (saturation pont Houphouët-Boigny → axe Marcory) | ❌ | ✅ Features croisées entre tronçons |
| **Non-linéarités** (la vitesse ne baisse pas linéairement avec le volume) | ❌ Une seule moyenne | ✅ Arbres = non-linéaire par nature |
| **Intervalle de prédiction calibré** (≠ simple min/max observé)     | ❌                | ✅ Quantile regression possible                |

### Architecture cible (P6.5 — optionnel post-hackathon)

```
Features in :  heure (0-23) + weekday (0-6) + mois (1-12)
               + troncon_id (one-hot) + type_jour
               + congestion observée 1h avant (sur ce tronçon ET les voisins)
               + pluie_dernière_heure (API meteo gratuite)
               + jour_férié_ivoirien (calendrier static)
               + nb_mesures_dernier_créneau (proxy de la confiance)
↓
Random Forest Regressor (sklearn) → temps_traversee_mn
+ Quantile Regressor → intervalle [p10, p90]
↓
Output : { min_mn, moyen_mn, max_mn, intervalle_confiance_90 }
```

### Pré-requis et chemin de mise en œuvre

1. **Données minimales** : 2-3 mois de collecte Google continue + 20+ vrais
   GPX par tronçon (calibration honnête).
2. **Split train/test** propre — séries temporelles, donc **pas de
   randomisation** des dates. Train = 60 % des semaines anciennes, test = 20 %
   intermédiaires, validation = 20 % les plus récentes.
3. **Baseline à battre** : la cascade actuelle (`mesures_jour_type_7j`)
   avec calibration GPX. Si le RF gagne ≥ 1 min de MAE → adoption. Sinon
   c'est juste du bruit → on garde la cascade.
4. **Coût opérationnel** : ré-entraînement nocturne (1 fois/24h) en parallèle
   du job d'agrégation des profils. Inférence en mémoire (RF de 50 arbres
   ≈ 5 MB), pas de GPU.

### Pourquoi c'est REPOUSSÉ et pas livré

Pour le hackathon : **pas assez de données réelles** (collecte démarrée
2026-06-19, à peine 5 jours). Le ML sur 5 jours de données overfitterait
sur le bruit. La cascade `mesures_jour_type_7j` actuelle est la **bonne
décision pour la livraison du hackathon** — simple, déterministe,
calibrable par GPX, alignée DEESP.

Le ML devient pertinent **après 2-3 mois en production** quand on disposera
d'un vrai dataset. À ce moment-là, P6.5 est une journée de travail (le
backend est déjà structuré pour exposer `source=ml_random_forest` comme
un 4e niveau de cascade).

---

## 0bis · Polylines des tronçons — état en production

> **Situation au 2026-06-23 :** les 6 tronçons ont des polylines réelles
> persistées en base Railway (558 à 1081 caractères chacune). Aucune
> manipulation supplémentaire n'est nécessaire — hard refresh suffit.

| Tronçon | Longueur polyline | Route couverte |
|---------|-------------------|----------------|
| CARENA → Palm Beach (id=1) | 939 cars | Bd de Marseille + pont HB |
| Palm Beach → CARENA (id=2) | 1081 cars | Retour complet |
| Toyota CFAO → Palm Beach (id=3) | 558 cars | Av. Christiani + port |
| Palm Beach → Toyota CFAO (id=4) | 567 cars | Retour |
| SODECI → Palm Beach (id=5) | 577 cars | Zone 4 → port |
| Palm Beach → SODECI (id=6) | 580 cars | Retour |

Ces polylines ont été générées par OSRM (extrait OSM Côte d'Ivoire) et
persistées via `python -m app.complete_troncons` lancé depuis la Console
Railway avec un **tunnel Cloudflare** temporaire vers OSRM local
(`cloudflared tunnel --url http://localhost:5000`). Étant idempotent, ce
script peut être rejoué à tout moment sans effet secondaire.

### Ce que demande chaque script

| Script | OSRM requis ? | DB requise ? | Action |
|--------|---------------|--------------|--------|
| `seed_troncons` | ❌ | ✅ | Insère les 6 lignes (noms, distance officielle). Coords et polyline restent `NULL`. |
| `set_coords_depuis_seed` | ❌ | ✅ | Pose **uniquement** les coords depuis `coordonnees.py`. Polyline et distance inchangées. |
| `complete_troncons` | ✅ | ✅ | Pose coords + **polyline réelle routière** + distance recalculée par OSRM. |

### Pour rejouer complete_troncons (idempotent)

```powershell
# 1. Sur le PC Windows — OSRM déjà en local sur :5000 (docker compose up osrm)
.\cloudflared-windows-amd64.exe tunnel --url http://localhost:5000
# → Cloudflare affiche une URL https://xxxx.trycloudflare.com

# 2. Sur Railway
railway variable set "OSRM_BASE_URL=https://xxxx.trycloudflare.com" --service backend

# 3. Console Railway
python -m app.complete_troncons

# 4. Nettoyage
railway variable delete OSRM_BASE_URL --service backend
```

Avantage du tunnel Cloudflare vs ngrok : pas de compte requis, pas de
limite de connexions, fonctionne même si le port 22 SSH est bloqué.

---

## 1 · À quoi ça sert ?

Le Port Autonome d'Abidjan veut **savoir en temps réel** combien de temps mettent
les camions et véhicules pour rejoindre la zone portuaire depuis trois points
stratégiques de la ville :

| Axe officiel | Distance | Temps idéal (à 50 km/h, sans bouchon) |
|---|---|---|
| **CARENA** *(Plateau)* ⇄ Pharmacie Palm Beach | ~14,9 km | ≈ 17 min 53 s |
| **Toyota CFAO** *(Treichville)* ⇄ Pharmacie Palm Beach | ~8,0 km | ≈ 9 min 36 s |
| **Agence SODECI** *(Zone 4)* ⇄ Pharmacie Palm Beach | ~8,3 km | ≈ 9 min 58 s |

Chaque axe est mesuré **dans les deux sens** (aller ET retour), car le trafic
est rarement le même selon qu'on entre ou qu'on sort de la zone du port. Cela
fait **6 tronçons** au total.

Le but final de l'application (à la fin des 7 phases) :

- afficher une **carte interactive** de ces 6 tronçons, colorés selon l'état du trafic ;
- montrer des **graphiques** de l'évolution des temps de parcours ;
- **identifier les heures et zones de congestion** récurrentes ;
- aider à **recommander un créneau optimal** pour acheminer une marchandise au port.

---

## 2 · Comment ça marche en images

```
                  ┌──────────────────────────────────────────┐
                  │   Tableau de bord (page web — phase P4)  │
                  │   Carte + graphiques + recommandations   │
                  └──────────────────────────────────────────┘
                                      ▲
                                      │  consulte
                                      │
                  ┌──────────────────────────────────────────┐
                  │   API du projet (notre backend FastAPI)  │
                  │   « Quel est le temps actuel sur l'axe » │
                  └──────────────────────────────────────────┘
                       ▲                              │
            consulte   │                              │ écrit chaque mesure
                       │                              ▼
        ┌─────────────────────┐         ┌─────────────────────────────────┐
        │  Google Routes API  │         │  Base de données PostgreSQL     │
        │  (trafic en direct) │         │  Historique de toutes les       │
        └─────────────────────┘         │  mesures faites sur chaque axe  │
                                        └─────────────────────────────────┘
                       ▲
                       │
       ┌─────────────────────────────────────────────────────────────────────┐
       │  OSRM (notre propre moteur de routage)                              │
       │  Sert à dessiner le tracé exact sur la carte et à calculer le       │
       │  "temps idéal" sans bouchon — comme un GPS hors-ligne.              │
       └─────────────────────────────────────────────────────────────────────┘
```

**En résumé :** un programme va régulièrement demander à Google « combien de
temps mettrais-je sur cet itinéraire maintenant ? », stocke la réponse en
base de données, et une page web vient lire ces données pour les afficher.

---

## 3 · Ce qui est livré dans la phase P1

Le projet est découpé en **7 phases** (cf. [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases)).
La phase **P1 — Fondations** est terminée. Voici ce que ça veut dire concrètement :

### ✅ L'infrastructure tourne

Cinq petits programmes (qu'on appelle des **services**) tournent côte à côte
dans des **conteneurs Docker** — pensez à Docker comme à des cartons
préemballés qui contiennent chacun un logiciel prêt à fonctionner, sans rien
casser sur votre PC.

| Service     | Rôle                                                              | URL d'accès                |
|-------------|-------------------------------------------------------------------|----------------------------|
| `db`        | Base de données PostgreSQL où on stocke tout l'historique         | `localhost:5432`           |
| `redis`     | Mémoire ultra-rapide pour les données temporaires (cache)         | `localhost:6379`           |
| `osrm`      | Notre GPS interne (sait dessiner les tracés sur la carte d'Abidjan) | `http://localhost:5000`  |
| `backend`   | Le cœur de l'application (l'API FastAPI en Python)                | `http://localhost:8081`    |
| `frontend`  | La future page web (Next.js, encore vide en P1)                   | `http://localhost:3000`    |

### ✅ Le schéma de la base de données est créé

Quatre tables ont été conçues pour stocker proprement les données du projet :

| Table              | Ce qu'elle contient                                                              |
|--------------------|----------------------------------------------------------------------------------|
| `troncons`         | Les 6 axes officiels avec leur tracé exact                                       |
| `mesures`          | Toutes les mesures de temps de parcours, datées (sera remplie en **P2**)         |
| `profils_horaires` | Statistiques par jour-de-semaine + heure (calculé chaque nuit en **P3**)         |
| `releves_terrain`  | Mesures faites manuellement avec un GPS sur le terrain (vérification en **P5**)  |

### ✅ Les 6 Axes sont chargés et leur tracé dessiné

Au démarrage, on a inséré les 6 axes dans la table `troncons`. Puis on a
demandé à OSRM (notre GPS interne) de **calculer le tracé exact de chaque axe**
sur les routes d'Abidjan. Résultat dans la base :

| ID | Tronçon                                            | Distance (mesurée par OSRM) | Couleur sur la carte |
|----|----------------------------------------------------|-----------------------------|----------------------|
| 1  | CARENA → Pharmacie Palm Beach                      | 11 823 m                    | bleu foncé           |
| 2  | Pharmacie Palm Beach → CARENA                      | 13 163 m                    | bleu clair           |
| 3  | Toyota CFAO → Pharmacie Palm Beach                 | 10 003 m                    | rouge foncé          |
| 4  | Pharmacie Palm Beach → Toyota CFAO                 |  9 984 m                    | rouge clair          |
| 5  | Agence SODECI → Pharmacie Palm Beach               |  8 324 m                    | vert foncé           |
| 6  | Pharmacie Palm Beach → Agence SODECI               |  8 986 m                    | vert clair           |

> 💡 Les distances mesurées par OSRM peuvent différer des distances officielles
> car OSRM choisit l'itinéraire automobile réel, et c'est cet itinéraire-là que
> Google et toutes les autres sources mesurent. Cohérence avant tout.

### ✅ L'API expose 3 routes utiles

L'**API**, c'est une porte d'entrée qu'on appelle avec une URL. Voici celles
qui existent à ce stade :

| URL                                       | Ce qu'elle fait                                                  |
|-------------------------------------------|------------------------------------------------------------------|
| `GET /health`                             | Dit simplement « je suis en ligne » — sert au monitoring         |
| `GET /diag/google/{id}`                   | Donne le temps actuel **en direct** d'après Google (avec/sans trafic) |

> Une documentation interactive auto-générée est disponible : http://localhost:8081/docs

### ❌ TomTom a été retiré du projet

Au départ on prévoyait d'utiliser TomTom comme deuxième source de données.
Après test, **TomTom n'a aucune couverture cartographique à Abidjan** : ses
serveurs répondent « point trop éloigné du segment le plus proche » sur
chacun des 18 points testés. On l'a donc **complètement retiré** plutôt que
de garder du code inutile (cf. [CLAUDE.md § 2.5](CLAUDE.md)).

### Ce qui n'est **pas encore** fait à la fin de P1 (et c'est normal)

- ❌ Pas de **collecte automatique** des mesures *(arrive en P2)*
- ❌ Pas d'**indicateurs** type FHWA *(arrive en P3)*
- ❌ Pas de **carte** ni de **graphiques** visibles *(arrive en P4)*
- ❌ Pas de **prédiction** ni de **recommandations** *(arrive en P6)*

---

## 4 · Ce qui est livré dans la phase P2

> **L'idée en une phrase :** un **robot** tourne tout seul en arrière-plan, demande
> à Google le temps de parcours actuel sur chaque tronçon, l'**écrit en base**,
> et chaque nuit **calcule des statistiques** réutilisables pour des graphiques.

### ✅ Un robot mesure le trafic tout seul, en continu

Un **ordonnanceur** (APScheduler — pensez à un « réveil programmable » à
l'intérieur du backend) se réveille **toutes les 60 minutes**, **entre 7h et
19h** (fuseau Abidjan), et fait ceci pour chacun des 6 tronçons :

1. **Appelle Google Routes** en parallèle pour récupérer le temps actuel.
2. **Calcule la vitesse moyenne** (= distance officielle ÷ durée).
3. **Insère une ligne** dans la table `mesures` avec l'horodatage exact.
4. **Si Google échoue** : nouvelle tentative au bout de 1 s, puis 2 s, puis 4 s
   (*backoff exponentiel*). Au bout de 3 essais infructueux, on insère quand
   même une ligne **vide** (`duree_trafic_s = NULL`) — c'est ce qu'on appelle
   un **« trou de mesure »** : on garde la preuve qu'on a tenté, **sans jamais
   inventer de valeur**.

### ✅ Le quota Google est respecté automatiquement

Google facture chaque appel. Le projet a un **plafond strict de 250 requêtes
par jour**. Le robot calcule au démarrage combien de requêtes il enverra et
**affiche un avertissement** si la configuration dépasse la limite :

| Intervalle | Plage horaire | Requêtes / jour | Statut       |
|-----------:|---------------|----------------:|--------------|
| 15 min     | 7h–19h        | **288**         | ❌ trop      |
| **20 min** | **7h–19h**    | **216**         | ✅ **utilisé** |
| 30 min     | 7h–19h        | 144             | ✅ marge confortable |

### ✅ Chaque nuit, les mesures deviennent des statistiques exploitables

Un **deuxième job** tourne tous les soirs à **23h00**. Il regroupe les mesures
par **(tronçon, jour de la semaine, heure)** et calcule pour chaque case :

- la **moyenne**, la **médiane**, le **min**, le **max**, le **P95**
  (le P95 = la valeur que 95 % des temps ne dépassent pas — utile pour
  « combien de temps faut-il prévoir pour arriver à l'heure presque toujours ? ») ;
- le **nombre de mesures** utilisées.

Le calcul est fait en parallèle sur **3 fenêtres glissantes** : **30, 60 et
90 jours**. Pourquoi 3 fenêtres ? Pour comparer la situation récente
(« 30 jours ») à la tendance plus ancienne (« 90 jours ») et détecter une
amélioration ou une dégradation du trafic.

### ✅ Les valeurs aberrantes sont détectées, mais conservées

Si une mesure est très loin des autres pour la même case (panne d'un capteur
Google, accident…), elle pourrait fausser les statistiques. On utilise la
**méthode IQR** (écart interquartile) : on prend les 25 % et 75 % du milieu de
la distribution, et toute valeur trop éloignée est **marquée comme aberrante**
(colonne `aberrante = true`). Elle reste en base (pour la traçabilité) mais est
**exclue du calcul des statistiques**.

### ✅ De nouvelles routes API pour piloter et exporter

| URL                                     | Ce qu'elle fait                                                              |
|-----------------------------------------|------------------------------------------------------------------------------|
| `POST /collecte/start`                  | Démarre le robot (si arrêté)                                                 |
| `POST /collecte/stop`                   | Arrête le robot proprement                                                   |
| `GET  /collecte/status`                 | Combien de mesures aujourd'hui, prochaine exécution, estimation du quota     |
| `POST /collecte/run-once`               | Déclenche **un cycle immédiat** (utile pour la démo ou les tests)            |
| `POST /agregation/run`                  | Force le recalcul des profils horaires (utile après import de données)       |
| `GET  /troncons/{id}/profil?jour=mardi` | Renvoie une **courbe heure-par-heure** prête à tracer pour un jour donné     |
| `GET  /export/mesures?format=csv\|xlsx` | Télécharge les mesures brutes (filtres : tronçon, plage de dates)            |
| `GET  /export/profils?format=xlsx`      | Télécharge un classeur Excel **heure × jour** par tronçon (1 feuille / axe)  |

### Ce qui n'est **pas encore** fait à la fin de P2

- ❌ Pas encore d'**indicateurs de congestion** (couleur Google Maps + temps min/moyen/max) — *arrive en P3*
- ❌ Pas encore de **carte** ni de **graphiques** visibles — *arrive en P4*

---

## 5 · Ce qui est livré dans la phase P3 *(refondu 2026-06-22)*

> **L'idée en une phrase :** les mesures brutes sont transformées en
> **indicateurs DEESP officiels** (couleurs Google Maps + temps min/moyen/max),
> et l'API est **restructurée** pour que le tableau de bord puisse les afficher
> **en temps réel** sans transformation.
>
> 📌 **Note historique** : initialement, P3 livrait des indicateurs FHWA (TTI /
> PTI / BTI) calculés à partir d'un ratio numérique. Depuis le **2026-06-22**,
> cette logique est remplacée par la lecture directe des couleurs Google Maps,
> conformément au rapport DEESP (cf. § « Refonte critère congestion » en haut
> de ce README).

### ✅ Trois pourcentages couleur lus pour chaque tronçon

À chaque cycle de collecte, Google Routes renvoie pour chaque segment du
tracé un enum `Speed` (`NORMAL` / `SLOW` / `TRAFFIC_JAM`). On somme les
distances par couleur et on en déduit 3 pourcentages :

| Champ | Couleur Google | Sens |
|---|---|---|
| `pourcentage_rouge`  | 🔴 TRAFFIC_JAM | Embouteillage sévère |
| `pourcentage_orange` | 🟠 SLOW | Trafic ralenti |
| `pourcentage_vert`   | 🟢 NORMAL | Circulation fluide |

### ✅ Classification immédiatement lisible — règle DEESP

Le rapport oct. 2025 n'utilise que **3 classes** (pas de "dense"
intermédiaire) :

| Cas | Classe | Couleur sur la carte | Interprétation |
|---|---|---|---|
| `pourcentage_rouge > 0` | **congestionné** | 🔴 rouge (`#E74C3C`) | « Au moins une portion en bouchon sévère » |
| `pourcentage_orange ≥ 50 %` | **congestionné** | 🔴 rouge | « Orange long → embouteillage selon le rapport » |
| Sinon, vert + orange court | **fluide** | 🟢 vert (`#2ECC71`) | « Circulation OK ; orange court = feux/manœuvres » |
| Aucune couleur retournée | **indéterminé** | ⚪ gris (`#95A5A6`) | « Google n'a pas qualifié le tracé. **Aucun verdict inventé.** » |

> **Exemple chiffré (Toyota CFAO → Palm Beach, hypothétique) :**
> Google renvoie 12.5 % du tracé en rouge, 41 % en orange, 46.5 % en vert.
> Règle DEESP → rouge > 0 → **classe = congestionné** 🔴. Le motif affiché
> dans le popup Leaflet : *« Tronçon tracé en rouge sur 12.5 % de sa
> longueur (critère DEESP : rouge → congestionné). »*

### ✅ Temps de référence — repli déterministe simple

Le rapport DEESP utilise le **temps théorique à 50 km/h** comme référence
unique (Tableau 1 du rapport) :

```
T_ref_50kmh = distance_m / (50 km/h × 1000 / 3600)  # en secondes
```

Plus de cascade Google freeflow → TomTom → 50 km/h : seul le 50 km/h est
utilisé pour les comparaisons, exactement comme dans le rapport.

### ✅ Détection automatique des heures de pointe

Une fonction parcourt les profils horaires et **identifie automatiquement**,
pour chaque jour de la semaine, les heures où la moyenne dépasse
`1,5 × temps_référence` (seuil configurable). Résultat utilisable directement
sous la forme `{ "jeudi": [7, 8, 17, 18, 19], "vendredi": [...] }`.

### ✅ L'API est restructurée en 7 routeurs métier (pour Swagger)

Avant P3, toutes les routes étaient mélangées. Maintenant l'API est organisée
**par domaine fonctionnel**, ce qui rend la page `/docs` beaucoup plus lisible :

| Routeur          | Rôle                                                                    |
|------------------|-------------------------------------------------------------------------|
| **`/troncons`**  | Référentiel + dernier état + indicateurs sur période                    |
| **`/mesures`**   | Accès transversal aux mesures (filtres : tronçon, source, dates, trous) |
| **`/profils`**   | Profils horaires (24 points heure-par-heure)                            |
| **`/indicateurs`** | Séries temporelles + heures de pointe                                 |
| **`/collecte`**  | Pilotage du robot                                                       |
| **`/export`**    | CSV / XLSX                                                              |
| **`/carte`**     | État temps réel prêt pour Leaflet                                       |

### ✅ Une route « état temps réel » prête à afficher sur une carte

`GET /carte/etat` renvoie en **un seul appel** tout ce dont le frontend Leaflet
aura besoin pour afficher la carte avec le bon code couleur :

```json
{
  "horodatage_utc": "2026-06-22T15:35:00+00:00",
  "fuseau_affichage": "Africa/Abidjan",
  "couleurs": {
    "fluide":       "#2ECC71",
    "congestionne": "#E74C3C",
    "indetermine":  "#95A5A6"
  },
  "criteres": {
    "source": "Couleurs Google Maps (speedReadingIntervals)",
    "regle_congestion": "Congestionné si ROUGE OU ORANGE ≥ 50 % du tronçon.",
    "seuil_orange_long_pct": 50.0
  },
  "nb_troncons": 6,
  "troncons": [{
    "id": 3,
    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
    "polyline": "qnj_@rinW...",
    "classe_congestion": "congestionne",
    "libelle_classe": "Congestionné",
    "couleur_etat": "#E74C3C",
    "couleur_google": {
      "pourcentage_rouge": 12.5,
      "pourcentage_orange": 41.0,
      "pourcentage_vert":  46.5
    },
    "motif_congestion": "Tronçon tracé en rouge sur 12.5 % de sa longueur (critère DEESP : rouge → congestionné).",
    "derniere_mesure": { "duree_trafic_s": 1642, "source": "google", "...": "..." }
  }]
}
```

### ✅ Un WebSocket pour pousser les mises à jour en temps réel

L'adresse `ws://localhost:8081/ws/etat` est un **canal permanent** entre le
serveur et le navigateur (différent d'une URL classique). Le serveur **pousse
spontanément** un nouveau message à chaque cycle de collecte — pas besoin de
recharger la page. Concrètement :

1. À l'ouverture : le serveur envoie un message `{"type": "snapshot", ...}` avec
   l'état complet **immédiatement**.
2. Toutes les 60 minutes (quand le robot tourne) : tous les clients connectés
   reçoivent un message `{"type": "maj", "donnees": {...}}` avec le nouvel état.
3. Le client peut envoyer le texte `"ping"` à tout moment ; le serveur répond
   `"pong"` (utile pour vérifier que la connexion est encore vivante).

> **À quoi ça sert concrètement ?** Quand le frontend (P4) sera prêt, la carte
> changera de couleur **dès qu'une nouvelle mesure arrive**, sans que
> l'utilisateur ait à appuyer sur F5.

### Ce qui n'est **pas encore** fait à la fin de P3

- ❌ Pas encore de **carte** ni de **graphiques** visibles — *arrive en P4*
- ❌ Pas encore de **prédiction** ni de **recommandations** — *arrive en P6*

---

## 6 · Ce qui est livré dans la phase P6.1

> **L'idée en une phrase :** la base de données est **alimentée dès le premier jour**
> avec **plus de 2 000 mesures terrain réelles** et un **comparatif pluriannuel**,
> au lieu d'attendre une semaine que le robot accumule de la matière.

### ✅ Import de la campagne terrain de Février 2025 (2 016 mesures)

Le fichier `Base_Nettoyee_PAA_Fev2025.xlsx` contient les mesures réelles
récoltées sur le terrain en février 2025. Elles sont importées dans la table
`mesures` avec `source = 'historique_paa_2025'` (un nouveau code source
distinct de `google` pour ne pas mélanger les calculs temps réel).

| Tronçon                                  | Mesures importées |
|------------------------------------------|------------------:|
| CARENA → Pharmacie Palm Beach            | 336               |
| Pharmacie Palm Beach → CARENA            | 336               |
| Toyota CFAO → Pharmacie Palm Beach       | 336               |
| Pharmacie Palm Beach → Toyota CFAO       | 336               |
| Agence SODECI → Pharmacie Palm Beach     | 336               |
| Pharmacie Palm Beach → Agence SODECI     | 336               |
| **Total**                                | **2 016**         |

Après l'import, les **profils horaires** sont **recalculés automatiquement** :
les statistiques (moyenne, médiane, P95) sont donc immédiatement disponibles.

### ✅ Import du comparatif pluriannuel (24 lignes)

Le fichier `FEVRIER_2026.xlsx`, feuille **`SYNTHESE COMPAREE`**, contient un
comparatif officiel **oct_2025 vs fev_2026** par axe, sens et type de jour
(jours ouvrables / week-ends). Une nouvelle table **`evolution_indicateur`**
le stocke :

- **6 axes** × **2 périodes** × **2 types de jour** = **24 lignes**
- Pour chacune : `temps_min_s`, `temps_moyen_s`, `temps_max_s`

Cette table alimentera plus tard le graphique d'évolution de la performance
« temps de traversée » demandé par le cahier des charges (article 4.4).

### ✅ Deux nouvelles routes d'import (utilisables depuis Swagger)

| URL                            | Ce qu'elle fait                                                                |
|--------------------------------|--------------------------------------------------------------------------------|
| `POST /import/base-nettoyee`   | Upload du fichier 2025 → insère les 2 016 mesures + recalcul des profils       |
| `POST /import/evolution`       | Upload du fichier 2026 → insère les 24 lignes du comparatif pluriannuel        |

Les imports sont **idempotents** : on peut relancer un upload sans risque,
les doublons sont ignorés (clé unique par `troncon_id + horodatage + source`
côté mesures, et `axe + sens + periode + type_jour` côté évolution).

### ⚠️ Règle d'or : ne jamais mélanger les sources

| Pour calculer…                                  | Source à utiliser                     |
|-------------------------------------------------|---------------------------------------|
| L'état **temps réel** affiché sur la carte      | `source = 'google'` uniquement        |
| Le **profil horaire** et la **page Temps de traversée** (P6.2) | `'google'` + `'historique_paa_2025'`  |
| La **comparaison pluriannuelle**                | Table `evolution_indicateur`          |

---

## 7 · Déploiement Railway (production)

> Le backend est **déployé en ligne** sur Railway depuis le 19 juin 2026 :
> **https://backend-production-6cbf.up.railway.app**

### Architecture déployée

| Composant       | Hébergement                          | État                              |
|-----------------|--------------------------------------|-----------------------------------|
| **Backend FastAPI** | Service Docker Railway          | ✅ En ligne 24h/24                |
| **PostgreSQL**  | Plugin Railway managé                | ✅ Provisionné, sauvegardes auto  |
| **Redis**       | Plugin Railway managé                | ✅ Provisionné                    |
| **OSRM**        | Non déployé (optionnel)              | ⚠️ Repli 50 km/h utilisé          |
| **Frontend**    | Service `frontend` Railway (Railpack) | ✅ En ligne 24h/24                |

### Méthode de déploiement validée (2026-06-29)

- **Déploiement frontend depuis le dossier dédié** : `cd frontend && railway up --service frontend`.
- **Build de vérification obligatoire** : `npm run build` dans `frontend/` avant tout déploiement.
- **Règle de cache Railway** : `git add -A && git commit -m "..."` avant `railway up`, sinon les nouveaux fichiers peuvent être absents du conteneur.
- **Port dynamique** : le frontend doit démarrer avec `npx next start -p $PORT` ; aucun port fixe n'est attendu par Railway.
- **Variables build-time** : `NEXT_PUBLIC_*` doivent être définies avant le premier build du frontend ; un changement de variable exige un redéploiement complet.
- **Vérification post-déploiement** : `railway status`, puis `railway logs --service frontend --deployment <id>` pour contrôler le démarrage.

### Ce qui tourne en continu sur Railway

- **Robot de collecte Google Routes** : toutes les **20 minutes**, **de 7h00
  à 19h00** (Africa/Abidjan), soit **216 mesures / jour** réparties sur les
  6 tronçons.
- **Agrégation nocturne** des profils horaires chaque jour à **23h00**.
- **Endpoints publics** : `/health`, `/carte/etat`, `/docs` (Swagger),
  `/troncons/{id}/indicateurs`, etc.

### Endpoints clés à vérifier

| URL publique                                                   | Ce qu'on doit voir                     |
|----------------------------------------------------------------|----------------------------------------|
| https://backend-production-6cbf.up.railway.app/health          | `{"status":"ok"}`                      |
| https://backend-production-6cbf.up.railway.app/collecte/status | `actif: true`, 6 tronçons, ~216 req/j  |
| https://backend-production-6cbf.up.railway.app/carte/etat      | Snapshot temps réel des 6 tronçons     |
| https://backend-production-6cbf.up.railway.app/docs            | Documentation Swagger interactive      |

### État de la base de données Railway

Au **19 juin 2026** (fin P6.1) :

| Table                      | Lignes  | Provenance                                   |
|----------------------------|--------:|----------------------------------------------|
| `troncons`                 | 6       | Seed initial                                 |
| `mesures` (`google`)       | +216 / jour | Robot APScheduler en continu             |
| `mesures` (`historique_paa_2025`) | **2 016** | Import campagne terrain Février 2025  |
| `evolution_indicateur`     | **24**  | Import SYNTHESE COMPAREE (oct_2025 / fev_2026) |
| `profils_horaires`         | recalculé chaque nuit | Agrégation IQR sur 30 / 60 / 90 jours  |

### Procédures de déploiement

📖 **Toutes les procédures, pièges et bonnes pratiques** sont documentés dans
[`railwaydeploy.md`](railwaydeploy.md) à la racine. **À lire avant tout
`railway up`** — notamment :

- **Déploiement frontend validé** : `cd frontend && railway up --service frontend`.
- **Vérification de build locale obligatoire** : `cd frontend && npm run build` doit réussir avant tout `railway up`.
- Règle critique : **`git add -A` + commit** avant `railway up` (Railway
  utilise `git archive` et ignore les fichiers non commités).
- Ne **jamais** mettre `alembic upgrade head` dans le `startCommand`
  (provoque un `pg_advisory_lock` bloquant). Lancer la migration
  **manuellement** depuis la **Console Railway** après chaque déploiement
  qui contient une nouvelle migration.
- `${PORT}` doit être utilisé dans le start command du frontend (`npx next start -p $PORT`) afin que Railway injecte le bon port.
- `numReplicas = 1` obligatoire (APScheduler vit en mémoire).
- `NEXT_PUBLIC_API_BASE_URL` doit être définie dans Railway **avant** le premier build du frontend et tout changement de valeur nécessite un nouveau déploiement complet.

---

## 8 · Ce qui est livré dans la phase P4 (frontend)

> **L'idée en une phrase :** une application web **Next.js + React + TypeScript**
> entièrement responsive (PC, tablette, mobile), bilingue FR/EN, en thème clair ou
> sombre, qui consomme l'API du backend et affiche en temps réel la carte des
> tronçons, les indicateurs FHWA et toute l'analyse historique.

### ✅ Identité visuelle PAA + design system

Une **palette dérivée du bleu marine institutionnel** du Port Autonome d'Abidjan :

| Rôle | Couleur | Code | Utilisation |
|------|---------|------|-------------|
| Bandeau principal | Bleu marine | `#0B2545` | Topbar, splash screen, accents |
| Surfaces secondaires | Bleus clairs | `#D9E2F3`, `#EFF4FA` | En-têtes de tableaux, lignes alternées |
| Boutons / accents | Navy soutenu | `#1F4E79` | Boutons primaires, focus, sélection |
| **Référence 50 km/h** | **Bleu ciel** | **`#4CC9F0`** | **Réservé EXCLUSIVEMENT à la ligne de référence sur les graphes** (norme du cahier des charges) |
| Fluide | Vert | `#2ECC71` | Tronçon sans bouchon (vert ou orange court Google Maps) |
| Congestionné | Rouge | `#E74C3C` | Bouchon sévère (rouge OU orange long Google Maps) |
| Indéterminé | Gris | `#95A5A6` | Google n'a pas qualifié le tracé |
| ~~Dense~~ | ~~Orange `#F39C12`~~ | *Alias couleur conservé pour warnings hors-congestion (jauges de calibration P5).* La **classe de congestion "dense" a été retirée** le 2026-06-22 — le rapport DEESP n'en distingue pas. |

Définie dans [`frontend/tailwind.config.ts`](frontend/tailwind.config.ts), réutilisée
**partout** : tronçons sur la carte, badges, courbes Recharts, heatmaps.

### ✅ 100 % responsive — trois points de rupture explicites

| Breakpoint | Largeur | Effet |
|------------|---------|-------|
| `sm` | **375 px** (mobile) | Sidebar cachée, menu burger qui ouvre un drawer ; tout empilé en colonne ; tailles fluides via `clamp()` |
| `md` | **768 px** (tablette) | Layout 2-3 colonnes sur les grilles, drawer toujours actif (pas encore de sidebar) |
| `lg` | **1024 px** (desktop) | Sidebar latérale repliable, carte sur 2/3 de la largeur, panneaux en 3-4 colonnes |

**Aucune valeur fixe en pixels** dans la mise en page critique : on utilise des
**tailles fluides** (`fluid-sm`, `fluid-base`, `fluid-2xl`, etc.) qui s'adaptent
automatiquement à la largeur de l'écran.

### ✅ Bilingue FR / EN, bascule INSTANTANÉE

- Dictionnaires plats dans [`frontend/messages/fr.json`](frontend/messages/fr.json)
  et [`frontend/messages/en.json`](frontend/messages/en.json).
- Provider React custom (`lib/i18n.tsx`) qui permute le dictionnaire **en mémoire**
  → bascule FR ↔ EN **sans aucun rechargement de page**.
- Choix persisté dans `localStorage` (clé `paa-locale`), restauré au prochain démarrage.
- Bouton de bascule visible en haut à droite, à côté du sélecteur de thème.

### ✅ Thème clair / sombre persistant

- Géré par [`next-themes`](https://github.com/pacocoursey/next-themes).
- Détecte automatiquement la préférence système, mais peut être forcé via le bouton.
- Persistance `localStorage` (clé `paa-theme`).
- Toutes les couleurs PAA ont leur variante sombre (variables CSS définies dans
  `globals.css`).

### ✅ Écran de démarrage HACKATONIA (splash screen animé)

À chaque ouverture du site, un **écran de démarrage de 4 secondes** s'affiche
avec le logo de la team HACKATONIA et un **effet d'animation laser printing** en
bleu ciel :

| Temps | Événement |
|-------|-----------|
| 0 s | Fond bleu marine, logo HACKATONIA apparaît (fade-in 300 ms) |
| 0,3 s | « **Hackathon** » se grave de gauche à droite avec un effet de **rayon laser** bleu ciel + lueur (`drop-shadow` + barre verticale glissante) |
| 1,5 s | « **Réalisé par l'équipe HACKATONIA** » s'écrit en dessous, même effet laser |
| 2,2 s | Les deux textes restent affichés ensemble en lueur stable |
| 3,5 s | Fondu de sortie (opacity 1 → 0) |
| 4 s | Carte révélée |

Caractéristiques :
- L'animation **ne bloque PAS** le chargement de l'application en arrière-plan
  (`position: fixed` au-dessus de l'app qui continue d'hydrater).
- Respecte la préférence `prefers-reduced-motion` (animations désactivées).
- Styles inline défensifs : le splash reste visible même si Tailwind n'a pas
  encore appliqué ses classes au tout premier rendu.
- Code source : [`frontend/components/SplashScreen.tsx`](frontend/components/SplashScreen.tsx),
  keyframes dans [`frontend/app/globals.css`](frontend/app/globals.css).

### ✅ Favicon multi-tailles à partir du logo

Un script Python ([`frontend/scripts/generer_favicons.py`](frontend/scripts/generer_favicons.py))
utilise **Pillow** pour générer toutes les déclinaisons :
- `app/favicon.ico` — 16×16 + 32×32 + 48×48 (un seul fichier multi-tailles)
- `public/apple-touch-icon.png` — 180×180 pour iOS/Safari
- `public/icon-192.png` + `public/icon-512.png` — pour PWA Android

Le `<head>` HTML est enrichi via les `metadata` Next.js (`title`, `description`,
`openGraph`, `keywords`).

### ✅ Coquille d'application navigable — 5 pages

| Page | URL | Statut P4 |
|------|-----|-----------|
| Accueil / Carte | `/` | ✅ Complète |
| Indicateurs | `/indicateurs` | ✅ Complète |
| Fiabilité | `/fiabilite` | ⏳ Coquille (P5) |
| Temps de traversée | `/prediction` | ✅ 3 blocs (temps actuel / mois / semaine) — P6.2 refondu 2026-06-23 |
| Administration | `/administration` | ⏳ Coquille (P6.4) |

Navigation accessible via :
- **Sidebar** desktop (≥ 1024 px) avec bouton de réduction icône-seulement
- **Drawer** sur tablette et mobile, déclenché par le bouton burger du topbar
- Marquage **`aria-pressed`** + `aria-label` traduits pour l'accessibilité

### ✅ Client API typé (`lib/api.ts`)

Client `fetch` minimal, typé en TypeScript strict, qui mirorise tous les endpoints
du backend :

```ts
import { api } from "@/lib/api";

const troncons = await api.troncons();
const etat = await api.carteEtat();
const indicateurs = await api.indicateurs(3, "7j");
const serie = await api.serieTemporelle(3, { granularite: "hour" });
const profil = await api.profilHoraire(3, "mardi", 90);
const evolution = await api.evolution();
const status = await api.collecteStatus();
await api.collecteStart();
await api.collecteStop();
const urlCsv = api.urlExportMesures({ troncon_id: 3, format: "csv" });
```

- Lit `NEXT_PUBLIC_API_BASE_URL` depuis l'environnement.
- Erreurs propagées via une classe `ApiError` dédiée (`statut`, `corps`).
- Utilisable côté serveur **et** côté client (Server Components, Route Handlers,
  composants `"use client"`).

### ✅ Page Accueil / Carte — cartographie temps réel

[`frontend/components/carte/PageCarte.tsx`](frontend/components/carte/PageCarte.tsx)
embarque **Leaflet** + **OpenStreetMap** centré sur la zone portuaire d'Abidjan :

| Fonctionnalité | Détail |
|----------------|--------|
| **6 tronçons polylines** colorés selon la classe de congestion (vert/orange/rouge) | Décodage du format Google Polyline (OSRM) côté client, repli sur segment droit origine → destination si polyline absente |
| **WebSocket `/ws/etat`** | Connexion automatique avec reconnexion exponentielle (1 s → 30 s) ; chaque mise à jour rafraîchit les couleurs des polylines sans recréer la carte |
| **Heatmap géographique** des congestions | Plugin `leaflet.heat` ; gradient orange → rouge ; échantillonnage des points le long des polylines pondéré par le niveau de congestion |
| **Popup détaillé** au clic | Tronçon, classe, temps actuel, **% rouge / orange / vert** (couleur Google Maps), heure de mesure, source, **motif DEESP humain** (« Tronçon tracé en rouge sur 12.5 % de sa longueur »), lien vers la fiche détaillée |
| **Zoom intelligent au chargement** | Sur le premier rendu, la carte se centre sur le **tronçon le plus dégradé** (worst classe DEESP puis worst % rouge). Si tous sont fluides, repli sur un cadrage global des 6 tronçons. |
| **Zoom intelligent au clic** sur la liste | `map.flyToBounds()` animé avec `fitBounds` autour du tronçon sélectionné |
| **Marqueurs POI** (`C`, `T`, `S`, `P`) | 4 pastilles colorées et étiquetées aux extrémités stratégiques : **C**ARENA (bleu), **T**oyota CFAO (rouge), **S**ODECI (vert), **P**alm Beach (navy). Tooltip au survol avec le libellé court. |
| **Panneau latéral enrichi** | Bandeau KPI (3 compteurs DEESP : *fluide / congestionné / indéterminé*) + carte « **Point chaud actuel** » avec liseré coloré, pourcentages rouge et orange, durée actuelle. La liste sous le bandeau est triée du plus dégradé au plus fluide. |
| **Panneau liste** (droite desktop, sous la carte mobile) | Les 6 tronçons avec couleur, nom, **barre couleur 3 segments rouge/orange/vert** (proportion Google Maps), temps actuel, source et horodatage |
| **Légende** | Codes couleur + ligne référence 50 km/h en bleu ciel |
| **Indicateur WebSocket** | Petit badge en haut à droite de la carte (`● temps réel` / `○ connexion…`) |

La carte reste **fluide au doigt** sur mobile (pinch-to-zoom et drag tactile
gérés nativement par Leaflet).

### ✅ Page Indicateurs — analyse complète (Recharts)

[`frontend/components/indicateurs/PageIndicateurs.tsx`](frontend/components/indicateurs/PageIndicateurs.tsx)
combine plusieurs visualisations :

| Bloc | Description | Source API |
|------|-------------|------------|
| **Sélecteurs** | Dropdown tronçon + boutons radio 24h / 7j / 30j / 90j | `getTroncons()` |
| **Barre de pilotage** | Badge « Mode planifié » avec **pastille à 3 états** (vert qui pulse en plage active / **bleu calme en veille la nuit** / gris arrêté) + libellé fidèle (« Collecte active / en veille / arrêtée ») + lignes **Plage active : 7h–19h (Africa/Abidjan)** et **Prochain cycle : aujourd'hui 18:40** ou **demain 07:00** + boutons **Démarrer / Arrêter la collecte** + boutons **Export CSV** et **Export Excel** | `collecteStatus`, `collecteStart`, `collecteStop`, `urlExportMesures` |
| **4 compteurs** | Temps moyen, minimum, maximum, nombre de mesures sur la période | `getIndicateursTroncon` |
| **3 cartes verdict couleur DEESP** | **Taux de congestion** (part de mesures congestionnées sur la période) + **% rouge moyen** (TRAFFIC_JAM) + **% orange moyen** (SLOW). Remplace les anciennes cartes FHWA TTI/PTI/BTI depuis le 2026-06-22. | idem |
| **Courbe Recharts** | 2 séries superposées : **temps moyen** (rouge plein), **temps maximal** (orange tirets), + **ligne référence 50 km/h en bleu ciel** | `getSerieTemporelle` |
| **Heatmap horaire jour × heure** | Grille 7 × 24 colorée du vert (fluide) au rouge (congestionné) selon le ratio temps observé / temps fluide ; survol → valeur précise | 7 appels parallèles à `getProfilHoraire(jour, fenetre=90j)` |
| **Évolution pluriannuelle** | Diagramme à barres comparant les temps min / moyen / max entre les campagnes officielles (`oct_2025` vs `fev_2026`) avec toggle **Jours ouvrables / Week-ends** | `getEvolution()` (table `evolution_indicateur` issue de P6.1) |

> **L'évolution pluriannuelle est la réponse directe au résultat n°4 de l'article 4
> du cahier des charges** (« Évolution de l'indicateur de performance temps de
> traversée »), explicitement mentionné dans le sous-titre du bloc.

> 💡 **Sélecteur de période — comment ça marche.** Les quatre boutons
> **24 h / 7 j / 30 j / 90 j** sont tous fonctionnels. Pour rester compatible
> avec le contrat backend qui attend un format `Nj` (`1j`, `7j`, `30j`, `90j`),
> le client API ([`frontend/lib/api.ts`](frontend/lib/api.ts)) traduit
> automatiquement « **24 h** » en `1j` avant d'appeler
> `/troncons/{id}/indicateurs`. **Tant que la collecte Google n'a pas accumulé
> plusieurs jours d'historique** (collecte démarrée le 19/06/2026), les quatre
> sélecteurs renvoient donc **le même contenu** : uniquement les mesures de la
> journée en cours. Les 2 016 mesures historiques de février 2025 (importées en
> P6.1) ne sont **pas** mélangées aux indicateurs temps réel — règle d'or du
> [CLAUDE.md § 2.5](CLAUDE.md) — mais elles alimentent en revanche la **heatmap
> horaire** et le **graphique d'évolution pluriannuelle** ci-dessus,
> indépendamment du sélecteur. Les écarts entre 7 j / 30 j / 90 j deviendront
> visibles au bout de quelques jours de collecte Google.

> 📐 **Compteur « Nb mesures »** : il porte sur **un seul tronçon** (celui
> sélectionné dans le dropdown). Pour le total des 6 tronçons, regarder
> `compteurs_jour.nb_mesures_total` renvoyé par `GET /collecte/status`.

> 🌙 **Mode veille nocturne automatique.** Le scheduler APScheduler du backend
> utilise un `CronTrigger` restreint à la **plage horaire** définie par
> `COLLECT_START_HOUR` et `COLLECT_END_HOUR` (par défaut **7h → 19h**, fuseau
> `Africa/Abidjan`). Conséquence : **aucune requête Google n'est émise entre
> 19h00 et 06:59** — la collecte reprend automatiquement le lendemain à 7h00
> sans aucune action manuelle. Le frontend reflète fidèlement cet état :
> pastille **verte qui pulse** quand un cycle peut tomber, **bleue calme**
> quand on est hors plage. Le libellé bascule de « **Collecte active** » à
> « **Collecte en veille** », et la ligne « Prochain cycle » passe de
> *aujourd'hui HH:MM* à *demain 07:00*. La détermination est faite côté client
> en lisant `config.plage_horaire` et l'heure courante convertie en
> `Africa/Abidjan` via `Intl.DateTimeFormat` — donc aucun nouvel endpoint
> backend nécessaire.

Tous les graphiques utilisent **`ResponsiveContainer`** : ils s'adaptent
automatiquement à la largeur de leur conteneur, donc lisibles à toutes les tailles
d'écran. La heatmap devient scrollable horizontalement sur mobile pour préserver
la lisibilité des cases.

### Comment vérifier le responsive

Dans le navigateur, ouvrir **DevTools** (F12) puis activer la **barre d'outils
appareils** :

- Chrome / Edge : `Ctrl + Shift + M`
- Firefox : `Ctrl + Shift + M`

Sélectionner ensuite :
- **iPhone SE (375 × 667)** — vérifier que le burger apparaît, sidebar cachée,
  carte ≤ hauteur écran, panneau dessous
- **iPad (768 × 1024)** — vérifier l'apparition des grilles 2-colonnes
- **Desktop ≥ 1024** — vérifier la sidebar et la carte sur 2/3 de la largeur

Pour tester la bascule FR/EN : cliquer sur **FR** ou **EN** dans le topbar →
toute l'interface bascule **instantanément**, sans rechargement.

Pour tester le thème : cliquer sur l'icône **🌙 / ☀️** → bascule clair / sombre,
persiste après un F5.

Pour rejouer le splash screen : il se rejoue à **chaque ouverture de fenêtre**
(nouvelle ouverture, F5, nouvel onglet).

### Ce qui n'est **pas encore** fait à la fin de P4

- ✅ Page **Fiabilité** : livrée en P5 (voir § 8bis ci-dessous)
- ✅ Page **Temps de traversée** : 3 blocs empilés sans saisie (temps actuel cascade Google → profils → 50 km/h, ce mois, cette semaine) calibrés par les GPX terrain (P6.2 refondu 2026-06-23)
- ❌ Page **Administration** : ajout/édition de tronçons *(arrive en P6.4)*
- ❌ **Polylines exactes** des 6 tronçons sur la carte : nécessite OSRM exposé
  (cf. CLAUDE.md § 8.3) — pour l'instant des **segments droits** entre origine
  et destination sont utilisés, ce qui reste lisible mais moins précis.

---

## 8bis · Ce qui est livré dans la phase P5 (validation terrain)

> **L'idée en une phrase :** on prend un fichier GPX issu d'un téléphone qui a
> parcouru un ou plusieurs des 6 tronçons, on découpe automatiquement la trace
> aux bornes officielles, on calcule le temps réel mesuré par tronçon, on le
> compare à la mesure Google la plus proche dans le temps, et on suit l'écart
> dans le temps pour détecter une dérive éventuelle des sources API.

### ✅ Endpoint d'import GPX

`POST /terrain/import` (multipart/form-data) accepte un fichier `.gpx` avec
horodatages. Pipeline :

1. **Parse** : `gpxpy` extrait les `<trkpt>` qui ont un `<time>` (les autres
   sont ignorés — sans timestamp on ne peut pas calculer une durée).
2. **Découpage automatique** : pour chaque tronçon des 6 actifs, on cherche
   dans la trace le point le plus proche de l'origine puis de la destination
   (rayon **80 m** — couvre l'imprécision GPS). Si trouvé et dans le bon
   ordre, on construit un segment.
3. **OSRM Match** (best-effort) : pour chaque segment, on appelle OSRM
   `/match/v1/driving/...` sur la sous-trace et on récupère une confiance
   (0..1). Si OSRM n'est pas accessible, le reste fonctionne quand même —
   seule la confiance reste à NULL.
4. **Appariement Google** : pour le timestamp médian du segment, on cherche
   dans `mesures` la ligne `source=google` (`duree_trafic_s NOT NULL`) la plus
   proche, dans une fenêtre de **30 minutes**. Calcul de
   ε = (T_terrain − T_api) / T_api.
5. **Persistance** : une ligne par tronçon détecté dans `releves_terrain`. Le
   GPX brut est conservé sur disque (`GPX_STORAGE_DIR`, défaut `./data/gpx`).

### ✅ Endpoints de lecture

| Endpoint | Rôle |
|----------|------|
| `GET /terrain/releves?troncon_id=...&limite=...` | Historique des relevés, du plus récent au plus ancien — inclut `nom_fichier_gpx` pour permettre au frontend de regrouper |
| `GET /terrain/releves/{id}/gpx` | Renvoie le **fichier GPX brut** stocké sur disque (avec garde anti directory-traversal). Utilisé par la page Fiabilité pour rejouer la prévisualisation cartographique d'une session passée |
| `GET /terrain/calibration?fenetre=4` | Moyenne mobile des écarts sur les 4 derniers relevés par tronçon (= facteur de calibration) |

### ✅ Script « Option A » — GPX synthétiques

Pour valider la boucle d'import **sans déplacement terrain**, le script
[`backend/app/generer_gpx_synthetiques.py`](backend/app/generer_gpx_synthetiques.py)
appelle OSRM `/route` pour chaque tronçon, décode la polyline retournée
(Google precision 5), interpole la trace à ~1 pt/s, et écrit un fichier GPX
1.1 standard.

```powershell
# Depuis le dossier backend, OSRM_BASE_URL doit pointer vers OSRM local Docker
docker compose exec backend python -m app.generer_gpx_synthetiques `
    --sortie /app/data/gpx_synth `
    --congestion 1.4 `
    --horodatage-debut "2026-06-19T14:00:00"
```

L'argument **`--horodatage-debut`** (ISO 8601, UTC par défaut) sert à
**caller** les GPX synthétiques sur une fenêtre où la collecte Google a
déjà tourné. Sans lui, le script utilise « aujourd'hui 08:00 UTC », et si
on teste en dehors des heures de collecte (par ex. samedi matin tôt), les
ε sortent à `null` faute de mesure API à apparier. Pour la démo, viser un
horaire représentatif (mi-après-midi d'un jour ouvré récent). Les 6 GPX
s'enchaînent avec 10 min de battement entre chacun, couvrant ~2h30 — ce qui
englobe largement plusieurs cycles Google de 20 min.

> 🧪 **Données synthétiques uniquement.** Ces GPX suivent le tracé OSRM
> théorique : ε proches de 0, et 1 trace peut « détecter » 2-3 tronçons
> contigus (ex. CARENA → Palm Beach passe à proximité de Toyota CFAO, donc
> les deux tronçons sont détectés). C'est utile pour valider la **boucle
> P5 de bout en bout** mais **NE remplace PAS** de vrais relevés terrain
> hebdomadaires. La calibration définitive nécessite des traces GPS issues
> d'un téléphone parcourant réellement les 6 tronçons (OsmAnd Tracker,
> Strava, GPX Logger…). Les fichiers générés ici sont **provisoires** et
> seront supprimés ou archivés à l'arrivée des premiers vrais GPX.

### 🧭 Mode actuel — simulation contrôlée

| Composant | Localisation | Statut |
|-----------|--------------|--------|
| Backend FastAPI + DB + Redis | **Railway** | ✅ Production |
| Frontend Next.js | **Local** (`npm start`) | ⏳ À déployer sur Vercel/Railway |
| Moteur OSRM | **Docker local uniquement** | ⏳ Pas exposé en prod |
| Relevés terrain GPX | **Synthétiques** (script `generer_gpx_synthetiques.py`) | ⏳ À remplacer par des traces téléphone |

**Ce qui est réel** : les mesures Google Routes (collecte planifiée 7h–19h),
le découpage automatique aux bornes des tronçons, l'appariement temporel
avec la mesure API la plus proche, la persistance dans la DB Railway,
l'affichage page Fiabilité.

**Ce qui est simulé** : les durées **terrain** elles-mêmes (générées via
OSRM théorique × facteur de congestion) et la confiance OSRM Match (`null`
faute d'OSRM en prod).

**Flux d'upload actuel** : navigateur → page Fiabilité locale
(`localhost:3030/fiabilite`) → POST direct vers le backend Railway.
Les conteneurs Docker locaux (`osrm`/`db`/`backend`) **ne sont nécessaires
QUE pour régénérer les GPX synthétiques**. Pour de simples uploads (qu'ils
soient synthétiques ou réels), aucun Docker requis — il suffit d'avoir le
frontend lancé.

**Migration vers le réel** :

1. Procurer un GPS smartphone (**OsmAnd Tracker** recommandé) à un opérateur PAA.
2. Sessions hebdomadaires : l'opérateur parcourt les 6 tronçons, exporte
   les `.gpx` du téléphone.
3. Upload via la même page Fiabilité — pas besoin de `--horodatage-debut`,
   les vraies heures sont dans le fichier.
4. (Optionnel) Exposer OSRM en prod via Oracle Cloud Free Tier (cf. CLAUDE.md
   § 8.3) pour récupérer `confiance_matching`.
5. (Optionnel) Purger les relevés synthétiques de la base :
   `DELETE FROM releves_terrain WHERE fichier_gpx LIKE '%gpx_synth%'` dans
   la Console Railway.

Les 6 fichiers produits dans `./backend/data/gpx_synth/troncon_*.gpx` sont
directement uploadables via `POST /terrain/import` ou via la page Fiabilité
(bouton **Importer le lot**).

### ✅ Page Fiabilité (frontend)

[`frontend/app/fiabilite/page.tsx`](frontend/app/fiabilite/page.tsx) compose
4 blocs depuis [`PageFiabilite.tsx`](frontend/components/fiabilite/PageFiabilite.tsx) :

| Bloc | Description |
|------|-------------|
| **3 KPI** | Date de la dernière session terrain ; **écart moyen global** (moyenne des écarts moyens par tronçon) ; **nombre de tronçons validés** (\|ε\| ≤ 10 %) |
| **Import GPX** | Input file `.gpx` **multi-fichiers** (sélection de 1 à 6+ fichiers en une fois) + bouton Importer → boucle séquentielle des POST, barre de progression, tableau consolidé avec le nom de fichier d'origine, gestion des erreurs ligne par ligne |
| **Prévisualisation cartographique** | **Carte Leaflet** affichant les 6 tronçons officiels (lignes pointillées) + la ou les traces GPX uploadées (or, en superposition) + marqueurs verts (début) / rouges (fin) aux bornes des tronçons détectés. Les traces sont parsées côté client dès la sélection du fichier — affichage instantané avant même l'upload. |
| **Évolution de l'écart** | Recharts LineChart, une ligne par tronçon, axe Y en pourcentage, ligne de référence à 0 % en bleu ciel pointillé. **Note** : tant qu'une seule session est importée, seuls les *dots* sont affichés (pas de trait) — Recharts a besoin de ≥ 2 points par tronçon pour tracer une polyligne. Les vraies courbes apparaissent dès la 2e session terrain hebdomadaire. |
| **Tableau de calibration** | Pour chaque tronçon : moyenne des 4 derniers écarts, dernier écart, statut coloré (vert ≤ 10 % / orange ≤ 25 % / rouge > 25 %) |

### Migrations de schéma 0004 et 0005

La migration **`backend/alembic/versions/0004_terrain_horodatage.py`** ajoute
3 colonnes à `releves_terrain` :

- `horodatage_passage` (datetime UTC) — instant médian du passage
- `duree_api_s` (int) — durée API utilisée comme référence
- `confiance_matching` (float 0..1) — confiance OSRM Match

La migration **`backend/alembic/versions/0005_contenu_gpx_bytea.py`** ajoute
une 4e colonne pour résoudre un bug critique de **persistance** :

- `contenu_gpx` (BYTEA) — contenu binaire du `.gpx`, **source de vérité**

**Pourquoi cette 5e migration** : sur Railway, le système de fichiers du
conteneur est **éphémère**. Tout redéploiement (push code) vide le disque,
et donc les `.gpx` stockés dans `/app/data/gpx/` disparaissent. La table
`releves_terrain` garde leur chemin mais le fichier n'existe plus → 404
permanent sur `/terrain/releves/{id}/gpx`.

En stockant le binaire directement dans la DB, on s'affranchit de
l'éphéméralité du disque. Survenance : transactionnelle, backup auto avec
PostgreSQL. Coût : ~100 Ko/relevé × N relevés = négligeable pour le volume
attendu (50-100 relevés/an).

```powershell
# Local
cd backend
alembic upgrade head

# Railway — depuis la Console du service backend
alembic upgrade head
```

### ✅ Stockage GPX : BYTEA en priorité, disque en repli

| Mode | Quand | Effet |
|------|-------|-------|
| **BYTEA en DB** | Toutes les nouvelles importations depuis migration 0005 | Source de vérité, survit aux redéploiements Railway |
| Disque local (`GPX_STORAGE_DIR`) | Dev local + repli pour relevés pré-0005 | Persistance hors Railway (Docker Compose, machines persistantes) |
| **HTTP 410 Gone** | Relevé sans contenu BYTEA + fichier perdu sur disque | Réponse explicite invitant à ré-uploader |

L'endpoint `GET /terrain/releves/{id}/gpx` essaie les trois sources dans
cet ordre, et le frontend ([`PageFiabilite.tsx`](frontend/components/fiabilite/PageFiabilite.tsx))
log silencieusement les 410 (relevés historiques) tout en remontant les
autres erreurs pour debug.

### Hydratation cartographique au montage

La page Fiabilité charge automatiquement la **dernière session terrain** au
montage, **sans aucun localStorage**. Le flux :

1. `GET /terrain/releves?limite=500` → identifie la session la plus récente
   par `date_session`
2. Pour chaque `nom_fichier_gpx` unique → `GET /terrain/releves/{id}/gpx`
3. Parse client-side → traces colorées sur la carte
4. Markers début/fin dédupés par libellé POI (CARENA / Toyota / SODECI /
   Palm Beach) avec badges numériques

Donc même après un F5, ou si l'utilisateur arrive directement sur l'URL
`/fiabilite`, la carte se peuple toute seule depuis la prod Railway.

---

## 9 · La page Rapport DEESP — alignement méthodologique PAA

> **TL;DR** — Cette page est la **réponse directe au rapport officiel
> DEESP/DEEF d'octobre 2025** du Port Autonome d'Abidjan. Elle reproduit ses
> **17 tableaux et 12 graphiques** dans le navigateur, alimentés par nos
> mesures temps réel. C'est la pièce qui transforme notre prototype en
> **outil opérationnel du processus officiel du PAA**.

### Pourquoi cette page existe (et pourquoi elle est différente d'« Indicateurs »)

L'application a **deux pages d'analyse**, et elles ne servent **pas au même
public** :

| Page | Pour qui | Indicateurs publiés | Fréquence de consultation |
|------|----------|--------------------|---------------------------|
| **`/indicateurs`** | **Opérateur du dispatch** qui suit la fluidité temps réel | Temps min / moyen / max sur la fenêtre choisie + verdict couleur DEESP (taux de congestion, % rouge moyen, % orange moyen) | Plusieurs fois par jour |
| **`/rapport`** (norme DEESP/DEEF officielle) | **DEESP/DEEF + direction PAA** qui rédigent les rapports semestriels | Temps min / moyen / max en minutes par axe × sens × type-jour, Tableau 16 des zones congestionnées | À chaque clôture mensuelle |

→ La page Indicateurs sert au **monitoring continu** (statut instantané basé
sur la couleur Google Maps actuelle, classification fluide / congestionné /
indéterminé). La page Rapport sert à la **production réglementaire** (les
chiffres qui finissent dans les comptes rendus officiels remontés à la
Direction Générale et au Ministère). **Les deux utilisent désormais la
même règle de congestion** (couleur Google Maps), depuis la refonte du
2026-06-22.

### Le principe de fonctionnement en 3 étages

```
┌─────────────────────────────────────────────────────────┐
│ 1. COLLECTE — 24h/24, 1 mesure / heure / tronçon       │
│    Google Routes (TRAFFIC_AWARE_OPTIMAL)               │
│    144 requêtes / jour                                  │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 2. FILTRE DEESP — couche `app/analyse/rapport_paa.py`  │
│    Ne garde que les mesures entre 7h et 19h            │
│    (conformité au rapport officiel)                    │
│    Distingue jour_ouvrable (lun-ven) vs week_end       │
│    Critère congestion : est_congestionne = TRUE        │
│    (lu depuis la couleur Google Maps — § 4.5.2bis)     │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 3. PUBLICATION — endpoints `/rapport/*` + page web     │
│    Tableau 1 : Distance + temps théorique 50 km/h      │
│    Tableaux 3-15 : Min/Moyen/Max par axe × type-jour   │
│    Tableau 16 : Tronçons congestionnés (règles 3 ou 4) │
│    Graphiques 1-12 : BarCharts par jour (min ou max)   │
└─────────────────────────────────────────────────────────┘
```

### Comment lire les 17 tableaux et 12 graphiques

#### Bloc 1 — Tableau 1 (temps théoriques)

Distance officielle des 3 axes + temps à 50 km/h calculé. Statique, dérivé
du seed des tronçons. C'est la **référence** contre laquelle on compare
toutes les mesures.

#### Bloc 2 — Tableaux 3 à 7 (temps MINIMAL)

Pour chaque tronçon et type-jour (ouvrable / week-end), le **temps minimum
observé** sur la campagne. Si un tronçon n'a *jamais* été en-dessous du
théorique, c'est un signe de congestion structurelle.

> **Exemple de lecture** : Tableau 4 (axe Toyota CFAO ↔ Palm Beach) affiche
> 12 mn (ouvrable) / 12 mn (week-end) dans le sens aller. Pour 8 km, le
> théorique est 9 min 36 s — on est donc à ~2 min au-dessus en condition
> idéale, lié probablement aux feux tricolores.

#### Bloc 3 — Tableaux 8 à 11 (temps MOYEN)

**Méthode DEESP particulière** : ce n'est pas la moyenne brute de toutes les
mesures. C'est la **moyenne des moyennes journalières** :

```
temps_moyen_mn = Σ ( moyenne_des_mesures_du_jour ) / nombre_de_jours
```

Cette méthode lisse les jours atypiques (manifs, accidents) sans les exclure.
C'est la valeur qui sert dans le rapport remonté à la Direction.

#### Bloc 4 — Tableaux 12 à 15 (temps MAXIMAL)

Plus grande durée observée. Met en évidence les **événements exceptionnels**.
Dans l'exemple du rapport oct. 2025 : 61 mn observées sur l'axe Palm Beach
→ CARENA un jour ouvrable, alors que la moyenne est de 37 mn.

#### Bloc 5 — Tableau 16 (zones congestionnées récurrentes)

**Le tableau opérationnellement le plus utile.** Liste les tranches horaires
où un tronçon a été congestionné selon les deux règles DEESP :

| Règle | Quand elle se déclenche |
|-------|--------------------------|
| **≥ 3 fois sur un jour-indicatif** | Le tronçon T1C est rouge 3 lundis sur 4, à 15h-16h → règle déclenchée |
| **≥ 4 fois dans la semaine** | Le tronçon T1C est rouge 4 jours différents (lun, mer, ven, sam), à 15h-16h → règle déclenchée |

Si **au moins une des deux** règles se déclenche pour un (tronçon, heure),
il apparaît dans le Tableau 16 avec un badge précisant **quelle règle** a
été déclenchée.

#### Bloc 6 — Graphiques 1 à 12 (BarCharts)

Exclusivement des **barres verticales** (pas de courbes), conformes au format
du rapport :

| Graphiques | Sens | Agrégat |
|------------|------|---------|
| 1, 3, 5 | Aller | Temps minimal par jour |
| 2, 4, 6 | Retour | Temps minimal par jour |
| 7, 9, 11 | Aller | Temps maximal par jour |
| 8, 10, 12 | Retour | Temps maximal par jour |

Axe X = jour calendaire de la campagne, axe Y = minutes entières. Une barre
= un point de mesure agrégé.

### Conformité au rapport officiel

L'application reproduit **tous** les éléments du rapport oct. 2025 :

| Élément du rapport DEESP | Implémentation | Endpoint API |
|--------------------------|----------------|--------------|
| Tableau 1 | TableauTempsTheoriques | `GET /rapport/temps-theoriques` |
| Tableaux 3 à 6 | TableauTempsTraversee (agregat='min') | `GET /rapport/temps-traversee` |
| Tableau 7 | Récap min sur les 3 axes | idem |
| Tableaux 8 à 10 | TableauTempsTraversee (agregat='moyen') | idem |
| Tableau 11 | Récap moyen | idem |
| Tableaux 12 à 14 | TableauTempsTraversee (agregat='max') | idem |
| Tableau 15 | Récap max | idem |
| Tableau 16 | TableauZonesCongestionnees | `GET /rapport/zones-congestionnees` |
| Tableau 17 | Synthèse (déduite) | idem |
| Tableau 19 | Comparaison pluriannuelle | `GET /rapport/comparaison` |
| Graphiques 1 à 12 | GraphiquesParAxe (BarChart Recharts) | `GET /rapport/graphique/{id}` |

### Comment l'utiliser en pratique (DEESP)

Pour produire le rapport mensuel du PAA :

1. **Sélectionner la campagne** (mois) dans le sélecteur en haut de page
   (input `<input type="month">`)
2. **Lire les blocs dans l'ordre** : Tableau 1 (référence) → Tableaux 3-15
   (temps observés) → Tableau 16 (zones rouges) → Graphiques 1-12
   (visualisation)
3. **Exporter** : tous les tableaux sont sélectionnables / copiables vers
   Excel ou Word ; les graphiques sont des images PNG capturables
4. **Comparer** : appeler manuellement
   `GET /rapport/comparaison?campagne_a=2025-10&campagne_b=2026-02` pour
   produire le Tableau 19 pluriannuel

### Limitations actuelles

- 🟡 La page est **techniquement opérationnelle** mais affiche peu de
  chiffres tant que la collecte n'a pas tourné **un mois complet** (28-30
  jours). Au 2026-06-21, on cumule ~2 jours.
- 🟡 La **comparaison pluriannuelle Tableau 19** nécessite au moins 2 mois
  d'historique. Elle utilisera la table `evolution_indicateur` (importée
  en P6.1 — fév 2025 vs oct 2025) en attendant que la collecte continue
  alimente les mois suivants.
- 🟢 La **conformité méthodologique** est garantie *quel que soit le volume
  de données* : si la collecte tourne 7 jours, les Tableaux 3-15 sont
  partiellement remplis mais déjà conformes (mêmes formules, même filtre
  7h-19h, même distinction ouvrable / week-end).

---

## 10 · Démarrer le projet sur ma machine

> ⚠️ Toutes les commandes ci-dessous se lancent dans **PowerShell sur Windows**,
> à la racine du projet (`C:\Users\…\fluidis`), pas dans un sous-dossier.

### Étape 1 — Installer Docker Desktop

[Télécharger Docker Desktop](https://www.docker.com/products/docker-desktop/) et
le lancer une fois. Tant que la baleine bleue 🐳 est visible en bas à droite,
Docker est prêt.

### Étape 2 — Préparer les fichiers de configuration

Le fichier `.env` contient les **mots de passe et clés d'API**. Il n'est pas
versionné sur Git pour des raisons de sécurité. On le crée à partir du modèle :

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Puis on ouvre `backend/.env` dans un éditeur et on remplit :

| Variable                | À quoi ça sert                                          | Comment l'obtenir                       |
|-------------------------|---------------------------------------------------------|-----------------------------------------|
| `POSTGRES_PASSWORD`     | Mot de passe de la base de données                      | Inventer un mot de passe long           |
| `API_SECRET_KEY`        | Clé secrète interne du backend                          | Inventer une chaîne aléatoire de ≥ 32 caractères |
| `GOOGLE_ROUTES_API_KEY` | Clé qui autorise l'appel à Google Routes                | Créer sur [Google Cloud Console](https://console.cloud.google.com/) |
| `ANTHROPIC_API_KEY`     | Clé pour le chatbot guide intégré (Claude)              | Créer sur [console.anthropic.com](https://console.anthropic.com/) — optionnelle, le chatbot est désactivé si absente |

> ⚠️ Si vous modifiez `POSTGRES_PASSWORD`, n'oubliez pas de le copier aussi
> dans la ligne `DATABASE_URL` juste en dessous.

### Étape 3 — Préparer le GPS interne OSRM (à faire une seule fois)

OSRM a besoin d'une carte d'Abidjan pour fonctionner. On télécharge donc la
carte d'OpenStreetMap, puis on la prépare en 3 étapes automatiquement :

```powershell
./osrm-data/prepare.ps1
```

Cette opération prend environ **3 à 5 minutes** (~80 Mo à télécharger). À la
fin, le dossier `osrm-data/` contiendra une dizaine de fichiers
`ivory-coast-latest.osrm.*`.

### Étape 4 — Démarrer les 5 services

```powershell
docker compose up -d
```

`-d` veut dire *"en arrière-plan"* (sinon vous verriez les logs défiler).

Vérifiez ensuite que tout est démarré :

```powershell
docker compose ps
```

Vous devez voir **5 services** en statut `running`. Les deux premiers (`db` et
`redis`) doivent en plus afficher `(healthy)`.

### Étape 5 — Initialiser la base de données

Trois commandes à enchaîner — elles sont idempotentes (on peut les relancer
sans casser quoi que ce soit) :

```powershell
# (a) Créer les 4 tables dans PostgreSQL
docker compose exec backend alembic upgrade head

# (b) Insérer les 6 tronçons officiels
docker compose exec backend python -m app.seed_troncons

# (c) Demander à OSRM de calculer le tracé exact de chaque tronçon
docker compose exec backend python -m app.complete_troncons
```

Si chaque commande affiche un message de succès (par ex. `6/6 tronçons mis à
jour`), **tout est prêt**.

---

## 11 · Vérifier que tout fonctionne (tests)

### Test 1 — Le backend répond

```powershell
curl http://localhost:8081/health
```

✅ Attendu : `{"status":"ok"}`

### Test 2 — La base contient bien les 6 tronçons avec leur tracé

```powershell
docker compose exec db psql -U paa -d paa_traffic -c "SELECT id, nom, distance_m FROM troncons ORDER BY id;"
```

✅ Attendu : 6 lignes (CARENA, Toyota CFAO, SODECI, et leurs retours respectifs).

### Test 3 — Google Routes répond en direct

```powershell
curl http://localhost:8081/diag/google/3
```

✅ Attendu : un JSON avec :
- `duree_trafic_s` : temps **avec** le trafic actuel
- `duree_sans_trafic_s` : temps **si la route était fluide**
- `ratio_trafic_sur_fluide` : un nombre ≥ 1,0 indiquant la « densité du
  bouchon » (1,0 = aucun bouchon ; 1,5 = 50 % plus long que la normale).

### Test 5 — La documentation interactive (mise à jour P3)

Ouvre dans le navigateur : http://localhost:8081/docs

✅ Tu vois maintenant **7 routeurs métier en français** (`tronçons`, `mesures`,
`profils`, `indicateurs`, `collecte`, `agrégation`, `export`, `carte`, plus le
WebSocket `temps réel`), chaque endpoint avec son résumé, sa description, et
un bouton « Try it out » pour l'essayer en direct.

### Test 6 — Le robot de collecte tourne (phase P2)

```powershell
# Déclenche un cycle immédiat sans attendre 20 minutes
irm -Method Post http://localhost:8081/collecte/run-once
```

✅ Attendu :
```
etat        : cycle_execute
nb_succes   : 6
nb_trous    : 0
nb_troncons : 6
nb_appels   : 6
```

Puis dans DBeaver (ou via `docker compose exec db psql`) :
```sql
SELECT id, troncon_id, horodatage, source, duree_trafic_s, vitesse_moyenne_kmh
FROM mesures ORDER BY horodatage DESC LIMIT 10;
```
✅ Attendu : 6 nouvelles lignes, source `google`, durées non nulles.

### Test 7 — Le statut du robot s'affiche correctement (phase P2)

```powershell
irm http://localhost:8081/collecte/status
```

✅ Attendu : un objet avec `actif: true`, la `prochaine_execution`, la
`prochaine_agregation` (≈ 23h00) et les compteurs du jour
(`nb_mesures_total`, `nb_succes`, `nb_trous`).

### Test 8 — L'agrégation des profils horaires fonctionne (phase P2)

```powershell
irm -Method Post http://localhost:8081/agregation/run
```

✅ Attendu :
```
etat                  : agregation_executee
nb_mesures_analysees  : 6
nb_aberrantes         : 0
nb_buckets            : 6
nb_lignes_profils     : 18   ← 6 buckets × 3 fenêtres (30/60/90 j)
fenetres_jours        : {90, 60, 30}
```

### Test 9 — Les indicateurs DEESP sont calculés (phase P3, refondue 2026-06-22)

```powershell
$r = irm "http://localhost:8081/troncons/3/indicateurs?periode=7j"
$r.snapshot
```

✅ Attendu : un objet contenant `min_s`, `moyenne_s`, `max_s`,
`taux_congestion`, `classe_congestion` (`fluide` / `congestionne` /
`indetermine`), `pourcentage_rouge_moyen`, `pourcentage_orange_moyen`,
`pourcentage_vert_moyen`, `temps_reference_50kmh_s`. **Plus de
`tti` / `pti` / `bti`** (cf. section « Refonte critère congestion »).

### Test 10 — L'état temps réel de la carte est prêt (phase P3, refondue)

```powershell
irm http://localhost:8081/carte/etat | ConvertTo-Json -Depth 4
```

✅ Attendu : un objet `troncons` contenant **6 entrées** avec, pour chacune :
géométrie (`polyline`, extrémités), `derniere_mesure`, `classe_congestion`,
`couleur_etat`, **`couleur_google.{pourcentage_rouge,orange,vert}`** et
`motif_congestion` (phrase humaine prête à afficher dans un popup Leaflet).

### Test 11 — Les exports Excel s'ouvrent correctement (phase P2)

```powershell
irm "http://localhost:8081/export/profils?fenetre_jours=30" -OutFile profils_30j.xlsx
Invoke-Item profils_30j.xlsx
```

✅ Attendu : Excel s'ouvre avec une feuille **« Synthèse »** + une feuille par
tronçon, chacune en format **heure × jour** (24 lignes × 7 colonnes) avec
moyenne en minutes.

### Test 12 — Le WebSocket pousse les mises à jour (phase P3)

Le plus simple si tu n'as pas d'outil WebSocket : ouvre la console de ton
navigateur (F12) sur `http://localhost:8081/docs` et tape :

```javascript
const ws = new WebSocket("ws://localhost:8081/ws/etat");
ws.onmessage = e => console.log(JSON.parse(e.data));
```

✅ Attendu : un premier message `{type: "snapshot", donnees: {...}}` arrive
immédiatement. Puis, si tu déclenches un cycle avec `irm -Method Post
http://localhost:8081/collecte/run-once` dans un autre terminal, un second
message `{type: "maj", donnees: {...}}` apparaît dans la console.

### Tout est OK ? Les phases P1, P2 et P3 sont validées ✅

---

## 12 · Comprendre les fichiers du projet

```
fluidis/
├── README.md              ← ce fichier
├── CLAUDE.md              ← le contexte complet du projet (à lire en premier)
├── docker-compose.yml     ← définit les 5 services qui doivent tourner ensemble
├── backend/               ← le code Python (l'API)
│   ├── .env.example       ← modèle des secrets à remplir
│   ├── Dockerfile         ← recette pour fabriquer l'image Docker du backend
│   ├── requirements.txt   ← liste des bibliothèques Python utilisées
│   ├── alembic/           ← scripts de création/évolution de la base de données
│   │   └── versions/      ← migrations 0001 → 0008 (la 0008 ajoute les pourcentages couleur DEESP)
│   └── app/
│       ├── main.py        ← point d'entrée de l'API (lifespan + 9 routeurs)
│       ├── core/config.py ← chargement des variables d'environnement (seuils TTI marqués legacy depuis 2026-06-22)
│       ├── db/session.py  ← connexion à PostgreSQL
│       ├── models/        ← description des 4 tables (en Python)
│       ├── sources/       ← appels vers Google Routes et OSRM
│       ├── collecte/      ← (P2) robot APScheduler de collecte
│       │   └── scheduler.py        ← jobs collecte (20 min) + agrégation (23h)
│       ├── agregation/    ← (P2) recalcul nocturne des profils horaires
│       │   └── profils.py          ← IQR + fenêtres glissantes 30/60/90 j
│       ├── analyse/       ← (P3) indicateurs DEESP — refondus 2026-06-22
│       │   ├── congestion.py        ← NOUVEAU : règles couleur DEESP (rouge OU orange ≥ 50 %)
│       │   ├── indicateurs.py       ← min/moyen/max + taux congestion + % rouge / orange moyens
│       │   └── rapport_paa.py       ← Tableaux 1-19 du rapport DEESP officiel
│       ├── etat/          ← (P3) construction d'états métier réutilisables
│       │   └── carte.py            ← état temps réel (HTTP + WebSocket)
│       ├── realtime/      ← (P3) diffusion temps réel
│       │   └── diffusion.py        ← singleton WebSocket broadcaster
│       ├── api/
│       │   ├── troncons.py    ← /troncons (liste + détail + indicateurs + mesures)
│       │   ├── mesures.py     ← (P2) /mesures (filtres transversaux)
│       │   ├── profils.py     ← (P2) /profils/troncons/{id}
│       │   ├── indicateurs.py ← (P3) /indicateurs/troncons/{id}/serie + heures-pointe
│       │   ├── collecte.py    ← (P2) /collecte/start /stop /status /run-once
│       │   ├── agregation.py  ← (P2) /agregation/run
│       │   ├── export.py      ← (P2) /export/mesures /export/profils
│       │   ├── carte.py       ← (P3) /carte/etat + WebSocket /ws/etat
│       │   └── diag.py        ← /diag/osrm /diag/google
│       ├── seed_troncons.py     ← script d'insertion des 6 tronçons
│       └── complete_troncons.py ← script qui complète les tracés via OSRM
├── frontend/              ← future page web (Next.js — vide en P1)
└── osrm-data/             ← cartes d'Abidjan pour le GPS interne
    ├── prepare.ps1        ← script de préparation OSRM (Windows)
    └── prepare.sh         ← script de préparation OSRM (Linux/macOS)
```

---

## 13 · Petit glossaire technique

| Mot                  | Explication simple                                                                                            |
|----------------------|---------------------------------------------------------------------------------------------------------------|
| **API**              | « Une porte d'entrée informatique » : un programme qui répond à des questions précises via des URL.           |
| **Backend**          | La partie « invisible » qui calcule et stocke les données (par opposition au **frontend**, la page web).      |
| **Conteneur Docker** | Un mini-ordinateur virtuel et isolé contenant un seul logiciel prêt à l'emploi.                               |
| **Base de données**  | Tableur géant et ultra-rapide qui garde des données structurées en tables.                                    |
| **PostgreSQL**       | La marque de base de données qu'on utilise (gratuite, populaire, fiable).                                     |
| **Migration**        | Une instruction qui modifie la structure de la base (ajout d'une table, d'une colonne…).                      |
| **Alembic**          | L'outil qui exécute les migrations dans l'ordre, sans casser les données existantes.                          |
| **Cache (Redis)**    | Stockage temporaire ultra-rapide pour éviter de refaire 100× le même calcul.                                  |
| **OSRM**             | Notre GPS hors-ligne (Open Source Routing Machine) : calcule des itinéraires sur la carte d'Abidjan.          |
| **Polyline**         | Représentation compacte d'un tracé sur la carte (une suite de lat/lon encodée en quelques caractères).        |
| **`localhost`**      | Votre propre ordinateur, vu depuis lui-même. Toutes les URL commençant par `localhost:` sont locales.         |
| **Port** (ex. 8081)  | Le « numéro de porte » d'un service sur votre ordinateur. `:8081` désigne le backend, `:3000` le frontend.    |
| **`.env`**           | Fichier texte contenant les secrets (mots de passe, clés). **Ne jamais le partager ni le mettre sur Git.**    |
| **APScheduler**      | Bibliothèque Python qui programme des tâches répétitives — c'est notre « réveil programmable » interne (P2).  |
| **Backoff exponentiel** | Stratégie de nouvelle tentative qui attend de plus en plus longtemps entre chaque essai (1 s, 2 s, 4 s…).  |
| **Trou de mesure**   | Ligne dans `mesures` avec `duree_trafic_s = NULL` : « on a essayé, ça n'a pas marché, on garde la trace » (P2). |
| **IQR**              | *Interquartile Range* — méthode statistique pour détecter les valeurs très éloignées du reste (P2).            |
| **Fenêtre glissante**| Période qui « avance » avec le temps : « les 30 derniers jours » se redéfinit chaque jour (P2).               |
| **Profil horaire**   | Statistiques agrégées par (tronçon, jour de la semaine, heure) — sert à dire « le mardi à 8h c'est X » (P2).  |
| **FHWA**             | *Federal Highway Administration* (USA). Norme TTI / PTI / BTI **retirée du projet le 2026-06-22** au profit du critère couleur DEESP officiel. |
| **TTI / PTI / BTI**  | *Legacy* — Travel Time Index / Planning Time Index / Buffer Time Index. **Plus calculés** depuis le 2026-06-22 (cf. section « Refonte critère congestion »). |
| **`speedReadingIntervals`** | Champ Google Routes (`travelAdvisory.speedReadingIntervals`) qui donne pour chaque portion de la polyline un enum `Speed` (NORMAL/SLOW/TRAFFIC_JAM) = vert/orange/rouge sur Maps. C'est **la source officielle** des couleurs DEESP. |
| **Temps de référence** | Temps théorique à 50 km/h calculé depuis la distance officielle du tronçon (Tableau 1 du rapport DEESP). |
| **WebSocket**        | Connexion permanente entre serveur et navigateur, par où le serveur peut **pousser** des messages (P3).        |
| **Polling**          | Inverse du WebSocket : le client demande régulièrement « du nouveau ? ». Plus lourd et plus lent.              |
| **Swagger / OpenAPI**| Page web auto-générée qui documente l'API et permet de tester chaque route depuis le navigateur (`/docs`).     |

---

## 14 · Problèmes fréquents et solutions

### « Le port 8000 est déjà utilisé / je n'arrive pas à démarrer le backend »

Windows réserve la plage 7981–8080 (vérifiable avec
`netsh interface ipv4 show excludedportrange protocol=tcp`). C'est pour ça
qu'on utilise **`:8081`** et non `:8000`. Si vous voyez encore une erreur de
port, regardez `docker-compose.yml` : la ligne `"8081:8000"` peut être changée
en `"8082:8000"` (puis adapter `frontend/.env.local`).

### « OSRM affiche `Required files are missing` »

Vous avez sauté l'étape 3 du démarrage. Lancez `./osrm-data/prepare.ps1` puis
`docker compose restart osrm`.

### « `service "backend" is not running` quand je tape `docker compose exec backend …` »

Le backend a planté ou n'a jamais démarré. Vérifiez avec :

```powershell
docker compose ps                       # est-il listé ?
docker compose logs backend --tail 30   # quel est le dernier message d'erreur ?
docker compose up -d backend            # tenter de le relancer
```

### « DNS / `No address associated with hostname` »

Docker Desktop sur Windows perd parfois le DNS après un `restart`. Le plus
fiable : `docker compose down` puis `docker compose up -d` (un redémarrage
complet rétablit le réseau).

### « Je suis dans `backend/` mais `docker compose up` ne marche pas »

Le fichier `docker-compose.yml` est à la **racine** du projet. Faites
`cd ..` pour remonter d'un dossier, puis relancez la commande.

### « Je veux tout effacer et repartir de zéro »

```powershell
docker compose down -v   # supprime les conteneurs ET les volumes (base de données vidée)
```

Puis recommencer depuis l'étape 4 du démarrage.

---

## 14bis · P6.9 — Segments GPX libres et précision progressive des temps de traversée

### Ce que c'est

La page **Fiabilité** comporte désormais un deuxième système d'import GPX,
indépendant du système de validation terrain (P5). Là où P5 exigeait une trace
couvrant l'intégralité d'un tronçon (de CARENA à Palm Beach sans s'arrêter),
**P6.9 accepte n'importe quelle sous-portion** : de CARENA à GMA, de DGI à
Terminus 19, de Sim Ivoire au Carrefour Seamen's…

C'est le format naturel des enregistrements terrain réels : on s'arrête aux feux,
on coupe l'enregistrement au parking, on reprend plus loin. Aucune contrainte.

### Comment ça marche techniquement

```
Session terrain
   ├── Fichier GPX A  : CARENA → GMA          (7:23)
   ├── Fichier GPX B  : GMA → Commissariat    (3:12)
   ├── Fichier GPX C  : Commissariat → Sim    (1:44)
   ├── ...
   └── Fichier GPX L  : Olibia → Palm Beach   (2:09)
                                              ──────
                        Durée totale tronçon 1 aller : 39:37 min
```

Le backend **somme** les durées de tous les segments d'une même session
(`session_id`) pour reconstituer le temps de traversée de bout en bout.
Avec plusieurs sessions importées, il en fait la **moyenne** — l'estimation
se stabilise au fil du temps.

### Comment la confiance s'améliore

L'indice de confiance (0 → 100 %) visible dans le tableau de résumé combine :

- **La couverture géographique** : quelle fraction de la distance totale du
  tronçon les segments couvrent-ils ?
- **Le nombre de sessions** : plus on répète la mesure, moins la variance
  individuelle compte.

```
confiance = couverture % × min(nb_sessions, 8) / 8
```

| Sessions importées | Couverture moy. | Confiance | Interprétation |
|--------------------|----------------|-----------|----------------|
| 1 | 85 % | 11 % | Estimation préliminaire |
| 2 | 85 % | 21 % | Début de tendance |
| 4 | 85 % | 43 % | Estimé intermédiaire |
| 8 | 85 % | **85 %** | Fiable |
| 8 | 100 % | **100 %** | Pleine confiance |

**Cible recommandée :** 4 sorties terrain couvrant chacune ≥ 80 % du tronçon,
à des heures différentes (matin pointe + hors-pointe) → confiance ≥ 40 %.
8 sorties → confiance ≥ 85 %.

### Miroir aller/retour

Quand un sens manque de données directes (ex. aucun GPX pour tronçon 6
Palm Beach→SODECI), le système utilise provisoirement le temps du **sens
opposé** (tronçon 5 SODECI→Palm Beach). C'est une approximation valable en
première estimation — les deux sens empruntent les mêmes routes, souvent
avec des conditions comparables. La précision s'améliore dès qu'une vraie
session directe est importée.

### Règle d'import par l'interface — un tronçon par lot

> **Tous les fichiers GPX d'un même import doivent appartenir au même tronçon.**

La raison : l'interface envoie le même `troncon_id` et le même `session_id`
pour tous les fichiers du lot. Si on mélange des fichiers de tronçons différents
sans préciser l'id, ils arrivent sans affectation et n'apparaissent dans aucun
résumé.

**Procédure pour une nouvelle sortie terrain :**

1. Ouvrir la page **Fiabilité** → section « Importer des segments GPX libres ».
2. Sélectionner les fichiers GPX du **tronçon 1 aller** (CARENA → Palm Beach).
3. Régler : Tronçon = **1**, Direction = **Aller**, Session = ex. `20260630_A`.
4. Cliquer **Importer**.
5. Répéter pour le **tronçon 2 retour** (même session `20260630_A`, tronçon = **2**), etc.

| Tronçon | ID | Sens |
|---------|----|----- |
| CARENA → Palm Beach | **1** | Aller |
| Palm Beach → CARENA | **2** | Retour |
| Toyota CFAO → Palm Beach | **3** | Aller |
| Palm Beach → Toyota CFAO | **4** | Retour |
| SODECI → Palm Beach | **5** | Aller |
| Palm Beach → SODECI | **6** | Retour |

### Ce que le tableau de résumé affiche

Après chaque import, le tableau « Temps de traversée par tronçon » se
rafraîchit automatiquement et montre pour chaque axe :

- **Temps moyen** (mm:ss) — moyenne des N sessions
- **Min / Max** — plage observée entre la session la plus rapide et la plus lente
- **Couverture** (%) — quelle fraction de l'axe les segments couvrent
- **Barre de confiance** (rouge → vert) — fiabilité globale de l'estimation
- **Badge** direct (bleu) ou miroir (jaune) — indique si l'estimation est basée
  sur des mesures directes ou sur le sens opposé

---

## 16 · Module Incidents & Accidents — P8 (planifié 2026-06-24)

Ce module ajoute une **veille automatique des incidents de circulation** dans la
zone portuaire d'Abidjan en scrutant la presse ivoirienne toutes les 30 minutes.

### Ce que fait le module

| Fonctionnalité | Description |
|---|---|
| **Scraping RSS** | Fraternité Matin, Abidjan.net, Koaci — flux RSS analysés toutes les 30 min |
| **Détection par mots-clés** | 20 mots-clés : accident, collision, bouchon, route barrée, Treichville, Port d'Abidjan… |
| **Extraction de lieu** | Dictionnaire de 15 lieux de référence de la zone portuaire |
| **Géocodage** | Nominatim OpenStreetMap (gratuit) — filtre sur la bbox portuaire |
| **Classification** | Type (accident / embouteillage / route barrée / travaux) + sévérité (mineur / moyen / grave) |
| **Page Incidents** | Carte Leaflet des markers colorés + liste chronologique filtrée |
| **Overlay carte principale** | Incidents actifs (<6h) affichés en superposition sur la carte Accueil |
| **Badge nav** | Compteur rouge dans la navigation si un incident actif est recensé |

### Architecture technique

```
backend/app/sources/
  scraper_incidents.py      # orchestrateur multi-source
  parsers/rss_parser.py     # feedparser + filtre mots-clés
  parsers/html_parser.py    # BeautifulSoup4 pour sites sans RSS

backend/app/analyse/
  incidents_nlp.py          # extraction lieu, type, sévérité + Nominatim

backend/app/api/
  incidents.py              # GET /incidents, GET /incidents/stats, POST /incidents/enrichir

frontend/app/incidents/
  page.tsx                  # page principale

frontend/components/incidents/
  CarteIncidents.tsx        # carte Leaflet markers incidents
  ListeIncidents.tsx        # liste chronologique
  FiltresIncidents.tsx      # filtres type/période/tronçon
```

---

### P9 — Chatbot guide intégré (Claude + RAG)

```
backend/app/api/
  chatbot.py                # POST /chatbot/message (relais Claude + injection RAG)
                            # GET  /chatbot/disponibilite

backend/app/rag/
  contexte.py               # detecter_intentions() + 5 récupérateurs DB
                            # construire_contexte_rag() — point d'entrée principal

frontend/components/chatbot/
  ChatbotButton.tsx         # bouton flottant + fenêtre de chat
```

Le chatbot utilise l'API Claude (Anthropic) via un endpoint backend sécurisé.
La clé `ANTHROPIC_API_KEY` reste côté serveur — elle n'est jamais exposée dans le navigateur.

**RAG — données injectées automatiquement selon la question :**

| Question type | Données injectées |
|---|---|
| État du trafic, congestion, carte | État DEESP + % couleurs + durée de chaque tronçon |
| Meilleure heure, quand partir, livraison | Top-3 créneaux optimaux du type de jour (ouvrable/week-end) |
| Temps de traversée, durée, combien de minutes | Dernière mesure Google + écart vs référence 50 km/h |
| Incidents, accidents, route barrée | Incidents actifs < 6h avec sévérité et source |
| Statistiques, indicateurs, taux | Min/moy/max + taux congestion depuis le lundi courant |

**Variables d'environnement :**

| Variable | Côté | Valeur |
|---|---|---|
| `ANTHROPIC_API_KEY` | Backend | Clé API Anthropic (sk-ant-...) |

**Activer en production Railway :**
```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-... --service backend
# Puis redémarrer le service pour que la clé soit lue
```

### Sources surveillées

| Source | URL | Type |
|--------|-----|------|
| Fraternité Matin | fraternitematin.ci | RSS |
| Abidjan.net | news.abidjan.net | RSS |
| Koaci | koaci.com | RSS |
| L'Infodrome | linfodrome.ci | HTML (scraping) |
| Soir Info | soir-info.ci | HTML (scraping) |

> **Pas de clé API requise.** Nominatim (géocodage) est gratuit et sans
> inscription. Les 5 sources de presse sont accessibles publiquement.

### Feuille de route P8

| Sous-phase | Description | Dépendances |
|------------|-------------|-------------|
| P8.1 | Fondations : migration `incidents`, scraper RSS, scheduler 30 min, endpoints `GET /incidents` | — |
| P8.2 | NLP légère + géocodage Nominatim + attribution tronçon | P8.1 |
| P8.3 | Frontend page /incidents (carte + liste + filtres) | P8.2 |
| P8.4 | Overlay sur carte principale + badge nav | P8.3 |
| P8.5 (opt.) | Déduplication cross-sources + export CSV | P8.4 |

Les **4 prompts d'implémentation** sont dans [CLAUDE.md § 10.5](CLAUDE.md).

---

## 15 · La suite du projet

Sept phases au total (voir [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases)).

| Phase     | Objectif                                                            | État               |
|:---------:|---------------------------------------------------------------------|--------------------|
| **P1**    | **Fondations** (infrastructure, modèle de données)                  | ✅ **terminée**    |
| **P2**    | **Robot de collecte + agrégation nocturne + exports**               | ✅ **terminée**    |
| **P3**    | **Indicateurs FHWA + API restructurée + WebSocket**                 | ✅ **terminée**    |
| **P6.1**  | **Import des 2 016 mesures terrain Fév 2025 + comparatif pluriannuel** | ✅ **terminée** |
| **Déploiement** | **Backend en ligne sur Railway** (collecte 24h/24 démarrée)   | ✅ **terminé**     |
| **P4**    | **Frontend Next.js complet : carte Leaflet, Indicateurs Recharts, splash HACKATONIA, i18n FR/EN, thème clair/sombre** | ✅ **terminée**    |
| P5        | Validation hebdomadaire par relevés GPS terrain                     | ✅ **terminée**    |
| P6.2/6.4  | Temps de traversée par période + ajout de parcours admin | ✅ **terminées**   |
| **P8**    | **Module Incidents & Accidents** (scraping presse, géoloc, page dédiée) | ⏳ À faire |
| P7        | Tests, cache Redis, déploiement Vercel, rapport final + pitch       | ⏳ À faire         |

À la fin de P8 + P7, l'application sera prête pour la démo au jury du hackathon.
