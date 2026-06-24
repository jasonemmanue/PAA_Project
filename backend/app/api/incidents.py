"""Router FastAPI pour les incidents de circulation (P8).

Endpoints :
  GET  /incidents               — liste paginée avec filtres
  GET  /incidents/stats         — KPI globaux (compteurs + dernière collecte)
  GET  /incidents/{id}          — détail d'un incident
  POST /incidents/scraper-now   — déclenchement manuel du scraping RSS

Tag Swagger : "incidents"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Incident, TypeIncident, SeveriteIncident
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
        db.close()

    background_tasks.add_task(_scraper)
    return {"message": "Scraping RSS lancé en arrière-plan."}
