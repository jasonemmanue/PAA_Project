"""Routeur /carte — état temps réel des tronçons + WebSocket de diffusion.

  - GET       /carte/etat → snapshot synchrone (rafraîchissement périodique).
  - GET       /carte/resume-axes → temps actuel + min/moy/max de tous les axes.
  - WebSocket /ws/etat    → push à chaque nouvelle mesure (rafraîchissement live).

Le WebSocket n'est pas sous le préfixe `/carte` pour respecter la convention
de ton brief (`/ws/etat`) ; il est exposé dans le même fichier pour cohérence.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collecte.plage import lire_plage_collecte
from app.core.config import get_settings
from app.db.session import get_db
from app.etat.carte import construire_etat_carte
from app.models.models import Troncon
from app.predicteur.profils import _prediction_google, _prediction_jour_type
from app.realtime.diffusion import get_diffuseur


logger = logging.getLogger("paa.realtime")


router = APIRouter(prefix="/carte", tags=["carte"])
router_ws = APIRouter(tags=["temps réel (WebSocket)"])


# ---------------------------------------------------------------------------
# GET /carte/etat
# ---------------------------------------------------------------------------


@router.get(
    "/etat",
    summary="État temps réel de tous les tronçons (prêt pour Leaflet)",
    description=(
        "Renvoie pour chaque tronçon actif :\n\n"
        "- la **géométrie** (polyline encodée + extrémités) ;\n"
        "- la **dernière mesure** (durée, vitesse, source, horodatage local) ;\n"
        "- la **classe de congestion DEESP** (`fluide` / `congestionne` / "
        "  `indetermine`) lue depuis les couleurs Google Maps ;\n"
        "- les **pourcentages couleur** (rouge / orange / vert) ;\n"
        "- la **couleur Leaflet** prête à utiliser pour tracer le tronçon.\n\n"
        "Format identique à celui poussé par le WebSocket `/ws/etat`, pour qu'un "
        "frontend puisse alimenter sa carte indifféremment via HTTP polling ou WS."
    ),
    responses={
        200: {
            "description": "Snapshot complet de l'état des tronçons.",
            "content": {"application/json": {"example": {
                "horodatage_utc": "2026-06-18T19:35:00+00:00",
                "fuseau_affichage": "Africa/Abidjan",
                "couleurs": {
                    "fluide": "#16a34a",
                    "congestionne": "#E74C3C",
                    "indetermine": "#95A5A6",
                },
                "criteres": {
                    "source": "Couleurs Google Maps (speedReadingIntervals)",
                    "regle_congestion": "Congestionné si ROUGE OU ORANGE ≥ 50 % du tronçon.",
                    "seuil_orange_long_pct": 50.0,
                },
                "nb_troncons": 1,
                "troncons": [{
                    "id": 3,
                    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                    "distance_km": 8.0,
                    "couleur_etat": "#E74C3C",
                    "classe_congestion": "congestionne",
                    "libelle_classe": "Congestionné",
                    "couleur_google": {
                        "pourcentage_rouge": 12.5,
                        "pourcentage_orange": 41.0,
                        "pourcentage_vert": 46.5,
                    },
                    "motif_congestion": "Tronçon tracé en rouge sur 12.5 % de sa longueur.",
                    "statut": "mesure_disponible",
                    "polyline": "qnj_@rinW...",
                    "derniere_mesure": {
                        "horodatage_local": "2026-06-18T19:19:04+00:00",
                        "duree_trafic_s": 1642,
                        "source": "google",
                    },
                }],
            }}}
        }
    },
)
async def etat_carte(db: Session = Depends(get_db)) -> dict[str, Any]:
    return construire_etat_carte(db)


# ---------------------------------------------------------------------------
# GET /carte/resume-axes — temps actuel + min/moy/max de tous les axes (§ 39)
# ---------------------------------------------------------------------------


class ResumeAxe(BaseModel):
    """Temps de traversée d'un axe, au format de la page Temps de traversée."""
    troncon_id: int
    nom: str
    temps_actuel_s: int | None = Field(
        None, description="Mesure Google du créneau horaire courant (null si aucune)",
    )
    min_s: int | None = Field(None, description="Minimum sur 7 j, même type de jour")
    moyen_s: int | None = Field(None, description="Moyenne sur 7 j, même type de jour")
    max_s: int | None = Field(None, description="Maximum sur 7 j, même type de jour")
    temps_reference_50kmh_s: float


class ResumeAxes(BaseModel):
    """Synthèse de tous les axes actifs pour la page Accueil."""
    instant_local: str
    type_jour: str
    hors_plage_collecte: bool
    plage_collecte: str
    axes: list[ResumeAxe]


@router.get(
    "/resume-axes",
    summary="Temps actuel et min/moyen/max de tous les axes",
    description=(
        "Pour chaque axe actif, en un seul appel :\n\n"
        "- **temps_actuel_s** : mesure Google du créneau courant (fenêtre 65 min), "
        "identique au bloc « Temps actuel » de la page Temps de traversée ; "
        "null hors plage de collecte ou sans mesure récente ;\n"
        "- **min_s / moyen_s / max_s** : 7 derniers jours du même type de jour "
        "(jours ouvrables ou week-ends).\n\n"
        "Un axe découpé en tronçons codifiés est agrégé par somme des tronçons."
    ),
    response_model=ResumeAxes,
)
def resume_axes(db: Session = Depends(get_db)) -> ResumeAxes:
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    maintenant_utc = maintenant_local.astimezone(timezone.utc)
    plage = lire_plage_collecte(db)

    axes = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    resumes: list[ResumeAxe] = []
    for axe in axes:
        actuel = _prediction_google(db, axe, maintenant_utc, fenetre_minutes=65)
        bornes = _prediction_jour_type(db, axe, maintenant_utc)
        resumes.append(ResumeAxe(
            troncon_id=axe.id,
            nom=axe.nom,
            temps_actuel_s=actuel.moyen_s if actuel else None,
            min_s=bornes.min_s if bornes else None,
            moyen_s=bornes.moyen_s if bornes else None,
            max_s=bornes.max_s if bornes else None,
            temps_reference_50kmh_s=round(axe.temps_reference_s(), 1),
        ))

    return ResumeAxes(
        instant_local=maintenant_local.isoformat(),
        type_jour="jour_ouvrable" if maintenant_local.weekday() < 5 else "week_end",
        hors_plage_collecte=not plage.contient(maintenant_local.hour),
        plage_collecte=plage.libelle,
        axes=resumes,
    )


# ---------------------------------------------------------------------------
# WebSocket /ws/etat
# ---------------------------------------------------------------------------


@router_ws.websocket("/ws/etat")
async def websocket_etat(websocket: WebSocket) -> None:
    """Push de l'état carte à chaque nouvelle mesure.

    Protocole :
      1. À l'ouverture, le serveur envoie immédiatement le snapshot courant
         (`{"type": "snapshot", ...}`) pour que le client initialise sa carte.
      2. Ensuite, à chaque cycle de collecte, le scheduler diffuse un message
         `{"type": "maj", "donnees": <état>}` à tous les abonnés.
      3. Le client peut envoyer un texte `"ping"` à tout moment ; le serveur
         répond `"pong"` (utile pour les heartbeats côté frontend).
    """
    await websocket.accept()
    diffuseur = get_diffuseur()
    await diffuseur.enregistrer(websocket)

    try:
        # Snapshot initial (calculé dans un thread — sync SQLAlchemy)
        snapshot_initial = await asyncio.to_thread(construire_etat_carte)
        await websocket.send_text(json.dumps(
            {"type": "snapshot", "donnees": snapshot_initial},
            default=str, ensure_ascii=False,
        ))

        # Boucle d'écoute des messages entrants — sert uniquement aux heartbeats.
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_text("pong")
            # Autres messages : ignorés silencieusement (protocole minimaliste).

    except WebSocketDisconnect:
        logger.info("WS /ws/etat : déconnexion client.")
    except Exception:
        logger.exception("WS /ws/etat : erreur inattendue.")
    finally:
        await diffuseur.desinscrire(websocket)
