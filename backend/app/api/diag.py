"""Endpoints de diagnostic des sources de mesure actives.

Ces endpoints permettent de **valider en live** que chaque source fonctionne
sur un tronçon réel. Ils ne stockent rien en base — ils servent uniquement à
faire un test ponctuel et à diagnostiquer la qualité de chaque source.

Tous renvoient un payload normalisé :
  - source       : nom de la source ('google' | 'osrm')
  - troncon_id   : id du tronçon testé
  - troncon_nom  : libellé humain
  - statut       : 'ok' | 'indisponible' | 'erreur'
  - donnees      : sous-objet spécifique à la source

`/diag/osrm` ajoute par ailleurs le temps de référence T_ref calculé à
50 km/h (cf. CLAUDE.md § 1.3 « comparaison systématique à un temps de référence »).

⚠️  TomTom a été retiré du projet après tests : aucune couverture cartographique
    à Abidjan (cf. CLAUDE.md § 2.5).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Troncon
from app.sources import google_routes
from app.sources.coordonnees import PointGPS


router = APIRouter(prefix="/diag", tags=["diagnostic"])


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _charger_troncon(troncon_id: int, db: Session) -> Troncon:
    """Charge un tronçon ou lève 404."""
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )
    return troncon


def _points_du_troncon(troncon: Troncon) -> tuple[PointGPS, PointGPS]:
    """Retourne (origine, destination) ou lève 409 si non résolu.

    Le tronçon doit avoir été complété au préalable par `complete_troncons.py`.
    """
    if (
        troncon.lat_origine is None
        or troncon.lon_origine is None
        or troncon.lat_destination is None
        or troncon.lon_destination is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tronçon id={troncon.id} non résolu (coordonnées NULL). "
                "Lancer d'abord : python -m app.complete_troncons"
            ),
        )
    return (
        PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine),
        PointGPS(lat=troncon.lat_destination, lon=troncon.lon_destination),
    )


def _temps_reference_s(distance_m: int, vitesse_ref_kmh: float) -> float:
    """T_ref = distance_m / (vitesse_ref_kmh / 3.6)  — résultat en secondes."""
    if vitesse_ref_kmh <= 0:
        raise ValueError("vitesse_ref_kmh doit être > 0")
    return distance_m / (vitesse_ref_kmh / 3.6)


# ---------------------------------------------------------------------------
# /diag/google/{troncon_id}
# ---------------------------------------------------------------------------


@router.get(
    "/google/{troncon_id}",
    summary="Diagnostic Google Routes (durée trafic + durée fluide + distance)",
)
async def diag_google(troncon_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    troncon = _charger_troncon(troncon_id, db)
    origine, destination = _points_du_troncon(troncon)

    if not get_settings().google_routes_api_key:
        return {
            "source": "google",
            "troncon_id": troncon.id,
            "troncon_nom": troncon.nom,
            "statut": "indisponible",
            "message": "GOOGLE_ROUTES_API_KEY non configurée dans backend/.env.",
        }

    try:
        reponse = await google_routes.calcul_itineraire(origine, destination)
    except Exception as exc:
        return {
            "source": "google",
            "troncon_id": troncon.id,
            "troncon_nom": troncon.nom,
            "statut": "erreur",
            "message": str(exc),
        }

    # Indicateur d'embouteillage : ratio (durée avec trafic) / (durée fluide)
    ratio_trafic = (
        reponse.duree_trafic_s / reponse.duree_sans_trafic_s
        if reponse.duree_sans_trafic_s > 0 else None
    )

    return {
        "source": "google",
        "troncon_id": troncon.id,
        "troncon_nom": troncon.nom,
        "statut": "ok",
        "donnees": {
            "duree_trafic_s": reponse.duree_trafic_s,
            "duree_trafic_min_s": _format_minutes_secondes(reponse.duree_trafic_s),
            "duree_sans_trafic_s": reponse.duree_sans_trafic_s,
            "duree_sans_trafic_min_s": _format_minutes_secondes(reponse.duree_sans_trafic_s),
            "distance_m": reponse.distance_m,
            "ratio_trafic_sur_fluide": round(ratio_trafic, 3) if ratio_trafic else None,
            "polyline_taille_caracteres": len(reponse.polyline_encodee),
        },
    }


# ---------------------------------------------------------------------------
# Petite aide d'affichage
# ---------------------------------------------------------------------------


def _format_minutes_secondes(secondes: float) -> str:
    """Format humain '12 min 34 s' (utile pour la lecture des réponses /diag)."""
    if secondes is None:
        return "n/a"
    minutes_entieres = int(secondes) // 60
    secondes_restantes = int(round(secondes - minutes_entieres * 60))
    return f"{minutes_entieres} min {secondes_restantes:02d} s"
