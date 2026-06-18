"""Construction de l'état temps réel des tronçons pour la carte.

Cette logique est appelée :
  - par l'endpoint HTTP `GET /carte/etat` (réponse synchrone immédiate),
  - par le WebSocket `/ws/etat` à chaque nouvelle mesure (push).

Le résultat est un dictionnaire prêt à sérialiser, structuré pour qu'un
frontend Leaflet puisse l'afficher sans transformation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyse.indicateurs import SeuilsCongestion, classifier_congestion
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import Mesure, Troncon


# Code couleur métier utilisé par la carte (Leaflet — `color` des Polyline).
# On distingue 4 états : fluide / dense / congestionné + indéterminé (gris).
COULEURS_CONGESTION: dict[str, str] = {
    "fluide":        "#2ecc71",
    "dense":         "#f39c12",
    "congestionne":  "#e74c3c",
    "indetermine":   "#95a5a6",
}


def _temps_reference_s(troncon: Troncon, derniere_mesure: Mesure | None) -> tuple[float, str]:
    """Cascade T_ref pour l'état carte (snapshot ponctuel).

    Priorité :
      1. `duree_sans_trafic_s` de la dernière mesure Google si présente.
      2. ~~TomTom~~ (retiré du projet — CLAUDE.md § 2.5).
      3. Repli déterministe 50 km/h sur la distance officielle.
    """
    if derniere_mesure is not None and derniere_mesure.duree_sans_trafic_s is not None:
        return float(derniere_mesure.duree_sans_trafic_s), "google_freeflow"
    return troncon.distance_m / (troncon.vitesse_ref_kmh / 3.6), "vitesse_ref_50kmh"


def construire_etat_carte(session: Session | None = None) -> dict[str, Any]:
    """Construit le snapshot complet : un objet par tronçon actif.

    Retourne :
      {
        "horodatage_utc": "...",
        "fuseau_affichage": "Africa/Abidjan",
        "seuils": {...},
        "troncons": [ { ... } x N ]
      }
    """
    settings = get_settings()
    seuils = SeuilsCongestion.depuis_settings(settings)
    fuseau_local = ZoneInfo(settings.tz)
    instant_utc = datetime.now(tz=timezone.utc)

    fermer_apres = session is None
    if fermer_apres:
        session = SessionLocal()

    try:
        # 1. Tronçons actifs (ordre stable)
        troncons: list[Troncon] = list(
            session.execute(
                select(Troncon)
                .where(Troncon.actif.is_(True))
                .order_by(Troncon.id)
            ).scalars()
        )

        # 2. Dernière mesure par tronçon (1 requête grâce à DISTINCT ON Postgres).
        #    SQLAlchemy traduit `distinct(col)` en PostgreSQL `SELECT DISTINCT ON (col)`.
        dernieres = list(
            session.execute(
                select(Mesure)
                .where(Mesure.troncon_id.in_([t.id for t in troncons]))
                .distinct(Mesure.troncon_id)
                .order_by(Mesure.troncon_id, Mesure.horodatage.desc())
            ).scalars()
        )
        dernieres_par_troncon: dict[int, Mesure] = {m.troncon_id: m for m in dernieres}

        # 3. Construction des cartes de tronçons
        etat_troncons: list[dict[str, Any]] = []
        for troncon in troncons:
            derniere = dernieres_par_troncon.get(troncon.id)
            t_ref_s, source_ref = _temps_reference_s(troncon, derniere)

            duree_mesuree: int | None = None
            tti: float | None = None
            horodatage_iso: str | None = None
            horodatage_local_iso: str | None = None
            vitesse_kmh: float | None = None
            source_mesure: str | None = None
            statut: str = "sans_mesure"

            if derniere is not None:
                horodatage_iso = derniere.horodatage.isoformat()
                horodatage_local_iso = derniere.horodatage.astimezone(
                    fuseau_local
                ).isoformat()
                if derniere.duree_trafic_s is not None:
                    duree_mesuree = derniere.duree_trafic_s
                    vitesse_kmh = derniere.vitesse_moyenne_kmh
                    source_mesure = derniere.source.value
                    if t_ref_s > 0:
                        tti = round(duree_mesuree / t_ref_s, 3)
                    statut = "mesure_disponible"
                else:
                    # Ligne trou de mesure : on a tenté mais sans valeur exploitable
                    statut = "trou_de_mesure"
                    source_mesure = derniere.source.value

            classe = classifier_congestion(tti, seuils)
            couleur_etat = COULEURS_CONGESTION[classe]

            etat_troncons.append({
                "id": troncon.id,
                "nom": troncon.nom,
                "distance_m": troncon.distance_m,
                "distance_km": round(troncon.distance_m / 1000.0, 2),
                "vitesse_ref_kmh": troncon.vitesse_ref_kmh,
                "couleur_base": troncon.couleur,
                "couleur_etat": couleur_etat,
                "polyline": troncon.polyline,
                "geometrie": {
                    "lat_origine": troncon.lat_origine,
                    "lon_origine": troncon.lon_origine,
                    "lat_destination": troncon.lat_destination,
                    "lon_destination": troncon.lon_destination,
                },
                "temps_reference_s": round(t_ref_s, 1),
                "source_temps_reference": source_ref,
                "statut": statut,
                "derniere_mesure": (
                    {
                        "horodatage_utc": horodatage_iso,
                        "horodatage_local": horodatage_local_iso,
                        "duree_trafic_s": duree_mesuree,
                        "vitesse_moyenne_kmh": vitesse_kmh,
                        "source": source_mesure,
                    }
                    if derniere is not None
                    else None
                ),
                "tti": tti,
                "classe_congestion": classe,
            })

        return {
            "horodatage_utc": instant_utc.isoformat(),
            "fuseau_affichage": settings.tz,
            "seuils": {
                "tti_dense": seuils.dense,
                "tti_congestionne": seuils.congestionne,
            },
            "couleurs": COULEURS_CONGESTION,
            "nb_troncons": len(etat_troncons),
            "troncons": etat_troncons,
        }
    finally:
        if fermer_apres:
            session.close()
