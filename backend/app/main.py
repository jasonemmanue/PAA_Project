"""Point d'entrée FastAPI du backend PAA-Traverse.

À ce stade (phase P1 — fondations), l'API n'expose qu'une route `/health` qui
permet de vérifier que le service est en ligne. La logique métier (collecte,
indicateurs, cartographie) sera ajoutée dans les phases ultérieures.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diag import router as diag_router
from app.core.config import get_settings

# Chargement unique de la configuration au démarrage du module
settings = get_settings()

app = FastAPI(
    title="PAA-Traverse API",
    description=(
        "API de suivi et de visualisation en temps réel des temps de traversée "
        "des axes routiers stratégiques du Port Autonome d'Abidjan."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
