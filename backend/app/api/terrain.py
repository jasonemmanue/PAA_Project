"""Routeur /terrain — validation terrain hebdomadaire (P5).

Endpoints :
  - POST /terrain/import      → upload d'un fichier GPX, découpage automatique
                                aux bornes des tronçons surveillés, calcul de
                                l'écart relatif par tronçon.
  - GET  /terrain/releves     → historique des relevés (filtres par tronçon).
  - GET  /terrain/calibration → moyenne mobile des écarts par tronçon.

Cascade de calcul (cf. CLAUDE.md § 4.1 — Indicateurs) :
  1. Parser le GPX → liste de points horodatés.
  2. Pour chaque tronçon T des 6 surveillés, détecter le sous-segment
     correspondant (via app.terrain.decoupage).
  3. (Optionnel) Appeler OSRM Match sur la sous-trace pour obtenir une
     confiance et valider que la trace suit bien le réseau routier.
  4. Pour chaque segment détecté, chercher dans `mesures` la ligne `google`
     la plus proche dans le temps avec `duree_trafic_s NOT NULL`.
  5. ε = (T_terrain - T_api) / T_api — stocké dans `releves_terrain`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Mesure, ReleveTerrain, SourceMesure, Troncon
from app.sources import osrm
from app.sources.coordonnees import PointGPS
from app.sources.gpx_parser import PointTrace, parser_gpx_octets
from app.terrain.calibration import calibration_par_troncon
from app.terrain.decoupage import SegmentTroncon, decouper_trace_par_troncon


logger = logging.getLogger("paa.api.terrain")

router = APIRouter(prefix="/terrain", tags=["validation terrain"])


# Fenêtre maximale (secondes) pour considérer qu'une mesure Google est
# « simultanée » d'un passage terrain. Au-delà, on n'apparie pas et
# `ecart_relatif` reste NULL.
FENETRE_APPARIEMENT_S = 30 * 60  # 30 minutes


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _slug(texte: str) -> str:
    """Slugifie un libellé pour construire un nom de fichier sûr."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Za-z0-9._-]+", "_", sans_accents).strip("_") or "fichier"


def _stocker_gpx(contenu: bytes, date_session: date, nom_original: str) -> str:
    """Persiste le GPX sur disque et retourne le chemin relatif."""
    dossier = Path(get_settings().gpx_storage_dir).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{date_session.isoformat()}_{_slug(Path(nom_original).stem)}.gpx"
    cible = dossier / nom
    # En cas de collision (même nom), on suffixe par un timestamp.
    if cible.exists():
        ts = int(datetime.now(tz=timezone.utc).timestamp())
        cible = dossier / f"{date_session.isoformat()}_{_slug(Path(nom_original).stem)}_{ts}.gpx"
    cible.write_bytes(contenu)
    return str(cible)


def _mesure_google_la_plus_proche(
    db: Session, troncon_id: int, instant_utc: datetime,
) -> Mesure | None:
    """Cherche la mesure Google avec `duree_trafic_s` non NULL la plus proche.

    Renvoie None si aucune mesure n'est dans la fenêtre `FENETRE_APPARIEMENT_S`.
    """
    # On trie par distance temporelle absolue à l'instant cible.
    # SQLAlchemy ne gère pas directement ABS sur timedelta — on utilise EXTRACT(EPOCH).
    requete = (
        select(Mesure)
        .where(
            Mesure.troncon_id == troncon_id,
            Mesure.source == SourceMesure.google,
            Mesure.duree_trafic_s.is_not(None),
        )
        .order_by(
            func.abs(
                func.extract("epoch", Mesure.horodatage)
                - func.extract("epoch", instant_utc)
            )
        )
        .limit(1)
    )
    mesure = db.execute(requete).scalar_one_or_none()
    if mesure is None:
        return None
    ecart_s = abs((mesure.horodatage - instant_utc).total_seconds())
    return mesure if ecart_s <= FENETRE_APPARIEMENT_S else None


async def _match_sous_trace(trace: list[PointTrace], segment: SegmentTroncon) -> float | None:
    """Appelle OSRM Match sur la sous-trace, renvoie la confiance moyenne.

    Renvoie None si OSRM n'est pas configuré ou si l'appel échoue (l'écart
    relatif reste calculable sans ce signal — c'est juste un bonus de
    fiabilité).
    """
    if get_settings().osrm_base_url is None:
        return None
    sous_points = [
        PointGPS(lat=trace[i].lat, lon=trace[i].lon)
        for i in range(segment.index_debut, segment.index_fin + 1)
    ]
    timestamps = [
        trace[i].timestamp_unix for i in range(segment.index_debut, segment.index_fin + 1)
    ]
    # OSRM Match limite la taille de la requête — on sous-échantillonne si trop long.
    LIMITE_OSRM = 100
    if len(sous_points) > LIMITE_OSRM:
        pas = max(1, len(sous_points) // LIMITE_OSRM)
        sous_points = sous_points[::pas]
        timestamps = timestamps[::pas]
    try:
        rep = await osrm.match(sous_points, timestamps=timestamps)
        return float(rep.confiance_moyenne)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("OSRM Match a échoué : %s", exc)
        return None


# ---------------------------------------------------------------------------
# POST /terrain/import
# ---------------------------------------------------------------------------


@router.post(
    "/import",
    summary="Importe un GPX terrain, le découpe par tronçon et calcule les écarts",
    description=(
        "Accepte un fichier `.gpx` avec horodatages. Pour chaque tronçon des 6 "
        "surveillés, détecte automatiquement le sous-segment correspondant "
        "(point d'origine et de destination présents dans la trace), calcule "
        "la durée réelle, recherche la mesure Google la plus proche dans le "
        "temps (fenêtre 30 min) et calcule ε = (T_terrain - T_api) / T_api. "
        "Enregistre une ligne `releves_terrain` par tronçon détecté."
    ),
    status_code=status.HTTP_200_OK,
)
async def importer_gpx(
    fichier: UploadFile = File(..., description="Fichier GPX avec horodatages."),
    date_session: date | None = Form(
        None,
        description="Date de la session terrain. Par défaut : date du premier point GPX.",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Importe un GPX, le découpe par tronçon et persiste les relevés."""
    if not fichier.filename or not fichier.filename.lower().endswith(".gpx"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier doit avoir l'extension .gpx",
        )

    contenu = await fichier.read()

    # 1. Parsing du GPX
    try:
        trace = parser_gpx_octets(contenu)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    if date_session is None:
        date_session = trace[0].horodatage.date()

    # 2. Persistance du GPX brut sur disque
    chemin_gpx = _stocker_gpx(contenu, date_session, fichier.filename)

    # 3. Découpage automatique : on récupère les tronçons actifs avec coords résolues
    troncons = list(
        db.execute(
            select(Troncon).where(
                Troncon.actif.is_(True),
                Troncon.lat_origine.is_not(None),
                Troncon.lon_origine.is_not(None),
                Troncon.lat_destination.is_not(None),
                Troncon.lon_destination.is_not(None),
            )
        ).scalars()
    )
    segments = decouper_trace_par_troncon(trace, troncons)
    if not segments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Aucun tronçon surveillé n'a été détecté dans la trace. "
                "Vérifiez que le trajet couvre bien les bornes d'au moins un "
                "des 6 tronçons (rayon de tolérance : 80 m)."
            ),
        )

    # 4. Pour chaque segment : confiance OSRM Match (best effort) + appariement Google
    resultats: list[dict[str, Any]] = []
    troncons_par_id = {t.id: t for t in troncons}

    for segment in segments:
        troncon = troncons_par_id[segment.troncon_id]
        confiance = await _match_sous_trace(trace, segment)

        mesure_google = _mesure_google_la_plus_proche(
            db, troncon.id, segment.horodatage_passage,
        )
        duree_api_s: int | None = None
        ecart_relatif: float | None = None
        if mesure_google is not None and mesure_google.duree_trafic_s:
            duree_api_s = int(mesure_google.duree_trafic_s)
            ecart_relatif = (
                float(segment.duree_s) - float(duree_api_s)
            ) / float(duree_api_s)

        releve = ReleveTerrain(
            troncon_id=troncon.id,
            date_session=date_session,
            horodatage_passage=segment.horodatage_passage,
            fichier_gpx=chemin_gpx,
            duree_mesuree_s=segment.duree_s,
            duree_api_s=duree_api_s,
            ecart_relatif=ecart_relatif,
            confiance_matching=confiance,
        )
        db.add(releve)
        db.flush()  # pour récupérer l'ID

        resultats.append({
            "id": releve.id,
            "troncon_id": troncon.id,
            "troncon_nom": troncon.nom,
            "horodatage_passage_utc": segment.horodatage_passage.isoformat(),
            "duree_terrain_s": segment.duree_s,
            "duree_api_s": duree_api_s,
            "ecart_relatif": (
                round(ecart_relatif, 4) if ecart_relatif is not None else None
            ),
            "confiance_matching": (
                round(confiance, 3) if confiance is not None else None
            ),
            "distance_trace_m": int(round(segment.distance_m_trace)),
            "distance_officielle_m": troncon.distance_m,
        })

    db.commit()

    return {
        "date_session": date_session.isoformat(),
        "fichier_gpx": chemin_gpx,
        "nb_points_gpx": len(trace),
        "nb_troncons_detectes": len(segments),
        "releves": resultats,
    }


# ---------------------------------------------------------------------------
# GET /terrain/releves
# ---------------------------------------------------------------------------


@router.get(
    "/releves",
    summary="Liste les relevés terrain (filtres optionnels)",
    description=(
        "Renvoie l'historique des relevés terrain, du plus récent au plus ancien. "
        "Filtres : par tronçon, par fenêtre de dates."
    ),
)
async def lister_releves(
    troncon_id: int | None = Query(None, description="Filtrer sur un tronçon."),
    limite: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    requete = select(ReleveTerrain).order_by(
        ReleveTerrain.horodatage_passage.desc().nullslast(),
        ReleveTerrain.date_session.desc(),
    )
    if troncon_id is not None:
        requete = requete.where(ReleveTerrain.troncon_id == troncon_id)
    requete = requete.limit(limite)

    lignes = list(db.execute(requete).scalars())
    return {
        "nb_lignes": len(lignes),
        "lignes": [
            {
                "id": r.id,
                "troncon_id": r.troncon_id,
                "date_session": r.date_session.isoformat(),
                "horodatage_passage_utc": (
                    r.horodatage_passage.isoformat() if r.horodatage_passage else None
                ),
                "duree_mesuree_s": r.duree_mesuree_s,
                "duree_api_s": r.duree_api_s,
                "ecart_relatif": (
                    round(r.ecart_relatif, 4) if r.ecart_relatif is not None else None
                ),
                "confiance_matching": (
                    round(r.confiance_matching, 3)
                    if r.confiance_matching is not None else None
                ),
                # Nom de fichier court (sans chemin) pour permettre au frontend
                # de regrouper les relevés par GPX source et de demander le
                # téléchargement via /terrain/releves/{id}/gpx.
                "nom_fichier_gpx": (
                    Path(r.fichier_gpx).name if r.fichier_gpx else None
                ),
            }
            for r in lignes
        ],
    }


# ---------------------------------------------------------------------------
# GET /terrain/releves/{id}/gpx — sert le fichier GPX brut depuis disque
# ---------------------------------------------------------------------------


@router.get(
    "/releves/{releve_id}/gpx",
    summary="Télécharge le fichier GPX brut d'un relevé",
    description=(
        "Renvoie le `.gpx` exact uploadé par l'opérateur, tel qu'il est stocké "
        "sur le volume `GPX_STORAGE_DIR` du backend. Utilisé par la page "
        "Fiabilité pour rejouer la prévisualisation cartographique d'une "
        "session passée sans re-télécharger via l'utilisateur."
    ),
    response_class=FileResponse,
)
async def telecharger_gpx(
    releve_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    releve = db.get(ReleveTerrain, releve_id)
    if releve is None or not releve.fichier_gpx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relevé id={releve_id} introuvable ou sans fichier GPX.",
        )
    # Résolution du chemin : si stocké en chemin absolu, on vérifie qu'il
    # reste contenu dans le dossier de stockage (anti directory-traversal).
    racine = Path(get_settings().gpx_storage_dir).resolve()
    candidat = Path(releve.fichier_gpx)
    chemin = candidat if candidat.is_absolute() else racine / candidat.name
    try:
        chemin = chemin.resolve()
        chemin.relative_to(racine)
    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chemin GPX hors du dossier de stockage autorisé.",
        ) from exc
    if not chemin.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier GPX absent du disque : {chemin.name}",
        )
    return FileResponse(
        chemin,
        media_type="application/gpx+xml",
        filename=chemin.name,
    )


# ---------------------------------------------------------------------------
# GET /terrain/calibration
# ---------------------------------------------------------------------------


@router.get(
    "/calibration",
    summary="Facteur de calibration par tronçon (moyenne mobile des écarts)",
    description=(
        "Pour chaque tronçon actif, calcule la moyenne des `ecart_relatif` "
        "des N derniers relevés (paramètre `fenetre`, défaut 4). Sert à "
        "détecter une dérive systématique des sources API par rapport à la "
        "réalité terrain."
    ),
)
async def lister_calibration(
    fenetre: int = Query(
        4, ge=1, le=52,
        description="Nombre de derniers relevés à moyenner (défaut 4 ≈ 1 mois).",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    calib = calibration_par_troncon(db, fenetre=fenetre)
    return {
        "fenetre_relevees": fenetre,
        "troncons": [
            {
                "troncon_id": c.troncon_id,
                "troncon_nom": c.troncon_nom,
                "nb_releves": c.nb_releves,
                "ecart_moyen": round(c.ecart_moyen, 4) if c.ecart_moyen is not None else None,
                "ecart_courant": round(c.ecart_courant, 4) if c.ecart_courant is not None else None,
            }
            for c in calib
        ],
    }
