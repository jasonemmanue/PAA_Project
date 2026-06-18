"""Routeur /troncons — référentiel des axes et leur dernier état.

Endpoints :
  - GET  /troncons                          → liste avec dernier état et classe
  - GET  /troncons/{id}                     → détail d'un tronçon
  - GET  /troncons/{id}/indicateurs         → snapshot TTI/PTI/BTI/P95 sur N jours
  - GET  /troncons/{id}/mesures             → mesures brutes filtrées

La lecture des profils horaires est exposée séparément sous /profils, et
la série temporelle sous /indicateurs (séparation routeurs métier).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyse.indicateurs import (
    SeuilsCongestion,
    calcul_indicateurs,
    indicateurs_par_jour,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.etat.carte import construire_etat_carte
from app.models.models import Mesure, Troncon


router = APIRouter(prefix="/troncons", tags=["tronçons"])


# ---------------------------------------------------------------------------
# Schémas Pydantic (réponses documentées dans Swagger)
# ---------------------------------------------------------------------------


class TronconResume(BaseModel):
    """Résumé d'un tronçon pour la vue liste."""
    id: int
    nom: str
    distance_m: int
    distance_km: float
    vitesse_ref_kmh: float
    couleur_base: str = Field(description="Couleur officielle du tronçon (réf. cartographique).")
    actif: bool


class TronconDetail(TronconResume):
    """Détail complet d'un tronçon."""
    lat_origine: float | None
    lon_origine: float | None
    lat_destination: float | None
    lon_destination: float | None
    polyline: str | None = Field(description="Tracé encodé Google polyline (precision 5).")
    temps_reference_s: float = Field(description="Temps théorique à la vitesse de référence.")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 3,
            "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
            "distance_m": 8000,
            "distance_km": 8.0,
            "vitesse_ref_kmh": 50.0,
            "couleur_base": "#1976D2",
            "actif": True,
            "lat_origine": 5.3018,
            "lon_origine": -4.0106,
            "lat_destination": 5.2645,
            "lon_destination": -3.9725,
            "polyline": "qnj_@rinWJ...",
            "temps_reference_s": 576.0,
        }
    })


class MesurePublique(BaseModel):
    """Une mesure exposée par l'API (mêmes champs que la table sans le flag interne)."""
    id: int
    troncon_id: int
    horodatage_utc: datetime
    horodatage_local: datetime
    duree_trafic_s: int | None
    duree_sans_trafic_s: int | None
    vitesse_moyenne_kmh: float | None
    source: str
    aberrante: bool


# ---------------------------------------------------------------------------
# GET /troncons
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="Liste les tronçons avec leur dernier état et classe de congestion",
    description=(
        "Renvoie tous les tronçons (par défaut actifs uniquement) enrichis de :\n\n"
        "- la **dernière mesure** disponible (horodatage local, durée, source),\n"
        "- le **TTI** calculé contre le temps de référence (cascade Google → 50 km/h),\n"
        "- la **classe de congestion** (`fluide`, `dense`, `congestionne`, `indetermine`),\n"
        "- la **couleur métier** prête à utiliser dans Leaflet.\n\n"
        "Format identique à `/carte/etat` mais limité au tableau (sans seuils)."
    ),
    responses={
        200: {
            "description": "Liste enrichie des tronçons.",
            "content": {"application/json": {"example": {
                "nb_troncons": 1,
                "troncons": [{
                    "id": 3,
                    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                    "distance_km": 8.0,
                    "tti": 2.831,
                    "classe_congestion": "congestionne",
                    "couleur_etat": "#e74c3c",
                    "statut": "mesure_disponible",
                    "derniere_mesure": {
                        "horodatage_local": "2026-06-18T19:19:04+00:00",
                        "duree_trafic_s": 1642,
                        "vitesse_moyenne_kmh": 21.33,
                        "source": "google",
                    },
                }]
            }}}
        }
    },
)
async def lister_troncons(
    inclure_inactifs: bool = Query(
        False,
        description="Si vrai, inclut aussi les tronçons archivés (`actif = false`).",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # On réutilise la logique de la carte — un seul code, deux canaux (HTTP + WS).
    etat = construire_etat_carte(db)
    if inclure_inactifs:
        # Si on veut les inactifs, on enrichit manuellement (la carte ne renvoie que actifs)
        inactifs = list(
            db.execute(
                select(Troncon).where(Troncon.actif.is_(False)).order_by(Troncon.id)
            ).scalars()
        )
        etat["troncons"].extend([{
            "id": t.id, "nom": t.nom, "actif": False,
            "distance_m": t.distance_m, "distance_km": round(t.distance_m / 1000.0, 2),
            "statut": "archive",
        } for t in inactifs])
        etat["nb_troncons"] = len(etat["troncons"])
    return etat


# ---------------------------------------------------------------------------
# GET /troncons/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{troncon_id}",
    summary="Détail d'un tronçon (référentiel statique + temps de référence)",
    response_model=TronconDetail,
)
async def detail_troncon(
    troncon_id: int,
    db: Session = Depends(get_db),
) -> TronconDetail:
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )
    return TronconDetail(
        id=troncon.id,
        nom=troncon.nom,
        distance_m=troncon.distance_m,
        distance_km=round(troncon.distance_m / 1000.0, 2),
        vitesse_ref_kmh=troncon.vitesse_ref_kmh,
        couleur_base=troncon.couleur,
        actif=troncon.actif,
        lat_origine=troncon.lat_origine,
        lon_origine=troncon.lon_origine,
        lat_destination=troncon.lat_destination,
        lon_destination=troncon.lon_destination,
        polyline=troncon.polyline,
        temps_reference_s=round(troncon.temps_reference_s(), 1),
    )


# ---------------------------------------------------------------------------
# GET /troncons/{id}/indicateurs
# ---------------------------------------------------------------------------


def _parse_periode(periode: str) -> int:
    """Convertit '7j' / '30j' / '90j' en nombre de jours entier."""
    if not periode.endswith("j"):
        raise ValueError("La période doit être au format '7j', '30j', '90j', etc.")
    return int(periode[:-1])


@router.get(
    "/{troncon_id}/indicateurs",
    summary="Snapshot des indicateurs FHWA sur une période (TTI/PTI/BTI/P95)",
    description=(
        "Calcule sur la fenêtre demandée :\n\n"
        "- **TTI** (Travel Time Index) = moyenne / temps_référence\n"
        "- **PTI** (Planning Time Index) = P95 / temps_référence\n"
        "- **BTI** (Buffer Time Index) = (P95 − moyenne) / moyenne\n"
        "- **Fréquence de dépassement** d'un seuil (configurable ou auto = 1,5 × T_ref)\n"
        "- **Classe de congestion** (`fluide`, `dense`, `congestionne`)\n\n"
        "Inclut également la décomposition jour par jour pour tracer une courbe."
    ),
    responses={
        200: {"description": "Snapshot + détail jour par jour."},
        404: {"description": "Tronçon introuvable."},
        400: {"description": "Période mal formatée (attendu : 7j, 30j, …)."},
    },
)
async def indicateurs_troncon(
    troncon_id: int,
    periode: str = Query("7j", description="Fenêtre d'analyse, ex. `7j`, `30j`, `90j`."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        jours = _parse_periode(periode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc

    if jours < 1 or jours > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La période doit être comprise entre 1 et 90 jours.",
        )

    settings = get_settings()
    fuseau_local = ZoneInfo(settings.tz)
    fin_local = datetime.now(tz=fuseau_local)
    debut_local = fin_local - timedelta(days=jours)

    try:
        snapshot = calcul_indicateurs(
            db, troncon_id,
            debut_local.astimezone(timezone.utc),
            fin_local.astimezone(timezone.utc),
        )
        detail = indicateurs_par_jour(db, troncon_id, nb_jours=jours)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return {
        "periode": periode,
        "fenetre_jours": jours,
        "fuseau": settings.tz,
        "snapshot": asdict(snapshot),
        "evolution_par_jour": detail["jours"],
    }


# ---------------------------------------------------------------------------
# GET /troncons/{id}/mesures
# ---------------------------------------------------------------------------


@router.get(
    "/{troncon_id}/mesures",
    summary="Mesures brutes d'un tronçon, filtrées par plage de dates locales",
    response_model=list[MesurePublique],
)
async def mesures_du_troncon(
    troncon_id: int,
    debut: date | None = Query(None, description="Date locale de début (YYYY-MM-DD)."),
    fin: date | None = Query(None, description="Date locale de fin (YYYY-MM-DD)."),
    limite: int = Query(500, ge=1, le=5000, description="Nombre maximum de lignes renvoyées."),
    inclure_aberrantes: bool = Query(True, description="Inclure les mesures marquées aberrantes."),
    db: Session = Depends(get_db),
) -> list[MesurePublique]:
    if db.get(Troncon, troncon_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )

    fuseau_local = ZoneInfo(get_settings().tz)
    requete = select(Mesure).where(Mesure.troncon_id == troncon_id)

    if debut is not None:
        debut_utc = datetime.combine(debut, time.min, tzinfo=fuseau_local).astimezone(timezone.utc)
        requete = requete.where(Mesure.horodatage >= debut_utc)
    if fin is not None:
        fin_utc = datetime.combine(fin, time.max, tzinfo=fuseau_local).astimezone(timezone.utc)
        requete = requete.where(Mesure.horodatage <= fin_utc)
    if not inclure_aberrantes:
        requete = requete.where(Mesure.aberrante.is_(False))

    mesures = list(
        db.execute(requete.order_by(Mesure.horodatage.desc()).limit(limite)).scalars()
    )

    return [
        MesurePublique(
            id=m.id,
            troncon_id=m.troncon_id,
            horodatage_utc=m.horodatage,
            horodatage_local=m.horodatage.astimezone(fuseau_local),
            duree_trafic_s=m.duree_trafic_s,
            duree_sans_trafic_s=m.duree_sans_trafic_s,
            vitesse_moyenne_kmh=m.vitesse_moyenne_kmh,
            source=m.source.value,
            aberrante=m.aberrante,
        )
        for m in mesures
    ]
