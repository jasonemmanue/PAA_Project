"""Routeur `/heure-optimale` — P6.3.

Endpoint :
  - GET /heure-optimale?depart=...&date=...&troncon_id=... → quand partir ?
"""

from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.predicteur.heure_optimale import calculer_heure_optimale
from app.sources.coordonnees import PointGPS
from app.sources.nominatim import geocoder, parser_latlon


router = APIRouter(prefix="/heure-optimale", tags=["heure optimale"])


@router.get(
    "",
    summary="Calcule l'heure de départ optimale vers un tronçon du port",
    description=(
        "Pour un point de départ donné (nom de lieu OU lat,lon) et une date "
        "cible, propose une heure de départ optimisée prenant en compte :\n\n"
        "1. La durée d'approche libre [depart → origine_du_tronçon] estimée via "
        "OSRM (ou Haversine ÷ 30 km/h en repli)\n"
        "2. Le profil horaire prédit pour l'instant **d'arrivée** au tronçon "
        "(propagation temporelle)\n\n"
        "Renvoie 24 créneaux (toutes les 30 min entre 7h et 19h), identifie "
        "l'optimal et le pire, et formule une recommandation textuelle."
    ),
)
async def get_heure_optimale(
    depart: str = Query(
        ..., description=(
            "Nom de lieu géocodable (ex. 'Plateau, Abidjan') OU coordonnées "
            "directes au format 'lat,lon' (ex. '5.328,-4.028')"
        ),
    ),
    date_cible: date_type | None = Query(
        None, alias="date",
        description="Jour visé (YYYY-MM-DD), défaut aujourd'hui",
    ),
    troncon_id: int | None = Query(
        None,
        description=(
            "Forcer un axe d'arrivée. Si omis, on prend le tronçon dont "
            "l'origine est la plus proche du point de départ."
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau = ZoneInfo(get_settings().tz)
    if date_cible is None:
        date_cible = datetime.now(tz=fuseau).date()

    # 1. Résoudre le point de départ
    point: PointGPS | None = parser_latlon(depart)
    libelle = depart
    if point is None:
        # Géocoder via Nominatim
        resultat = await geocoder(depart)
        if resultat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Impossible de géocoder '{depart}'. Essayez un nom de lieu "
                    "plus précis ou des coordonnées 'lat,lon'."
                ),
            )
        point = resultat.point
        libelle = resultat.libelle

    # 2. Calcul
    try:
        calcul = await calculer_heure_optimale(
            db, point, libelle, date_cible, troncon_id=troncon_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    # 3. Sérialisation
    return {
        "depart": {
            "adresse": calcul.depart_libelle,
            "lat": calcul.depart.lat,
            "lon": calcul.depart.lon,
        },
        "troncon_utilise": {
            "id": calcul.troncon_id,
            "nom": calcul.troncon_nom,
        },
        "date": calcul.date_cible.isoformat(),
        "type_jour": calcul.type_jour,
        "approche_libre_mn": calcul.approche_libre_mn,
        "methode_approche": calcul.methode_approche,
        "creneaux": [
            {
                "depart": c.depart_local,
                "arrivee_troncon": c.arrivee_troncon_local,
                "approche_mn": c.approche_mn,
                "traversee_mn": c.traversee_mn,
                "total_mn": c.total_mn,
            }
            for c in calcul.creneaux
        ],
        "creneau_optimal": {
            "depart": calcul.creneau_optimal.depart_local,
            "total_mn": calcul.creneau_optimal.total_mn,
            "gain_vs_pire_mn": calcul.gain_vs_pire_mn,
        },
        "creneau_pire": {
            "depart": calcul.creneau_pire.depart_local,
            "total_mn": calcul.creneau_pire.total_mn,
        },
        "recommandation": calcul.recommandation,
    }
