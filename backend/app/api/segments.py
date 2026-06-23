"""Routeur /terrain/segments — accumulation GPX libres pour temps de traversée progressif.

Endpoints :
  POST /terrain/segments/import
      Upload d'un segment GPX partiel (entre deux landmarks intermédiaires).
      Stocke en base et retourne les métadonnées du segment.

  GET  /terrain/segments
      Liste des segments (filtres par tronçon, date, session).

  GET  /terrain/segments/resume
      Résumé consolidé : temps moyen par tronçon + historique des sessions.
      Intègre le miroir aller/retour pour les tronçons sans données directes.

  GET  /terrain/segments/resume/{troncon_id}
      Résumé pour un seul tronçon.

Cf. CLAUDE.md § 4.9 — Précision progressive par accumulation GPX.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import SegmentTerrain, Troncon
from app.sources.gpx_parser import parser_gpx_octets
from app.terrain.assemblage import (
    EstimationSession,
    ResumeTempsTraversee,
    assembler_pour_troncon,
    assembler_tous_troncons,
    calculer_distance_trace,
)


logger = logging.getLogger("paa.api.segments")

router = APIRouter(prefix="/terrain/segments", tags=["segments terrain (GPX libres)"])


# ---------------------------------------------------------------------------
# Schémas de réponse
# ---------------------------------------------------------------------------


class EstimationSessionSchema(BaseModel):
    date_session: date
    session_id: str | None
    nb_segments: int
    duree_totale_s: int
    duree_totale_mn: float
    distance_couverte_m: float
    couverture_pct: float
    source: str  # 'segments_directs' ou 'miroir_aller_retour'

    @classmethod
    def from_domain(cls, e: EstimationSession) -> "EstimationSessionSchema":
        return cls(
            date_session=e.date_session,
            session_id=e.session_id,
            nb_segments=e.nb_segments,
            duree_totale_s=e.duree_totale_s,
            duree_totale_mn=round(e.duree_totale_s / 60.0, 2),
            distance_couverte_m=round(e.distance_couverte_m, 1),
            couverture_pct=round(e.couverture_pct, 1),
            source=e.source,
        )


class ResumeTempsSchema(BaseModel):
    troncon_id: int
    troncon_nom: str
    distance_m: int
    nb_sessions: int
    temps_moyen_s: float | None
    temps_moyen_mn: float | None
    temps_min_s: float | None
    temps_max_s: float | None
    couverture_moyenne_pct: float
    confiance: float   # 0.0–1.0 (combinaison nb_sessions et couverture)
    sessions: list[EstimationSessionSchema]

    @classmethod
    def from_domain(cls, r: ResumeTempsTraversee) -> "ResumeTempsSchema":
        return cls(
            troncon_id=r.troncon_id,
            troncon_nom=r.troncon_nom,
            distance_m=r.distance_m,
            nb_sessions=r.nb_sessions,
            temps_moyen_s=round(r.temps_moyen_s, 1) if r.temps_moyen_s else None,
            temps_moyen_mn=round(r.temps_moyen_s / 60.0, 2) if r.temps_moyen_s else None,
            temps_min_s=r.temps_min_s,
            temps_max_s=r.temps_max_s,
            couverture_moyenne_pct=round(r.couverture_moyenne_pct, 1),
            confiance=r.confiance,
            sessions=[EstimationSessionSchema.from_domain(s) for s in r.sessions],
        )


class SegmentImporteSchema(BaseModel):
    id: int
    nom_segment: str
    troncon_id: int | None
    direction: str | None
    lat_debut: float
    lon_debut: float
    lat_fin: float
    lon_fin: float
    duree_s: int
    duree_mn: float
    distance_m: float | None
    horodatage_debut: datetime
    horodatage_fin: datetime
    date_session: date
    session_id: str | None


# ---------------------------------------------------------------------------
# POST /terrain/segments/import
# ---------------------------------------------------------------------------


@router.post(
    "/import",
    response_model=SegmentImporteSchema,
    summary="Importer un segment GPX (sous-portion d'un trajet libre)",
    description=(
        "Accepte un fichier GPX enregistré entre deux landmarks intermédiaires. "
        "Le segment est stocké en base et contribue au calcul progressif des temps "
        "de traversée pour le tronçon parent indiqué."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def importer_segment(
    fichier: Annotated[UploadFile, File(description="Fichier GPX du segment")],
    nom_segment: Annotated[str, Form(description="Libellé du segment (ex. 'CARENA-GMA')")] = "",
    troncon_id: Annotated[int | None, Form(description="ID du tronçon parent (optionnel)")] = None,
    direction: Annotated[str | None, Form(description="'aller' ou 'retour'")] = None,
    session_id: Annotated[str | None, Form(description="Identifiant de session (ex. '20260622_A')")] = None,
    source_reelle: Annotated[bool, Form(description="True = vrai GPX terrain (False = synthétique)")] = True,
    db: Session = Depends(get_db),
) -> SegmentImporteSchema:
    contenu = await fichier.read()
    nom_fichier = fichier.filename or "segment.gpx"

    # --- Parser le GPX ---
    try:
        points = parser_gpx_octets(contenu)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"GPX invalide : {exc}",
        )

    if len(points) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le GPX doit contenir au moins 2 points horodatés.",
        )

    p_debut = points[0]
    p_fin = points[-1]
    duree_s = int((p_fin.horodatage - p_debut.horodatage).total_seconds())
    if duree_s <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Durée nulle ou négative ({duree_s}s) — vérifiez les horodatages.",
        )

    # --- Distance cumulée de la trace ---
    lats = [pt.lat for pt in points]
    lons = [pt.lon for pt in points]
    distance_m = calculer_distance_trace(lats, lons)

    # --- Direction auto-détectée si non fournie ---
    direction_finale = direction
    if direction_finale is None:
        # Si le point de fin est plus au sud (lat plus basse), c'est l'aller
        if p_fin.lat < p_debut.lat - 0.001:
            direction_finale = "aller"
        elif p_fin.lat > p_debut.lat + 0.001:
            direction_finale = "retour"
        # Sinon on laisse NULL (segment est-ouest ou très court)

    # --- Nom auto si non fourni ---
    nom_final = nom_segment.strip() or nom_fichier.replace(".gpx", "")

    # --- Date de session ---
    date_sess = p_debut.horodatage.date()

    # --- Validation troncon_id ---
    if troncon_id is not None:
        troncon = db.get(Troncon, troncon_id)
        if troncon is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tronçon {troncon_id} introuvable.",
            )

    segment = SegmentTerrain(
        nom_segment=nom_final,
        troncon_id=troncon_id,
        direction=direction_finale,
        lat_debut=p_debut.lat,
        lon_debut=p_debut.lon,
        lat_fin=p_fin.lat,
        lon_fin=p_fin.lon,
        duree_s=duree_s,
        distance_m=distance_m,
        horodatage_debut=p_debut.horodatage,
        horodatage_fin=p_fin.horodatage,
        date_session=date_sess,
        session_id=session_id,
        source_reelle=source_reelle,
        contenu_gpx=contenu,
        nom_fichier_gpx=nom_fichier,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)

    logger.info(
        "Segment importé : id=%d nom=%r troncon_id=%s direction=%s duree=%ds",
        segment.id, nom_final, troncon_id, direction_finale, duree_s,
    )

    return SegmentImporteSchema(
        id=segment.id,
        nom_segment=segment.nom_segment,
        troncon_id=segment.troncon_id,
        direction=segment.direction,
        lat_debut=segment.lat_debut,
        lon_debut=segment.lon_debut,
        lat_fin=segment.lat_fin,
        lon_fin=segment.lon_fin,
        duree_s=segment.duree_s,
        duree_mn=round(segment.duree_s / 60.0, 2),
        distance_m=segment.distance_m,
        horodatage_debut=segment.horodatage_debut,
        horodatage_fin=segment.horodatage_fin,
        date_session=segment.date_session,
        session_id=segment.session_id,
    )


# ---------------------------------------------------------------------------
# GET /terrain/segments/{segment_id}/gpx
# ---------------------------------------------------------------------------


@router.get(
    "/{segment_id}/gpx",
    summary="Contenu GPX brut d'un segment",
    description="Retourne le fichier GPX binaire stocké pour ce segment (BYTEA).",
    response_class=__import__("fastapi").responses.Response,
)
async def gpx_segment(
    segment_id: int,
    db: Session = Depends(get_db),
) -> __import__("fastapi").responses.Response:
    from fastapi.responses import Response as FastAPIResponse

    seg = db.get(SegmentTerrain, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail=f"Segment {segment_id} introuvable.")
    if not seg.contenu_gpx:
        raise HTTPException(status_code=410, detail="Contenu GPX non disponible pour ce segment.")
    nom = seg.nom_fichier_gpx or f"segment_{segment_id}.gpx"
    return FastAPIResponse(
        content=bytes(seg.contenu_gpx),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


# ---------------------------------------------------------------------------
# GET /terrain/segments
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="Liste des segments terrain importés",
    description="Historique des segments GPX, filtrables par tronçon et date.",
)
async def lister_segments(
    troncon_id: int | None = Query(None, description="Filtrer par tronçon"),
    date_debut: date | None = Query(None, description="Date de début (YYYY-MM-DD)"),
    date_fin: date | None = Query(None, description="Date de fin (YYYY-MM-DD)"),
    session_id: str | None = Query(None, description="Filtrer par identifiant de session"),
    limite: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    q = select(SegmentTerrain).order_by(SegmentTerrain.horodatage_debut.desc())
    if troncon_id is not None:
        q = q.where(SegmentTerrain.troncon_id == troncon_id)
    if date_debut:
        q = q.where(SegmentTerrain.date_session >= date_debut)
    if date_fin:
        q = q.where(SegmentTerrain.date_session <= date_fin)
    if session_id:
        q = q.where(SegmentTerrain.session_id == session_id)
    q = q.limit(limite)

    segments = db.execute(q).scalars().all()
    return [
        {
            "id": s.id,
            "nom_segment": s.nom_segment,
            "troncon_id": s.troncon_id,
            "direction": s.direction,
            "lat_debut": s.lat_debut,
            "lon_debut": s.lon_debut,
            "lat_fin": s.lat_fin,
            "lon_fin": s.lon_fin,
            "duree_s": s.duree_s,
            "duree_mn": round(s.duree_s / 60.0, 2),
            "distance_m": s.distance_m,
            "date_session": s.date_session.isoformat(),
            "session_id": s.session_id,
            "source_reelle": s.source_reelle,
            "nom_fichier_gpx": s.nom_fichier_gpx,
        }
        for s in segments
    ]


# ---------------------------------------------------------------------------
# GET /terrain/segments/resume
# ---------------------------------------------------------------------------


@router.get(
    "/resume",
    response_model=list[ResumeTempsSchema],
    summary="Résumé temps de traversée par tronçon (tous axes)",
    description=(
        "Agrège les segments terrain pour calculer le temps de traversée estimé "
        "par tronçon officiel. Applique le miroir aller/retour si un sens manque "
        "de données directes. La précision s'améliore à chaque nouvelle session."
    ),
)
async def resume_tous_troncons(
    appliquer_miroir: bool = Query(True, description="Utiliser le sens opposé si pas de données directes"),
    db: Session = Depends(get_db),
) -> list[ResumeTempsSchema]:
    resumes = assembler_tous_troncons(db, appliquer_miroir=appliquer_miroir)
    return [ResumeTempsSchema.from_domain(r) for r in resumes]


# ---------------------------------------------------------------------------
# GET /terrain/segments/resume/{troncon_id}
# ---------------------------------------------------------------------------


@router.get(
    "/resume/{troncon_id}",
    response_model=ResumeTempsSchema,
    summary="Résumé temps de traversée pour un tronçon",
    description=(
        "Détaille toutes les sessions terrain qui contribuent à l'estimation "
        "du temps de traversée pour le tronçon donné."
    ),
)
async def resume_troncon(
    troncon_id: int,
    appliquer_miroir: bool = Query(True, description="Utiliser le sens opposé si pas de données directes"),
    db: Session = Depends(get_db),
) -> ResumeTempsSchema:
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon {troncon_id} introuvable.",
        )
    resume = assembler_pour_troncon(db, troncon_id, appliquer_miroir=appliquer_miroir)
    return ResumeTempsSchema.from_domain(resume)
