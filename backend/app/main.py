"""Point d'entrée FastAPI du backend PAA-Traverse.

Phase P2 : ajout du robot de collecte planifié (APScheduler). Le scheduler
est démarré au lancement du serveur et arrêté proprement à la fermeture, via
le mécanisme `lifespan` de FastAPI.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agregation import router as agregation_router
from app.api.collecte import router as collecte_router
from app.api.diag import router as diag_router
from app.api.export import router as export_router
from app.api.troncons import router as troncons_router
from app.collecte.scheduler import arreter_scheduler, demarrer_scheduler
from app.core.config import get_settings

# Configuration minimale du logger applicatif (le journal `paa.collecte` du
# scheduler hérite de cette configuration).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# Chargement unique de la configuration au démarrage du module
settings = get_settings()


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


app = FastAPI(
    title="PAA-Traverse API",
    description=(
        "API de suivi et de visualisation en temps réel des temps de traversée "
        "des axes routiers stratégiques du Port Autonome d'Abidjan."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuration CORS — les origines autorisées proviennent de l'environnement
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    summary="Vérifie que l'API est en ligne",
    description="Sonde utilisée par Docker et le monitoring pour valider la disponibilité du backend.",
    tags=["système"],
)
async def health() -> dict[str, str]:
    """Retourne un statut simple confirmant que le service répond."""
    return {"status": "ok"}


# Routeurs métier
app.include_router(diag_router)
app.include_router(collecte_router)
app.include_router(agregation_router)
app.include_router(troncons_router)
app.include_router(export_router)
