"""Point d'entrée FastAPI du backend PAA-Traverse.

Organisation des routeurs (phase P4) :

  - /troncons     — référentiel + dernier état + indicateurs sur période
  - /mesures      — accès transversal aux mesures (filtres)
  - /profils      — profils horaires agrégés (lecture)
  - /indicateurs  — séries temporelles + heures de pointe
  - /collecte     — pilotage du robot de collecte (start/stop/status/run-once)
  - /export       — exports CSV / XLSX
  - /carte        — état temps réel pour la cartographie
  - /ws/etat      — WebSocket de diffusion temps réel (push à chaque cycle)

Endpoints utilitaires conservés :
  - /agregation/run    — déclenche manuellement le recalcul des profils
  - /diag/{source}/{id}— diagnostic ponctuel des sources de mesure
  - /health            — sonde de disponibilité
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agregation import router as agregation_router
from app.api.import_data import router as import_router
from app.api.carte import router as carte_router
from app.api.carte import router_ws as carte_ws_router
from app.api.collecte import router as collecte_router
from app.api.diag import router as diag_router
from app.api.evolution import router as evolution_router
from app.api.export import router as export_router
from app.api.indicateurs import router as indicateurs_router
from app.api.mesures import router as mesures_router
from app.api.administration import router as administration_router
from app.api.predire import router as predire_router
from app.api.profils import router as profils_router
from app.api.rapport import router as rapport_router
from app.api.terrain import router as terrain_router
from app.api.segments import router as segments_router
from app.api.troncons import router as troncons_router
from app.collecte.scheduler import arreter_scheduler, demarrer_scheduler
from app.core.config import get_settings


# Configuration minimale du logger applicatif (les journaux `paa.*` héritent
# de cette configuration ; APScheduler et Uvicorn ont leurs propres loggers).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# Chargement unique de la configuration au démarrage du module
settings = get_settings()


# ---------------------------------------------------------------------------
# Cycle de vie : démarrage / arrêt du scheduler APScheduler
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Démarre le scheduler au boot et l'arrête proprement à la fermeture."""
    try:
        demarrer_scheduler()
    except Exception:
        # On laisse l'API démarrer même si le scheduler échoue : les endpoints
        # /collecte/start permettront de réessayer après correction.
        logging.exception("Échec du démarrage initial du scheduler de collecte.")
    try:
        yield
    finally:
        try:
            arreter_scheduler()
        except Exception:
            logging.exception("Échec de l'arrêt propre du scheduler de collecte.")


# ---------------------------------------------------------------------------
# Métadonnées Swagger — pour une page /docs lisible et professionnelle
# ---------------------------------------------------------------------------


_TAGS_METADATA = [
    {
        "name": "tronçons",
        "description": (
            "Référentiel des 6 tronçons dirigés du Port Autonome d'Abidjan. "
            "Liste enrichie du dernier état, détail, mesures brutes et snapshot "
            "d'indicateurs sur une période glissante."
        ),
    },
    {
        "name": "mesures",
        "description": (
            "Accès transversal aux mesures (succès et trous). Filtres par tronçon, "
            "source, plage de dates locales (Africa/Abidjan)."
        ),
    },
    {
        "name": "profils",
        "description": (
            "Profils horaires agrégés (moyenne, médiane, p95, …) calculés chaque "
            "nuit sur des fenêtres glissantes de 30, 60 et 90 jours."
        ),
    },
    {
        "name": "indicateurs",
        "description": (
            "Indicateurs DEESP : temps min / moyen / max, taux de congestion "
            "(critère couleur Google Maps), pourcentages rouge/orange/vert "
            "moyens, série temporelle, heures de pointe."
        ),
    },
    {
        "name": "collecte",
        "description": (
            "Pilotage du robot APScheduler de collecte des temps de parcours "
            "(start, stop, status, déclencheur manuel)."
        ),
    },
    {
        "name": "agrégation",
        "description": (
            "Déclencheur manuel du recalcul nocturne des profils horaires (job "
            "planifié chaque nuit à 23h00 — Africa/Abidjan)."
        ),
    },
    {
        "name": "export",
        "description": (
            "Exports CSV et XLSX des mesures brutes et des profils horaires "
            "(tableau pivoté heure × jour)."
        ),
    },
    {
        "name": "carte",
        "description": (
            "État temps réel des tronçons pour la cartographie Leaflet : "
            "géométrie, dernière mesure, pourcentages couleur Google Maps, "
            "classe de congestion DEESP (fluide / congestionné / indéterminé)."
        ),
    },
    {
        "name": "temps réel (WebSocket)",
        "description": (
            "Diffusion push : à chaque nouvelle mesure, le serveur émet le snapshot "
            "carte à tous les clients abonnés à `/ws/etat`."
        ),
    },
    {
        "name": "import données historiques",
        "description": (
            "Import one-shot des fichiers Excel terrain : "
            "Base_Nettoyee_PAA_Fev2025 (2016 mesures, source=historique_paa_2025) "
            "et SYNTHESE COMPAREE FEVRIER_2026 (indicateurs pluriannuels)."
        ),
    },
    {
        "name": "validation terrain",
        "description": (
            "Import hebdomadaire des relevés terrain GPX (P5) : découpage "
            "automatique de la trace par tronçon via OSRM Match, appariement "
            "avec la mesure Google la plus proche, calcul de l'écart relatif "
            "et du facteur de calibration par tronçon."
        ),
    },
    {
        "name": "segments terrain (GPX libres)",
        "description": (
            "Accumulation progressive de sous-sections GPX enregistrées librement "
            "(entre landmarks intermédiaires, sans obligation de couvrir un tronçon "
            "officiel en entier). Les segments s'agrègent par session pour reconstituer "
            "les temps de traversée par axe. La précision s'améliore à chaque nouvelle "
            "session importée. Miroir aller/retour appliqué quand un sens manque."
        ),
    },
    {
        "name": "rapport DEESP",
        "description": (
            "Reproduit les 17 tableaux et 12 graphiques du rapport officiel "
            "DEESP/DEEF (cf. CLAUDE.md § 4.5) — temps min/moyen/max par axe "
            "× sens × type-jour, identification des tronçons congestionnés "
            "selon les règles d'occurrence du rapport (≥ 3/jour-indicatif "
            "ou ≥ 4/semaine), comparaison pluriannuelle entre campagnes."
        ),
    },
    {
        "name": "temps de traversée par période",
        "description": (
            "Résumé des temps de traversée sur 3 horizons temporels : "
            "période courante (cascade Google → profils 60 j → 50 km/h), "
            "semaine en cours et mois en cours (min/moyen/max depuis les "
            "mesures Google réelles, séparés jours-ouvrables/week-ends). "
            "La précision de l'estimation courante est améliorée par les "
            "relevés GPX terrain importés via la page Fiabilité."
        ),
    },
    {
        "name": "administration",
        "description": (
            "P6.4 — CRUD tronçons + sous-tronçons codifiés (T1A, T1B, T1C, "
            "T2A...) selon la convention DEESP. Suppression toujours LOGIQUE. "
            "Sans dépendance OSRM — la géométrie est calculée à partir des "
            "waypoints fournis par l'utilisateur."
        ),
    },
    {
        "name": "diagnostic",
        "description": "Tests ponctuels des sources de mesure (Google, OSRM).",
    },
    {"name": "système", "description": "Sonde de disponibilité."},
]


app = FastAPI(
    title="PAA-Traverse — API de suivi des temps de traversée",
    description=(
        "API du **Port Autonome d'Abidjan** pour le suivi en temps réel et "
        "l'analyse historique des temps de parcours sur les axes stratégiques "
        "de la zone portuaire.\n\n"
        "**Cascade de mesure** : Google Routes (TRAFFIC_AWARE_OPTIMAL) → "
        "profils horaires 60 j (P6) → temps de référence 50 km/h via OSRM.\n\n"
        "**Indicateurs DEESP** : temps min / moyen / max, taux de congestion "
        "(critère couleur Google Maps), classification fluide / congestionné, "
        "heures de pointe.\n\n"
        "**Temps réel** : un WebSocket `/ws/etat` diffuse l'état carte à chaque "
        "nouveau cycle de collecte."
    ),
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=_TAGS_METADATA,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS — les origines autorisées proviennent de la variable d'environnement
# ALLOWED_ORIGINS (CSV), parsée par pydantic-settings dans config.py.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Sonde de disponibilité
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    summary="Vérifie que l'API est en ligne",
    description="Sonde utilisée par Docker et le monitoring pour valider la disponibilité du backend.",
    tags=["système"],
)
async def health() -> dict[str, str]:
    """Retourne un statut simple confirmant que le service répond."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Câblage des routeurs (l'ordre détermine la lecture du /docs)
# ---------------------------------------------------------------------------
app.include_router(troncons_router)
app.include_router(mesures_router)
app.include_router(profils_router)
app.include_router(indicateurs_router)
app.include_router(collecte_router)
app.include_router(agregation_router)
app.include_router(export_router)
app.include_router(carte_router)
app.include_router(carte_ws_router)
app.include_router(import_router)
app.include_router(evolution_router)
app.include_router(terrain_router)
app.include_router(segments_router)
app.include_router(rapport_router)
app.include_router(predire_router)
app.include_router(administration_router)
app.include_router(diag_router)
