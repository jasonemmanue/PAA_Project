"""Diffuseur d'état temps réel — singleton de WebSocket clients.

Modèle simple « publish / subscribe » en mémoire process :
  - les clients ouvrent une connexion sur `/ws/etat` ;
  - le scheduler appelle `get_diffuseur().diffuser(...)` après chaque
    nouveau cycle de collecte ;
  - le diffuseur émet le payload à tous les WebSocket vivants ;
  - les connexions cassées sont retirées silencieusement.

Convient pour un déploiement mono-processus (Uvicorn 1 worker). Pour
plusieurs workers il faudra un canal Redis pub/sub — hors scope hackathon.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket


logger = logging.getLogger("paa.realtime")


class DiffuseurEtat:
    """Stocke les WebSocket abonnés et diffuse les messages JSON."""

    def __init__(self) -> None:
        self._connexions: set[WebSocket] = set()
        self._verrou = asyncio.Lock()

    async def enregistrer(self, websocket: WebSocket) -> None:
        async with self._verrou:
            self._connexions.add(websocket)
        logger.info("WS abonné — %d connexion(s) actives.", len(self._connexions))

    async def desinscrire(self, websocket: WebSocket) -> None:
        async with self._verrou:
            self._connexions.discard(websocket)
        logger.info("WS désabonné — %d connexion(s) actives.", len(self._connexions))

    async def diffuser(self, payload: dict[str, Any]) -> int:
        """Envoie `payload` à tous les abonnés. Retourne le nombre de cibles touchées."""
        message = json.dumps(payload, default=str, ensure_ascii=False)
        async with self._verrou:
            cibles = list(self._connexions)

        cassees: list[WebSocket] = []
        nb_envoyes = 0
        for ws in cibles:
            try:
                await ws.send_text(message)
                nb_envoyes += 1
            except Exception:
                # Connexion fermée côté client ou erreur réseau : on retire.
                cassees.append(ws)

        if cassees:
            async with self._verrou:
                for ws in cassees:
                    self._connexions.discard(ws)
            logger.info("WS — %d connexion(s) cassée(s) retirées.", len(cassees))

        return nb_envoyes

    @property
    def nb_abonnes(self) -> int:
        return len(self._connexions)


# Singleton de processus
_diffuseur = DiffuseurEtat()


def get_diffuseur() -> DiffuseurEtat:
    """Retourne le diffuseur unique du processus."""
    return _diffuseur
