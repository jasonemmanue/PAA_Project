"""Routeur /carte — état temps réel des tronçons + WebSocket de diffusion.

  - GET       /carte/etat → snapshot synchrone (rafraîchissement périodique).
  - WebSocket /ws/etat    → push à chaque nouvelle mesure (rafraîchissement live).

Le WebSocket n'est pas sous le préfixe `/carte` pour respecter la convention
de ton brief (`/ws/etat`) ; il est exposé dans le même fichier pour cohérence.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.etat.carte import construire_etat_carte
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
        "- le **TTI**, la **classe de congestion** et la **couleur** Leaflet ;\n"
        "- le **temps de référence** retenu et sa source dans la cascade.\n\n"
        "Format identique à celui poussé par le WebSocket `/ws/etat`, pour qu'un "
        "frontend puisse alimenter sa carte indifféremment via HTTP polling ou WS."
    ),
    responses={
        200: {
            "description": "Snapshot complet de l'état des tronçons.",
            "content": {"application/json": {"example": {
                "horodatage_utc": "2026-06-18T19:35:00+00:00",
                "fuseau_affichage": "Africa/Abidjan",
                "seuils": {"tti_dense": 1.3, "tti_congestionne": 2.0},
                "couleurs": {
                    "fluide": "#2ecc71", "dense": "#f39c12",
                    "congestionne": "#e74c3c", "indetermine": "#95a5a6",
                },
                "nb_troncons": 1,
                "troncons": [{
                    "id": 3,
                    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                    "distance_km": 8.0,
                    "couleur_etat": "#e74c3c",
                    "tti": 2.831,
                    "classe_congestion": "congestionne",
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
