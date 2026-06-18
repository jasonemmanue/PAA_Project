"""Routeur /mesures — accès transversal aux mesures (tous tronçons confondus).

Cet endpoint complète `GET /troncons/{id}/mesures` lorsqu'on veut filtrer
par source, plage de dates ou inspecter les trous (`duree_trafic_s = NULL`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Mesure, SourceMesure


router = APIRouter(prefix="/mesures", tags=["mesures"])


@router.get(
    "",
    summary="Liste les mesures (filtrage transversal multi-tronçons)",
    description=(
        "Renvoie les mesures les plus récentes, filtrables par tronçon, source, "
        "plage de dates locales (Africa/Abidjan) et statut (succès / trou). "
        "Pour télécharger l'historique complet préférer `GET /export/mesures`."
    ),
    responses={
        200: {
            "description": "Liste paginée des mesures.",
            "content": {"application/json": {"example": {
                "nb_resultats": 1,
                "mesures": [{
                    "id": 1,
                    "troncon_id": 3,
                    "horodatage_local": "2026-06-18T19:19:04+00:00",
                    "duree_trafic_s": 1642,
                    "duree_sans_trafic_s": 580,
                    "vitesse_moyenne_kmh": 21.33,
                    "source": "google",
                    "aberrante": False,
                }],
            }}},
        }
    },
)
async def lister_mesures(
    troncon_id: int | None = Query(None, description="Filtrer sur un tronçon précis."),
    source: SourceMesure | None = Query(
        None,
        description="Filtrer sur une source (`google`, `tomtom`, `terrain`, `interne`).",
    ),
    debut: date | None = Query(None, description="Date locale de début (YYYY-MM-DD)."),
    fin: date | None = Query(None, description="Date locale de fin (YYYY-MM-DD)."),
    inclure_trous: bool = Query(
        True,
        description="Inclure les lignes sans valeur (`duree_trafic_s = NULL`).",
    ),
    limite: int = Query(200, ge=1, le=5000, description="Nombre maximum de lignes renvoyées."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau_local = ZoneInfo(get_settings().tz)
    requete = select(Mesure)

    if troncon_id is not None:
        requete = requete.where(Mesure.troncon_id == troncon_id)
    if source is not None:
        requete = requete.where(Mesure.source == source)
    if debut is not None:
        debut_utc = datetime.combine(debut, time.min, tzinfo=fuseau_local).astimezone(timezone.utc)
        requete = requete.where(Mesure.horodatage >= debut_utc)
    if fin is not None:
        fin_utc = datetime.combine(fin, time.max, tzinfo=fuseau_local).astimezone(timezone.utc)
        requete = requete.where(Mesure.horodatage <= fin_utc)
    if not inclure_trous:
        requete = requete.where(Mesure.duree_trafic_s.is_not(None))

    mesures = list(
        db.execute(requete.order_by(Mesure.horodatage.desc()).limit(limite)).scalars()
    )

    return {
        "nb_resultats": len(mesures),
        "limite_appliquee": limite,
        "mesures": [
            {
                "id": m.id,
                "troncon_id": m.troncon_id,
                "horodatage_utc": m.horodatage.isoformat(),
                "horodatage_local": m.horodatage.astimezone(fuseau_local).isoformat(),
                "duree_trafic_s": m.duree_trafic_s,
                "duree_sans_trafic_s": m.duree_sans_trafic_s,
                "vitesse_moyenne_kmh": m.vitesse_moyenne_kmh,
                "source": m.source.value,
                "aberrante": m.aberrante,
            }
            for m in mesures
        ],
    }
