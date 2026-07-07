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

import asyncio
import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

logger = logging.getLogger("paa.administration")

from app.collecte.scheduler import (
    QUOTA_GOOGLE_JOUR_MAX,
    estimer_requetes_par_jour,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import SousTroncon, Troncon, axe_sous_troncons
from app.sources.polyline import (
    calculer_sens_par_axe,
    distance_cumulee_m,
    distance_haversine_m,
    encoder_polyline,
)


router = APIRouter(prefix="/administration", tags=["administration"])


# ===========================================================================
# Réordonnancement des sous-tronçons — ordre DEESP officiel
# ===========================================================================

# Ordre officiel de traversée des sous-tronçons codifiés par axe DEESP.
# Clé = axe_id (1-6), Valeur = liste ordonnée des codes de sous-tronçons
# dans le sens de circulation de cet axe.
_ORDRE_DEESP_PAR_AXE: dict[int, list[str]] = {
    # Axe 1 — CARENA → Pharmacie Palm Beach (aller)
    1: ["T1C", "T1A", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"],
    # Axe 2 — Pharmacie Palm Beach → CARENA (retour)
    2: ["T11", "T10", "T9", "T8", "T7", "T6", "T5", "T4", "T3", "T2", "T1A", "T1C"],
    # Axe 3 — Toyota CFAO → Pharmacie Palm Beach (aller)
    3: ["T1B", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"],
    # Axe 4 — Pharmacie Palm Beach → Toyota CFAO (retour)
    4: ["T11", "T10", "T9", "T8", "T7", "T6", "T5", "T4", "T1B"],
    # Axe 5 — Agence SODECI → Pharmacie Palm Beach (aller)
    5: ["T1D", "T7", "T8", "T9", "T10", "T11"],
    # Axe 6 — Pharmacie Palm Beach → Agence SODECI (retour)
    6: ["T11", "T10", "T9", "T8", "T7", "T1D"],
}


def _reordonner_sous_troncons_par_axe(db: Session, axe_id: int) -> None:
    """Recalcule l'ordre des sous-tronçons d'un axe.

    Pour les 6 axes officiels DEESP (id 1-6) : l'ordre est fixé selon
    la séquence officielle du rapport (§ CLAUDE.md 23). Un sous-tronçon
    absent de la séquence officielle est placé après les codes connus,
    trié par distance GPS.

    Pour les axes créés via Administration (id > 6) : l'ordre est
    calculé par distance Haversine depuis l'origine de l'axe, en tenant
    compte du sens de circulation (direct / inverse).
    """
    axe = db.get(Troncon, axe_id)
    if axe is None or axe.lat_origine is None or axe.lon_origine is None:
        return

    liens = db.execute(
        select(axe_sous_troncons.c.sous_troncon_id)
        .where(axe_sous_troncons.c.axe_id == axe_id)
    ).scalars().all()
    if not liens:
        return

    subs = list(db.execute(
        select(SousTroncon)
        .where(SousTroncon.id.in_(liens), SousTroncon.actif.is_(True))
    ).scalars())
    if not subs:
        return

    ordre_deesp = _ORDRE_DEESP_PAR_AXE.get(axe_id)
    if ordre_deesp:
        # Axes officiels : tri par position dans la séquence DEESP.
        # Codes absents de la séquence → placés à la fin (ordre 999+).
        index_par_code = {code: i for i, code in enumerate(ordre_deesp)}
        subs.sort(key=lambda s: index_par_code.get(s.code, 999))
    else:
        # Axes créés via Administration : tri par distance GPS.
        subs_avec_dist = []
        for s in subs:
            sens = calculer_sens_par_axe(
                axe.lat_origine, axe.lon_origine,
                s.lat_debut, s.lon_debut, s.lat_fin, s.lon_fin,
            )
            lat_entree, lon_entree = (
                (s.lat_debut, s.lon_debut) if sens == "direct"
                else (s.lat_fin, s.lon_fin)
            )
            d = distance_haversine_m(
                axe.lat_origine, axe.lon_origine, lat_entree, lon_entree,
            )
            subs_avec_dist.append((d, s))
        subs_avec_dist.sort(key=lambda x: x[0])
        subs = [s for _, s in subs_avec_dist]

    for nouvel_ordre, s in enumerate(subs, start=1):
        db.execute(
            axe_sous_troncons.update()
            .where(
                axe_sous_troncons.c.axe_id == axe_id,
                axe_sous_troncons.c.sous_troncon_id == s.id,
            )
            .values(ordre=nouvel_ordre)
        )
        if axe_id == s.troncon_id and s.ordre != nouvel_ordre:
            s.ordre = nouvel_ordre


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
            "Si True (défaut), marqué comme axe. Si False, "
            "tronçon codifié (enfant d'un axe)."
        ),
    )


class TronconMaj(BaseModel):
    """Payload pour PATCH /administration/troncons/{id} — tous les champs sont optionnels."""
    nom: str | None = Field(None, min_length=3, max_length=200)
    vitesse_ref_kmh: float | None = None
    couleur: str | None = None
    lat_origine: float | None = None
    lon_origine: float | None = None
    lat_destination: float | None = None
    lon_destination: float | None = None
    # Si l'une des 4 coord change, la polyline et la distance sont recalculées
    # (OSRM si dispo, sinon Haversine) — cf. maj_troncon.
    distance_m: int | None = None
    est_axe: bool | None = None


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
    axe_ids: list[int] | None = Field(
        default=None,
        description=(
            "Multi-parent (migration 0016) : liste d'ids d'axes auxquels "
            "rattacher ce sous-tronçon en plus du parent principal (dans "
            "l'URL). Utile pour un pont partagé — évite la duplication. "
            "Le parent principal est TOUJOURS ajouté même s'il est omis. "
            "Si None, seul le parent principal est rattaché."
        ),
    )


class SousTronconMaj(BaseModel):
    """Payload pour PATCH /administration/sous-troncons/{id}."""
    code: str | None = Field(None, min_length=2, max_length=10)
    nom_court: str | None = Field(None, min_length=3, max_length=120)
    lat_debut: float | None = None
    lon_debut: float | None = None
    lat_fin: float | None = None
    lon_fin: float | None = None
    axe_ids: list[int] | None = Field(
        default=None,
        description=(
            "Remplace la liste des axes parents rattachés (multi-parent). "
            "Le parent principal (troncon_id) est TOUJOURS ajouté à la liste."
        ),
    )


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
    summary="Mettre à jour un tronçon (nom, couleur, vitesse, coordonnées)",
    description=(
        "Tous les champs sont optionnels. Si l'une des 4 coordonnées est "
        "modifiée, la polyline et la distance sont recalculées (OSRM si "
        "configuré, sinon segment droit + Haversine). Après recalcul de "
        "l'origine, tous les sous-tronçons rattachés à cet axe sont "
        "automatiquement réordonnés par distance GPS (§ 18)."
    ),
)
async def maj_troncon(
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
    if payload.est_axe is not None:
        troncon.est_axe = payload.est_axe

    coords_changees = any(
        v is not None for v in [
            payload.lat_origine, payload.lon_origine,
            payload.lat_destination, payload.lon_destination,
        ]
    )
    if coords_changees:
        if payload.lat_origine is not None: troncon.lat_origine = payload.lat_origine
        if payload.lon_origine is not None: troncon.lon_origine = payload.lon_origine
        if payload.lat_destination is not None: troncon.lat_destination = payload.lat_destination
        if payload.lon_destination is not None: troncon.lon_destination = payload.lon_destination

        settings = get_settings()
        pts = [
            (troncon.lat_origine, troncon.lon_origine),
            (troncon.lat_destination, troncon.lon_destination),
        ]
        polyline: str = encoder_polyline(pts)
        distance = payload.distance_m if payload.distance_m is not None else distance_cumulee_m(pts)
        if settings.osrm_base_url:
            try:
                from app.sources import osrm
                from app.sources.coordonnees import PointGPS
                rep = await osrm.route(
                    PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine),
                    PointGPS(lat=troncon.lat_destination, lon=troncon.lon_destination),
                )
                polyline = rep.polyline_encodee
                if payload.distance_m is None:
                    distance = rep.distance_m
            except Exception:
                pass
        troncon.polyline = polyline
        troncon.distance_m = distance
        # Ré-ordonne les sous-tronçons de cet axe : l'origine a bougé.
        _reordonner_sous_troncons_par_axe(db, troncon_id)
    elif payload.distance_m is not None:
        troncon.distance_m = payload.distance_m

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

    # Inclut les sous-tronçons rattachés à cet axe :
    #  - soit comme parent principal (`troncon_id == axe_id`, rétro-compat),
    #  - soit via la M2M (`axe_sous_troncons`, migration 0016 — pour un
    #    tronçon partagé rattaché à un axe secondaire, ex. le retour).
    ids_via_m2m = db.execute(
        select(axe_sous_troncons.c.sous_troncon_id)
        .where(axe_sous_troncons.c.axe_id == troncon_id)
    ).scalars().all()

    from sqlalchemy import or_
    requete = (
        select(SousTroncon)
        .where(or_(
            SousTroncon.troncon_id == troncon_id,
            SousTroncon.id.in_(ids_via_m2m) if ids_via_m2m else False,
        ))
    )
    if not inclure_archives:
        requete = requete.where(SousTroncon.actif.is_(True))

    sous_troncons = list(db.execute(requete).scalars())

    # Tri par l'ordre M2M spécifique à CET axe (respecte le sens de circulation
    # propre, cf. _reordonner_sous_troncons_par_axe). Repli sur SousTroncon.ordre.
    ordre_ici: dict[int, int] = {
        sid: o for (sid, o) in db.execute(
            select(
                axe_sous_troncons.c.sous_troncon_id,
                axe_sous_troncons.c.ordre,
            ).where(axe_sous_troncons.c.axe_id == troncon_id)
        ).all()
    }
    sous_troncons.sort(key=lambda s: ordre_ici.get(s.id, s.ordre))
    # Charger les axes parents de chaque sous-tronçon en un seul SELECT
    liens = db.execute(
        select(axe_sous_troncons.c.sous_troncon_id, axe_sous_troncons.c.axe_id)
        .where(axe_sous_troncons.c.sous_troncon_id.in_([s.id for s in sous_troncons]))
    ).all() if sous_troncons else []
    axes_par_sous: dict[int, list[int]] = {}
    for sous_id, axe_id in liens:
        axes_par_sous.setdefault(sous_id, []).append(axe_id)

    return {
        "troncon_id": troncon_id,
        "troncon_nom": parent.nom,
        "nb_sous_troncons": len(sous_troncons),
        "sous_troncons": [
            _serializer_sous_troncon(
                s, db=db,
                axes_ids=axes_par_sous.get(s.id, [s.troncon_id]),
            ) for s in sous_troncons
        ],
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
    db.flush()  # obtient sous.id sans commit

    # Multi-parent : construit la liste finale des axes parents.
    axes_finaux: set[int] = {troncon_id}
    if payload.axe_ids:
        # Vérifie que tous les axes existent, sont actifs et sont bien des axes
        # principaux (est_axe=True). Un tronçon codifié (est_axe=False) ne peut
        # pas être parent d'un autre tronçon codifié.
        cibles = list(db.execute(
            select(Troncon).where(
                Troncon.id.in_(payload.axe_ids),
                Troncon.actif.is_(True),
            )
        ).scalars())
        ids_valides = {t.id for t in cibles if getattr(t, "est_axe", True)}
        manquants = set(payload.axe_ids) - ids_valides
        if manquants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Axes parents invalides ou archivés : {sorted(manquants)}. "
                    "Seuls des axes principaux actifs peuvent être parents."
                ),
            )
        axes_finaux.update(ids_valides)

    # Insertion dans la table de jonction — ordre = celui calculé sur le
    # parent principal, réutilisé partout (simplification acceptable, ordre
    # spécifique par parent = amélioration future).
    for axe_id in axes_finaux:
        db.execute(insert(axe_sous_troncons).values(
            axe_id=axe_id, sous_troncon_id=sous.id, ordre=ordre,
        ))
    # Réordonnancement automatique sur CHAQUE axe parent.
    # Peu importe l'ordre d'ajout, tous les sous-tronçons sont retriés
    # par position GPS le long du parcours de chaque axe (avec sens propre).
    for axe_id in axes_finaux:
        _reordonner_sous_troncons_par_axe(db, axe_id)
    db.commit()
    db.refresh(sous)
    return _serializer_sous_troncon(
        sous, db=db, axes_ids=list(axes_finaux),
    )


@router.patch(
    "/sous-troncons/{sous_id}",
    summary="Modifier code, nom, coordonnées ou axes parents d'un sous-tronçon",
    description=(
        "Tous les champs sont optionnels. Si une coordonnée change, la "
        "polyline et la distance sont recalculées, et TOUS les axes parents "
        "de ce sous-tronçon sont réordonnés par distance GPS."
    ),
)
async def maj_sous_troncon(
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

    # Coordonnées : recalcule polyline + distance si l'une bouge.
    coords_changees = any(
        v is not None for v in [
            payload.lat_debut, payload.lon_debut,
            payload.lat_fin, payload.lon_fin,
        ]
    )
    if coords_changees:
        if payload.lat_debut is not None: sous.lat_debut = payload.lat_debut
        if payload.lon_debut is not None: sous.lon_debut = payload.lon_debut
        if payload.lat_fin is not None: sous.lat_fin = payload.lat_fin
        if payload.lon_fin is not None: sous.lon_fin = payload.lon_fin
        settings = get_settings()
        polyline = encoder_polyline([
            (sous.lat_debut, sous.lon_debut),
            (sous.lat_fin, sous.lon_fin),
        ])
        distance = distance_haversine_m(
            sous.lat_debut, sous.lon_debut,
            sous.lat_fin, sous.lon_fin,
        )
        if settings.osrm_base_url:
            try:
                from app.sources import osrm
                from app.sources.coordonnees import PointGPS
                rep = await osrm.route(
                    PointGPS(lat=sous.lat_debut, lon=sous.lon_debut),
                    PointGPS(lat=sous.lat_fin, lon=sous.lon_fin),
                )
                polyline = rep.polyline_encodee
                distance = rep.distance_m
            except Exception:
                pass
        sous.polyline = polyline
        sous.distance_m = distance

    if payload.axe_ids is not None:
        cibles = list(db.execute(
            select(Troncon).where(
                Troncon.id.in_(payload.axe_ids),
                Troncon.actif.is_(True),
            )
        ).scalars())
        ids_valides = {t.id for t in cibles if getattr(t, "est_axe", True)}
        manquants = set(payload.axe_ids) - ids_valides
        if manquants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Axes parents invalides ou archivés : {sorted(manquants)}."
                ),
            )
        axes_finaux = ids_valides | {sous.troncon_id}
        # Remplacement complet des liens M2M
        db.execute(delete(axe_sous_troncons).where(
            axe_sous_troncons.c.sous_troncon_id == sous.id
        ))
        for axe_id in axes_finaux:
            db.execute(insert(axe_sous_troncons).values(
                axe_id=axe_id, sous_troncon_id=sous.id, ordre=sous.ordre,
            ))
        # Réordonnancement automatique sur chaque axe touché (ancien + nouveau).
        anciens_axes = {row[0] for row in db.execute(
            select(axe_sous_troncons.c.axe_id).where(
                axe_sous_troncons.c.sous_troncon_id == sous.id
            )
        ).all()}
        for axe_id in axes_finaux | anciens_axes:
            _reordonner_sous_troncons_par_axe(db, axe_id)
    elif coords_changees:
        # Coords ont changé sans toucher aux liens M2M : réordonne les axes actuels.
        axes_actuels_ids = {row[0] for row in db.execute(
            select(axe_sous_troncons.c.axe_id).where(
                axe_sous_troncons.c.sous_troncon_id == sous.id
            )
        ).all()}
        axes_actuels_ids.add(sous.troncon_id)
        for axe_id in axes_actuels_ids:
            _reordonner_sous_troncons_par_axe(db, axe_id)

    db.commit()
    db.refresh(sous)
    axes_actuels = [row[0] for row in db.execute(
        select(axe_sous_troncons.c.axe_id).where(
            axe_sous_troncons.c.sous_troncon_id == sous.id
        )
    ).all()]
    return _serializer_sous_troncon(sous, db=db, axes_ids=axes_actuels)


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
    # Parents sans sous-tronçon actif + liens M2M sous-tronçons
    axes_couverts_par_sous = {
        aid for (aid,) in db.execute(
            select(axe_sous_troncons.c.axe_id).distinct()
        ).all()
    }
    for (tid,) in db.execute(
        select(SousTroncon.troncon_id).where(SousTroncon.actif.is_(True)).distinct()
    ).all():
        axes_couverts_par_sous.add(tid)
    ids_parents_actifs = [
        tid for (tid,) in db.execute(
            select(Troncon.id).where(Troncon.actif.is_(True))
        ).all()
    ]
    nb_parents_a_mesurer = sum(
        1 for tid in ids_parents_actifs if tid not in axes_couverts_par_sous
    )
    nb_liens_sous = db.execute(
        select(func.count()).select_from(
            axe_sous_troncons.join(
                SousTroncon,
                axe_sous_troncons.c.sous_troncon_id == SousTroncon.id,
            )
        ).where(SousTroncon.actif.is_(True))
    ).scalar_one() or 0
    nb_sous_orphelins = db.execute(
        select(func.count(SousTroncon.id))
        .where(
            SousTroncon.actif.is_(True),
            ~SousTroncon.id.in_(select(axe_sous_troncons.c.sous_troncon_id)),
        )
    ).scalar_one() or 0
    nb_actifs = nb_parents_a_mesurer + nb_liens_sous + nb_sous_orphelins
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


# ===========================================================================
# Géocodage — proxy Nominatim pour l'autocomplétion des lieux (P12.3)
# ===========================================================================


# Cache mémoire process — évite de re-taper Nominatim pour la même requête.
_CACHE_GEOCODE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL_SEC = 3600
# Anti-flood — délai minimal entre 2 appels sortants vers Nominatim (ToS OSM).
_DERNIER_APPEL_NOMINATIM: dict[str, float] = {"t": 0.0}
_DELAI_NOMINATIM_SEC = 1.1

# Bounding box élargie sur l'agglomération d'Abidjan pour biaiser les
# résultats. Nominatim n'exclut PAS les résultats hors bbox par défaut ;
# `viewbox` ne fait que prioriser.
_VIEWBOX_ABIDJAN = "-4.15,5.10,-3.85,5.55"  # left,top,right,bottom (lon,lat)


@router.get(
    "/preview-route",
    summary="Prévisualisation du tracé OSRM entre 2 points GPS",
    description=(
        "Retourne la polyline encodée + la distance calculée par OSRM entre "
        "(lat1, lon1) et (lat2, lon2). Permet de prévisualiser le vrai tracé "
        "routier avant de créer un axe ou un sous-tronçon. Si OSRM n'est pas "
        "configuré, retourne un segment droit Haversine. Résultat en cache "
        "mémoire 10 min par paire de points."
    ),
)
async def preview_route(
    lat1: float = Query(...),
    lon1: float = Query(...),
    lat2: float = Query(...),
    lon2: float = Query(...),
) -> dict[str, Any]:
    settings = get_settings()
    cle = f"{lat1:.5f},{lon1:.5f}::{lat2:.5f},{lon2:.5f}"
    maintenant = time.time()
    # Réutilise le cache _CACHE_GEOCODE (structure identique) sous préfixe distinct.
    cle_cache = f"preview::{cle}"
    if cle_cache in _CACHE_GEOCODE:
        t_cache, cached = _CACHE_GEOCODE[cle_cache]
        if maintenant - t_cache < 600 and isinstance(cached, list) and cached:
            return cached[0]  # type: ignore[return-value]

    polyline = encoder_polyline([(lat1, lon1), (lat2, lon2)])
    distance = distance_haversine_m(lat1, lon1, lat2, lon2)
    source = "haversine"

    if settings.osrm_base_url:
        try:
            from app.sources import osrm
            from app.sources.coordonnees import PointGPS
            rep = await osrm.route(
                PointGPS(lat=lat1, lon=lon1),
                PointGPS(lat=lat2, lon=lon2),
            )
            polyline = rep.polyline_encodee
            distance = rep.distance_m
            source = "osrm"
        except Exception as exc:
            logger.warning("Preview OSRM indisponible (%s) → repli Haversine.", exc)

    resultat = {
        "polyline": polyline,
        "distance_m": distance,
        "distance_km": round(distance / 1000.0, 2),
        "source": source,
    }
    _CACHE_GEOCODE[cle_cache] = (maintenant, [resultat])  # type: ignore[arg-type]
    return resultat


# Ancre géographique d'Abidjan pour biaiser Google Places
_ABIDJAN_LAT = 5.29
_ABIDJAN_LON = -4.0
_ABIDJAN_RAYON_M = 25_000  # 25 km — couvre l'agglomération et le port


async def _google_places_autocomplete(
    q: str, limit: int, cle_api: str,
) -> list[dict[str, Any]]:
    """Interroge Google Places API (New) — 'Autocomplete' + 'Place Details'.

    Retourne une liste `[{nom_affiche, lat, lon, type, importance}]`
    filtrée sur la zone Abidjan et enrichie des coordonnées via
    Place Details (une requête par suggestion).

    Utilise le même GOOGLE_ROUTES_API_KEY (la clé doit autoriser
    l'API 'Places API (New)' dans Google Cloud Console).
    """
    url_autocomplete = "https://places.googleapis.com/v1/places:autocomplete"
    entetes = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": cle_api,
    }
    corps = {
        "input": q,
        "languageCode": "fr",
        "regionCode": "CI",
        "locationBias": {
            "circle": {
                "center": {"latitude": _ABIDJAN_LAT, "longitude": _ABIDJAN_LON},
                "radius": float(_ABIDJAN_RAYON_M),
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            rep = await client.post(url_autocomplete, json=corps, headers=entetes)
            rep.raise_for_status()
            payload = rep.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("Google Places Autocomplete indisponible : %s", exc)
        return []

    suggestions = payload.get("suggestions", [])[:limit]
    resultats: list[dict[str, Any]] = []
    for s in suggestions:
        pp = s.get("placePrediction") or {}
        place_id = pp.get("placeId")
        texte = (pp.get("text") or {}).get("text") or ""
        structured = pp.get("structuredFormat") or {}
        nom_principal = (structured.get("mainText") or {}).get("text") or texte
        nom_secondaire = (structured.get("secondaryText") or {}).get("text") or ""
        if not place_id:
            continue
        # Place Details pour récupérer lat/lon
        try:
            url_details = f"https://places.googleapis.com/v1/places/{place_id}"
            entetes_det = {
                "X-Goog-Api-Key": cle_api,
                "X-Goog-FieldMask": "location,displayName,formattedAddress",
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                rep_det = await client.get(url_details, headers=entetes_det)
                rep_det.raise_for_status()
                det = rep_det.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Google Places Details KO place_id=%s : %s", place_id, exc)
            continue

        loc = det.get("location") or {}
        try:
            lat = float(loc["latitude"])
            lon = float(loc["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        # Filtre "élargi Abidjan" — évite un résultat à Bouaké par exemple
        if not (4.9 <= lat <= 5.55 and -4.25 <= lon <= -3.7):
            continue

        libelle = nom_principal
        if nom_secondaire and nom_secondaire.lower() not in libelle.lower():
            libelle = f"{nom_principal} — {nom_secondaire}"

        resultats.append({
            "nom_affiche": libelle,
            "lat": lat,
            "lon": lon,
            "type": "google_place",
            "importance": 0.85,
            "source": "google_places",
        })

    return resultats


@router.get(
    "/geocoder",
    summary="Autocomplétion de lieux — cascade Landmarks PAA → Google Places → Nominatim",
    description=(
        "Cascade à 3 niveaux :\n"
        "1. **Landmarks PAA** : dictionnaire curé des points d'intérêt de la "
        "zone portuaire (CARENA, Palm Beach, GMA, CIMIVOIRE, DGI, SOTRA…) "
        "avec coordonnées Google Maps validées.\n"
        "2. **Google Places API** (si `GOOGLE_ROUTES_API_KEY` est configurée "
        "et couvre l'API Places (New)) — biais sur Abidjan, résultats de "
        "qualité équivalente à Google Maps.\n"
        "3. **Nominatim OSM** en repli (couverture Abidjan limitée).\n\n"
        "Cache mémoire 1 h par requête. Filtre géographique élargi Abidjan."
    ),
)
async def geocoder_lieu(
    q: str = Query(..., min_length=2, max_length=200,
                   description="Texte partiel de lieu (ex. 'palm beach')"),
    limit: int = Query(5, ge=1, le=10),
) -> dict[str, Any]:
    """Autocomplétion en cascade avec cache et rate limiting."""
    from app.sources.landmarks_paa import rechercher_landmarks

    cle = f"{q.strip().lower()}::{limit}"
    maintenant = time.time()

    if cle in _CACHE_GEOCODE:
        t_cache, resultats_cache = _CACHE_GEOCODE[cle]
        if maintenant - t_cache < _CACHE_TTL_SEC:
            return {"q": q, "resultats": resultats_cache, "cache": True}

    resultats: list[dict[str, Any]] = []

    # 1. Landmarks curés (instantané, offline, coords Google Maps validées)
    landmarks = rechercher_landmarks(q, limit=limit)
    resultats.extend(landmarks)

    # 2. Google Places API — si clé dispo et budget quota respecté
    settings = get_settings()
    besoin_plus = len(resultats) < limit
    if besoin_plus and settings.google_routes_api_key:
        limite_google = limit - len(resultats)
        places = await _google_places_autocomplete(
            q, limite_google, settings.google_routes_api_key,
        )
        # Dédoublonne : évite d'ajouter un Google Place trop proche d'un landmark
        for p in places:
            doublon = any(
                abs(p["lat"] - r["lat"]) < 5e-4 and abs(p["lon"] - r["lon"]) < 5e-4
                for r in resultats
            )
            if not doublon:
                resultats.append(p)
                if len(resultats) >= limit:
                    break

    # 3. Nominatim OSM en dernier repli si vraiment aucun résultat
    if not resultats:
        depuis_dernier = maintenant - _DERNIER_APPEL_NOMINATIM["t"]
        if depuis_dernier < _DELAI_NOMINATIM_SEC:
            await asyncio.sleep(_DELAI_NOMINATIM_SEC - depuis_dernier)
        _DERNIER_APPEL_NOMINATIM["t"] = time.time()

        parametres = {
            "q": q, "format": "jsonv2", "addressdetails": 1, "limit": limit,
            "countrycodes": "ci", "viewbox": _VIEWBOX_ABIDJAN, "bounded": 0,
            "accept-language": "fr",
        }
        entetes = {
            "User-Agent": "FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                rep = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params=parametres, headers=entetes,
                )
                rep.raise_for_status()
                donnees = rep.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Nominatim indisponible pour q=%r : %s", q, exc)
            donnees = []

        for r in donnees[:limit]:
            try:
                lat = float(r["lat"])
                lon = float(r["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            resultats.append({
                "nom_affiche": r.get("display_name", ""),
                "lat": lat, "lon": lon,
                "type": r.get("category", r.get("type", "lieu")),
                "importance": r.get("importance", 0.0),
                "source": "nominatim",
            })

    _CACHE_GEOCODE[cle] = (maintenant, resultats)
    return {"q": q, "resultats": resultats, "cache": False}


# ===========================================================================
# Sérialiseurs — suite
# ===========================================================================


def _serializer_sous_troncon(
    s: SousTroncon,
    db: Session | None = None,
    axes_ids: list[int] | None = None,
) -> dict[str, Any]:
    ids = axes_ids if axes_ids is not None else [s.troncon_id]
    # Enrichit chaque parent avec son sens de circulation (direct/inverse).
    # L'UI peut ainsi afficher un badge ⇢ / ⇠ par rattachement.
    axes_details: list[dict[str, Any]] = []
    if db is not None and ids:
        axes = list(db.execute(
            select(Troncon).where(Troncon.id.in_(ids))
        ).scalars())
        for a in axes:
            if a.lat_origine is None or a.lon_origine is None:
                sens = "direct"
            else:
                sens = calculer_sens_par_axe(
                    a.lat_origine, a.lon_origine,
                    s.lat_debut, s.lon_debut, s.lat_fin, s.lon_fin,
                )
            axes_details.append({
                "id": a.id,
                "nom": a.nom,
                "sens": sens,
            })
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
        # Multi-parent (migration 0016). Contient TOUJOURS `troncon_id`.
        "axe_ids": ids,
        # Détail par axe avec sens de circulation calculé depuis la géométrie.
        "axes": axes_details,
    }
