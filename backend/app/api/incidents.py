"""Router FastAPI pour les incidents de circulation (P8).

Endpoints :
  GET  /incidents               — liste paginée avec filtres
  GET  /incidents/stats         — KPI globaux (compteurs + dernière collecte)
  GET  /incidents/export        — export CSV (P8.5)
  GET  /incidents/{id}          — détail d'un incident
  POST /incidents/scraper-now   — déclenchement manuel du scraping RSS
  POST /incidents/enrichir      — déclenchement manuel NLP + géocodage (P8.2)

Tag Swagger : "incidents"
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyse.incidents_nlp import enrichir_incidents
from app.core.config import get_settings
from app.db.session import get_db, SessionLocal
from app.models.models import Incident, Troncon, TypeIncident, SeveriteIncident
from app.sources.parsers.rss_parser import scraper_toutes_sources


router = APIRouter(prefix="/incidents", tags=["incidents"])


# ---------------------------------------------------------------------------
# Schémas Pydantic de sortie
# ---------------------------------------------------------------------------


class IncidentOut(BaseModel):
    """Représentation publique d'un incident scrapé."""

    id: int
    titre: str
    resume: str | None
    source_url: str
    source_nom: str
    horodatage_publication: datetime
    horodatage_collecte: datetime
    lat: float | None
    lon: float | None
    lieu_extrait: str | None
    troncon_id: int | None
    type_incident: str | None
    severite: str | None
    actif: bool
    verifie: bool
    fiabilite_source: float | None

    model_config = {"from_attributes": True}


class IncidentsPage(BaseModel):
    """Réponse paginée pour GET /incidents."""

    total: int
    items: list[IncidentOut]


class StatsIncidents(BaseModel):
    """Statistiques globales renvoyées par GET /incidents/stats."""

    nb_total: int
    nb_actifs: int
    nb_par_type: dict[str, int]
    nb_par_source: dict[str, int]
    derniere_collecte: datetime | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _incident_to_out(inc: Incident) -> IncidentOut:
    """Convertit un modèle SQLAlchemy `Incident` vers le schéma de sortie."""
    return IncidentOut(
        id=inc.id,
        titre=inc.titre,
        resume=inc.resume,
        source_url=inc.source_url,
        source_nom=inc.source_nom,
        horodatage_publication=inc.horodatage_publication,
        horodatage_collecte=inc.horodatage_collecte,
        lat=inc.lat,
        lon=inc.lon,
        lieu_extrait=inc.lieu_extrait,
        troncon_id=inc.troncon_id,
        type_incident=inc.type_incident.value if inc.type_incident else None,
        severite=inc.severite.value if inc.severite else None,
        actif=inc.actif,
        verifie=inc.verifie,
        fiabilite_source=inc.fiabilite_source,
    )


# ---------------------------------------------------------------------------
# GET /incidents/stats  — doit être avant GET /incidents/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    summary="Statistiques globales des incidents scrapés",
    description=(
        "Retourne le nombre total d'incidents, le nombre d'actifs (<6h), "
        "les compteurs par type et par source, et l'horodatage de la dernière "
        "collecte RSS."
    ),
    response_model=StatsIncidents,
)
def get_stats(db: Session = Depends(get_db)) -> StatsIncidents:
    """KPI globaux : compteurs, types, sources, dernière collecte."""
    nb_total: int = db.scalar(select(func.count(Incident.id))) or 0

    maintenant = datetime.now(tz=timezone.utc)

    # Incidents actifs : publication < 6 h
    tous = db.execute(
        select(
            Incident.horodatage_publication,
            Incident.type_incident,
            Incident.source_nom,
            Incident.horodatage_collecte,
        )
    ).all()

    nb_actifs = 0
    nb_par_type: dict[str, int] = {}
    nb_par_source: dict[str, int] = {}
    derniere_collecte: datetime | None = None

    for pub, type_inc, source, collecte in tous:
        # Normalisation UTC
        pub_utc = pub.replace(tzinfo=timezone.utc) if pub.tzinfo is None else pub
        if (maintenant - pub_utc).total_seconds() < 6 * 3600:
            nb_actifs += 1

        cle_type = type_inc.value if type_inc else "inconnu"
        nb_par_type[cle_type] = nb_par_type.get(cle_type, 0) + 1
        nb_par_source[source] = nb_par_source.get(source, 0) + 1

        if collecte and (derniere_collecte is None or collecte > derniere_collecte):
            derniere_collecte = collecte

    return StatsIncidents(
        nb_total=nb_total,
        nb_actifs=nb_actifs,
        nb_par_type=nb_par_type,
        nb_par_source=nb_par_source,
        derniere_collecte=derniere_collecte,
    )


# ---------------------------------------------------------------------------
# GET /incidents
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="Liste paginée des incidents de circulation",
    description=(
        "Retourne les incidents scrapés depuis la presse ivoirienne, "
        "filtrés optionnellement par statut actif, tronçon impacté et type. "
        "Triés du plus récent au plus ancien."
    ),
    response_model=IncidentsPage,
)
def lister_incidents(
    actif_seulement: bool = Query(False, description="Si True, retourne uniquement les incidents < 6 h"),
    troncon_id: int | None = Query(None, description="Filtre sur le tronçon impacté"),
    type_incident: str | None = Query(None, description="Filtre sur le type (accident, embouteillage, …)"),
    limit: int = Query(50, ge=1, le=200, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    db: Session = Depends(get_db),
) -> IncidentsPage:
    """Liste et filtre les incidents."""
    q = select(Incident).order_by(Incident.horodatage_publication.desc())

    if troncon_id is not None:
        q = q.where(Incident.troncon_id == troncon_id)

    if type_incident:
        try:
            t = TypeIncident(type_incident)
            q = q.where(Incident.type_incident == t)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type inconnu : {type_incident!r}. "
                       "Valeurs acceptées : accident, embouteillage, route_barree, travaux, autre",
            )

    tous: list[Incident] = list(db.execute(q).scalars())

    # Filtre actif en Python (propriété calculée, pas requêtable en SQL)
    if actif_seulement:
        tous = [i for i in tous if i.actif]

    total = len(tous)
    items = [_incident_to_out(i) for i in tous[offset: offset + limit]]

    return IncidentsPage(total=total, items=items)


# ---------------------------------------------------------------------------
# GET /incidents/export  — export CSV (P8.5)
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export CSV des incidents",
    description=(
        "Retourne un fichier CSV téléchargeable contenant les incidents "
        "sur la période choisie (1j / 7j / 30j). "
        "Filtres optionnels : type_incident, troncon_id."
    ),
)
def exporter_incidents_csv(
    periode: str = Query("7j", description="Fenêtre temporelle : 1j, 7j ou 30j"),
    troncon_id: int | None = Query(None),
    type_incident: str | None = Query(None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Génère un CSV des incidents pour la période demandée."""
    # Calcul du début de la fenêtre temporelle
    maintenant = datetime.now(tz=timezone.utc)
    _DUREE = {"1j": 1, "7j": 7, "30j": 30}
    nb_jours = _DUREE.get(periode, 7)
    debut = maintenant - timedelta(days=nb_jours)

    # Requête principale
    q = (
        select(Incident)
        .where(Incident.horodatage_publication >= debut)
        .order_by(Incident.horodatage_publication.desc())
    )
    if troncon_id is not None:
        q = q.where(Incident.troncon_id == troncon_id)
    if type_incident:
        try:
            q = q.where(Incident.type_incident == TypeIncident(type_incident))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type inconnu : {type_incident!r}",
            )

    incidents: list[Incident] = list(db.execute(q).scalars())

    # Index des noms de tronçons (évite N+1 queries)
    troncon_ids = {inc.troncon_id for inc in incidents if inc.troncon_id}
    noms_troncons: dict[int, str] = {}
    if troncon_ids:
        for tr in db.execute(
            select(Troncon).where(Troncon.id.in_(troncon_ids))
        ).scalars():
            noms_troncons[tr.id] = tr.nom

    # Construction du CSV en mémoire
    sortie = io.StringIO()
    writer = csv.writer(sortie, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "id", "titre", "source_nom", "type_incident", "severite",
        "lieu_extrait", "lat", "lon", "troncon_nom",
        "horodatage_publication", "actif", "fiabilite_source",
    ])
    for inc in incidents:
        pub = inc.horodatage_publication
        pub_utc = pub.replace(tzinfo=timezone.utc) if pub.tzinfo is None else pub
        actif_val = (maintenant - pub_utc).total_seconds() < 6 * 3600
        writer.writerow([
            inc.id,
            inc.titre,
            inc.source_nom,
            inc.type_incident.value if inc.type_incident else "",
            inc.severite.value if inc.severite else "",
            inc.lieu_extrait or "",
            inc.lat if inc.lat is not None else "",
            inc.lon if inc.lon is not None else "",
            noms_troncons.get(inc.troncon_id, "") if inc.troncon_id else "",
            pub_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "oui" if actif_val else "non",
            round(inc.fiabilite_source, 2) if inc.fiabilite_source is not None else "",
        ])

    contenu = sortie.getvalue()
    nom_fichier = f"incidents_paa_{maintenant.strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([contenu]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


# ---------------------------------------------------------------------------
# GET /incidents/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{incident_id}",
    summary="Détail d'un incident",
    response_model=IncidentOut,
)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
) -> IncidentOut:
    """Retourne l'incident correspondant à l'id fourni."""
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} introuvable.",
        )
    return _incident_to_out(inc)


# ---------------------------------------------------------------------------
# POST /incidents/scraper-now  — déclenchement manuel du scraping RSS
# ---------------------------------------------------------------------------


@router.post(
    "/scraper-now",
    summary="Déclenche le scraping RSS des incidents manuellement",
    description=(
        "Lance immédiatement un cycle de scraping RSS (toutes les sources). "
        "Endpoint sécurisé par le header `X-API-Key`. "
        "L'exécution est asynchrone — la réponse est immédiate."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def scraper_maintenant(
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Déclenche un cycle de scraping en tâche de fond."""
    settings = get_settings()
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé API invalide ou absente.",
        )

    async def _scraper():
        nb = await scraper_toutes_sources(db)
        nb_enrichis = await enrichir_incidents(db)
        db.close()

    background_tasks.add_task(_scraper)
    return {"message": "Scraping RSS lancé en arrière-plan."}


# ---------------------------------------------------------------------------
# POST /incidents/enrichir  — enrichissement NLP + géocodage (P8.2)
# ---------------------------------------------------------------------------


@router.post(
    "/enrichir",
    summary="Déclenche l'enrichissement NLP et le géocodage des incidents",
    description=(
        "Parcourt les incidents dont `type_incident` est NULL, applique "
        "l'extraction de lieu par regex, la classification type/sévérité et "
        "le géocodage Nominatim. Exécution en tâche de fond. "
        "Sécurisé par le header `X-API-Key`."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrichir_maintenant(
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
) -> dict[str, str]:
    """Déclenche l'enrichissement NLP en tâche de fond."""
    settings = get_settings()
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé API invalide ou absente.",
        )

    async def _enrichir():
        session = SessionLocal()
        try:
            nb = await enrichir_incidents(session)
        except Exception:
            import logging
            logging.getLogger("paa.incidents.nlp").exception(
                "Erreur lors de l'enrichissement manuel."
            )
        finally:
            session.close()

    background_tasks.add_task(_enrichir)
    return {"message": "Enrichissement NLP lancé en arrière-plan."}
