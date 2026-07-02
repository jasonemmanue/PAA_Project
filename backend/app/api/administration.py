"""Routeur `/administration` — CRUD tronçons + sous-tronçons codifiés (P6.4).

Endpoints :
  - POST   /administration/troncons                       → créer un axe principal
  - PATCH  /administration/troncons/{id}                  → modifier nom/couleur/vitesse
  - DELETE /administration/troncons/{id}                  → suppression LOGIQUE
  - GET    /administration/troncons/{id}/sous-troncons    → liste ordonnée
  - POST   /administration/troncons/{id}/sous-troncons    → créer un sous-tronçon T1A...
  - PATCH  /administration/sous-troncons/{id}             → modifier code/nom
  - DELETE /administration/sous-troncons/{id}             → suppression LOGIQUE

Cohérent avec la convention DEESP (CLAUDE.md § 4.5 et §6.4 du carnet de
prompts). La géométrie est calculée à la création — polyline simple
(origine → waypoints → destination) encodée en Google Polyline, distance
en mètres via Haversine cumulée. Sans dépendance OSRM.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collecte.scheduler import (
    QUOTA_GOOGLE_JOUR_MAX,
    estimer_requetes_par_jour,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import SousTroncon, Troncon
from app.sources.polyline import (
    distance_cumulee_m,
    distance_haversine_m,
    encoder_polyline,
)


router = APIRouter(prefix="/administration", tags=["administration"])


# ===========================================================================
# Pydantic schemas
# ===========================================================================


class TronconCreer(BaseModel):
    """Payload pour POST /administration/troncons."""
    nom: str = Field(..., min_length=3, max_length=200,
                     description="Libellé canonique 'Origine → Destination'")
    lat_origine: float
    lon_origine: float
    lat_destination: float
    lon_destination: float
    waypoints: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Points intermédiaires optionnels (lat, lon)",
    )
    distance_m: int | None = Field(
        None,
        description="Distance officielle ; si omise, calcul Haversine cumulée",
    )
    vitesse_ref_kmh: float = 50.0
    couleur: str = "#1976D2"
    est_axe: bool = Field(
        default=True,
        description=(
            "Si True (défaut), marqué comme axe officiel DEESP. Si False, "
            "tronçon supplémentaire ajouté en complément des 6 axes initiaux."
        ),
    )


class TronconMaj(BaseModel):
    """Payload pour PATCH /administration/troncons/{id} — tous les champs sont optionnels."""
    nom: str | None = Field(None, min_length=3, max_length=200)
    vitesse_ref_kmh: float | None = None
    couleur: str | None = None


class SousTronconCreer(BaseModel):
    """Payload pour POST /administration/troncons/{id}/sous-troncons."""
    code: str = Field(..., min_length=2, max_length=10,
                      description="Code DEESP — ex. 'T1A', 'T2B'")
    nom_court: str = Field(..., min_length=3, max_length=120)
    lat_debut: float
    lon_debut: float
    lat_fin: float
    lon_fin: float
    ordre: int | None = Field(
        None,
        description="Si omis, place à la fin (max(ordre) + 1)",
    )


class SousTronconMaj(BaseModel):
    """Payload pour PATCH /administration/sous-troncons/{id}."""
    code: str | None = Field(None, min_length=2, max_length=10)
    nom_court: str | None = Field(None, min_length=3, max_length=120)


# ===========================================================================
# CRUD tronçons principaux
# ===========================================================================


@router.post(
    "/troncons",
    summary="Créer un nouvel axe principal",
    description=(
        "Crée un tronçon avec ses extrémités (et waypoints optionnels). "
        "La polyline est encodée à partir des points fournis (Google Polyline "
        "precision 5). La distance est calculée par Haversine cumulée sauf "
        "si `distance_m` est fournie explicitement. Sans dépendance OSRM."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def creer_troncon(
    payload: TronconCreer,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Refuse les doublons exacts de nom (parmi les actifs)
    existant = db.execute(
        select(Troncon).where(Troncon.nom == payload.nom, Troncon.actif.is_(True))
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un tronçon actif portant le nom {payload.nom!r} existe déjà (id={existant.id}).",
        )

    points: list[tuple[float, float]] = [
        (payload.lat_origine, payload.lon_origine),
        *payload.waypoints,
        (payload.lat_destination, payload.lon_destination),
    ]

    # OSRM si disponible → polyline qui suit les vraies routes + distance réelle
    polyline: str
    distance: int
    settings = get_settings()
    if settings.osrm_base_url and not payload.waypoints:
        # OSRM ne prend que 2 points ; en présence de waypoints, on les respecte
        # tels quels (Google Polyline). Sinon on délègue à OSRM.
        try:
            from app.sources import osrm
            from app.sources.coordonnees import PointGPS
            rep = await osrm.route(
                PointGPS(lat=payload.lat_origine, lon=payload.lon_origine),
                PointGPS(lat=payload.lat_destination, lon=payload.lon_destination),
            )
            polyline = rep.polyline_encodee
            distance = payload.distance_m if payload.distance_m is not None else rep.distance_m
        except Exception:
            polyline = encoder_polyline(points)
            distance = payload.distance_m if payload.distance_m is not None else distance_cumulee_m(points)
    else:
        polyline = encoder_polyline(points)
        distance = payload.distance_m if payload.distance_m is not None else distance_cumulee_m(points)

    if distance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La distance calculée est nulle — vérifier les coordonnées.",
        )

    troncon = Troncon(
        nom=payload.nom,
        lat_origine=payload.lat_origine,
        lon_origine=payload.lon_origine,
        lat_destination=payload.lat_destination,
        lon_destination=payload.lon_destination,
        polyline=polyline,
        distance_m=distance,
        vitesse_ref_kmh=payload.vitesse_ref_kmh,
        couleur=payload.couleur,
        actif=True,
        est_axe=payload.est_axe,
    )
    db.add(troncon)
    db.commit()
    db.refresh(troncon)

    # Le tronçon est inclus AU PROCHAIN CYCLE sans redémarrage du scheduler,
    # car `cycle_de_collecte()` recharge la liste des tronçons actifs à chaque
    # tick. On expose dans la réponse une estimation du quota Google et un
    # avertissement éventuel pour aider l'opérateur à dimensionner la collecte.
    payload_reponse = _serializer_troncon(troncon)
    payload_reponse["adoption_collecte"] = _resume_adoption_collecte(db)
    return payload_reponse


@router.patch(
    "/troncons/{troncon_id}",
    summary="Mettre à jour un tronçon (nom, couleur, vitesse de référence)",
)
def maj_troncon(
    troncon_id: int,
    payload: TronconMaj,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    troncon = db.get(Troncon, troncon_id)
    if troncon is None or not troncon.actif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable ou archivé.",
        )
    if payload.nom is not None:
        troncon.nom = payload.nom
    if payload.vitesse_ref_kmh is not None:
        troncon.vitesse_ref_kmh = payload.vitesse_ref_kmh
    if payload.couleur is not None:
        troncon.couleur = payload.couleur
    db.commit()
    db.refresh(troncon)
    return _serializer_troncon(troncon)


@router.delete(
    "/troncons/{troncon_id}",
    summary="Suppression LOGIQUE d'un tronçon (actif=false)",
    description=(
        "Conserve l'historique. Le tronçon disparaît de la collecte au "
        "cycle suivant mais ses mesures et sous-tronçons restent en base."
    ),
)
def supprimer_troncon(
    troncon_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )
    if not troncon.actif:
        return {"id": troncon.id, "actif": False, "message": "Déjà archivé."}
    troncon.actif = False
    # Archiver aussi les sous-tronçons du parent
    for sous in troncon.sous_troncons:
        sous.actif = False
    db.commit()
    return {"id": troncon.id, "actif": False, "message": "Archivé."}


# ===========================================================================
# CRUD sous-tronçons codifiés (DEESP T1A, T1B...)
# ===========================================================================


@router.get(
    "/troncons/{troncon_id}/sous-troncons",
    summary="Liste ordonnée des sous-tronçons d'un axe",
)
def lister_sous_troncons(
    troncon_id: int,
    inclure_archives: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    parent = db.get(Troncon, troncon_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )

    requete = (
        select(SousTroncon)
        .where(SousTroncon.troncon_id == troncon_id)
        .order_by(SousTroncon.ordre)
    )
    if not inclure_archives:
        requete = requete.where(SousTroncon.actif.is_(True))

    sous_troncons = list(db.execute(requete).scalars())
    return {
        "troncon_id": troncon_id,
        "troncon_nom": parent.nom,
        "nb_sous_troncons": len(sous_troncons),
        "sous_troncons": [_serializer_sous_troncon(s) for s in sous_troncons],
    }


@router.post(
    "/troncons/{troncon_id}/sous-troncons",
    summary="Créer un sous-tronçon codifié (T1A, T1B...)",
    description=(
        "Crée un sous-tronçon. Si OSRM est configuré (OSRM_BASE_URL), la "
        "polyline et la distance suivent les vraies routes (boulevard, "
        "pont, etc.). Sinon repli sur un segment droit + distance Haversine."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def creer_sous_troncon(
    troncon_id: int,
    payload: SousTronconCreer,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    parent = db.get(Troncon, troncon_id)
    if parent is None or not parent.actif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon parent id={troncon_id} introuvable ou archivé.",
        )

    # Vérifier unicité du code parmi les sous-tronçons actifs
    existant = db.execute(
        select(SousTroncon).where(
            SousTroncon.troncon_id == troncon_id,
            SousTroncon.code == payload.code,
            SousTroncon.actif.is_(True),
        )
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Le code {payload.code!r} est déjà utilisé pour ce tronçon "
                f"(sous-tronçon id={existant.id})."
            ),
        )

    # Déterminer l'ordre si non fourni
    if payload.ordre is None:
        ordre_max = db.execute(
            select(func.coalesce(func.max(SousTroncon.ordre), 0))
            .where(SousTroncon.troncon_id == troncon_id)
        ).scalar_one()
        ordre = (ordre_max or 0) + 1
    else:
        ordre = payload.ordre

    # OSRM si disponible → polyline qui suit les vraies routes + distance réelle
    polyline: str
    distance: int
    settings = get_settings()
    if settings.osrm_base_url:
        try:
            from app.sources import osrm
            from app.sources.coordonnees import PointGPS
            rep = await osrm.route(
                PointGPS(lat=payload.lat_debut, lon=payload.lon_debut),
                PointGPS(lat=payload.lat_fin, lon=payload.lon_fin),
            )
            polyline = rep.polyline_encodee
            distance = rep.distance_m
        except Exception as exc:  # OSRM indispo → repli silencieux
            polyline = encoder_polyline([
                (payload.lat_debut, payload.lon_debut),
                (payload.lat_fin, payload.lon_fin),
            ])
            distance = distance_haversine_m(
                payload.lat_debut, payload.lon_debut,
                payload.lat_fin, payload.lon_fin,
            )
    else:
        polyline = encoder_polyline([
            (payload.lat_debut, payload.lon_debut),
            (payload.lat_fin, payload.lon_fin),
        ])
        distance = distance_haversine_m(
            payload.lat_debut, payload.lon_debut,
            payload.lat_fin, payload.lon_fin,
        )

    if distance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La distance entre début et fin est nulle.",
        )

    sous = SousTroncon(
        troncon_id=troncon_id,
        code=payload.code.upper(),
        nom_court=payload.nom_court,
        ordre=ordre,
        lat_debut=payload.lat_debut,
        lon_debut=payload.lon_debut,
        lat_fin=payload.lat_fin,
        lon_fin=payload.lon_fin,
        polyline=polyline,
        distance_m=distance,
        actif=True,
    )
    db.add(sous)
    db.commit()
    db.refresh(sous)
    return _serializer_sous_troncon(sous)


@router.patch(
    "/sous-troncons/{sous_id}",
    summary="Modifier le code ou nom d'un sous-tronçon",
)
def maj_sous_troncon(
    sous_id: int,
    payload: SousTronconMaj,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sous = db.get(SousTroncon, sous_id)
    if sous is None or not sous.actif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sous-tronçon id={sous_id} introuvable ou archivé.",
        )
    if payload.code is not None and payload.code.upper() != sous.code:
        # Vérifier unicité du nouveau code
        conflit = db.execute(
            select(SousTroncon).where(
                SousTroncon.troncon_id == sous.troncon_id,
                SousTroncon.code == payload.code.upper(),
                SousTroncon.actif.is_(True),
                SousTroncon.id != sous.id,
            )
        ).scalar_one_or_none()
        if conflit is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code {payload.code!r} déjà utilisé.",
            )
        sous.code = payload.code.upper()
    if payload.nom_court is not None:
        sous.nom_court = payload.nom_court
    db.commit()
    db.refresh(sous)
    return _serializer_sous_troncon(sous)


@router.delete(
    "/sous-troncons/{sous_id}",
    summary="Suppression LOGIQUE d'un sous-tronçon (actif=false)",
)
def supprimer_sous_troncon(
    sous_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sous = db.get(SousTroncon, sous_id)
    if sous is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sous-tronçon id={sous_id} introuvable.",
        )
    sous.actif = False
    db.commit()
    return {"id": sous.id, "code": sous.code, "actif": False, "message": "Archivé."}


# ===========================================================================
# Sérialiseurs
# ===========================================================================


def _serializer_troncon(t: Troncon) -> dict[str, Any]:
    return {
        "id": t.id,
        "nom": t.nom,
        "lat_origine": t.lat_origine,
        "lon_origine": t.lon_origine,
        "lat_destination": t.lat_destination,
        "lon_destination": t.lon_destination,
        "polyline": t.polyline,
        "distance_m": t.distance_m,
        "distance_km": round((t.distance_m or 0) / 1000.0, 2),
        "vitesse_ref_kmh": t.vitesse_ref_kmh,
        "couleur": t.couleur,
        "actif": t.actif,
        "est_axe": getattr(t, "est_axe", True),
    }


def _resume_adoption_collecte(db: Session) -> dict[str, Any]:
    """Renvoie ce que devient la collecte Google après la création d'un tronçon.

    Permet à la page Administration d'afficher dès l'enregistrement :
      - combien de tronçons actifs sont désormais surveillés,
      - le nombre de requêtes/jour estimées,
      - un avertissement si on franchit le plafond Google (250 req/jour).

    Le scheduler ne nécessite pas de redémarrage : `cycle_de_collecte()`
    relit la liste des tronçons actifs à chaque tick.
    """
    settings = get_settings()
    # Granularité réelle de mesure : parents sans sous-tronçon actif + sous-tronçons actifs.
    parents_avec_sous = {
        tid for (tid,) in db.execute(
            select(SousTroncon.troncon_id).where(SousTroncon.actif.is_(True)).distinct()
        ).all()
    }
    ids_parents_actifs = [
        tid for (tid,) in db.execute(
            select(Troncon.id).where(Troncon.actif.is_(True))
        ).all()
    ]
    nb_parents_a_mesurer = sum(1 for tid in ids_parents_actifs if tid not in parents_avec_sous)
    nb_sous_actifs = db.execute(
        select(func.count(SousTroncon.id)).where(SousTroncon.actif.is_(True))
    ).scalar_one() or 0
    nb_actifs = nb_parents_a_mesurer + nb_sous_actifs
    estimation = estimer_requetes_par_jour(settings, nb_actifs)
    avertissement: str | None = None
    if estimation > QUOTA_GOOGLE_JOUR_MAX:
        avertissement = (
            f"Le quota Google estimé ({estimation} req/jour) dépasse la "
            f"limite {QUOTA_GOOGLE_JOUR_MAX}. Augmenter COLLECT_INTERVAL_MINUTES "
            "ou réduire la plage horaire."
        )
    return {
        "nb_troncons_actifs": nb_actifs,
        "google_requetes_par_jour": estimation,
        "plafond_google": QUOTA_GOOGLE_JOUR_MAX,
        "scheduler_redemarrage_requis": False,
        "inclusion_prochain_cycle": True,
        "avertissement_quota": avertissement,
    }


def _serializer_sous_troncon(s: SousTroncon) -> dict[str, Any]:
    return {
        "id": s.id,
        "troncon_id": s.troncon_id,
        "code": s.code,
        "nom_court": s.nom_court,
        "ordre": s.ordre,
        "lat_debut": s.lat_debut,
        "lon_debut": s.lon_debut,
        "lat_fin": s.lat_fin,
        "lon_fin": s.lon_fin,
        "polyline": s.polyline,
        "distance_m": s.distance_m,
        "actif": s.actif,
    }
