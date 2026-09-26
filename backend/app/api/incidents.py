"""Router FastAPI pour les incidents de circulation (P8).

Endpoints :
  GET    /incidents             — liste paginée avec filtres
  GET    /incidents/stats       — KPI globaux (compteurs + dernière collecte)
  GET    /incidents/export      — export CSV (P8.5)
  GET    /incidents/{id}        — détail d'un incident
  POST   /incidents             — création manuelle (constat terrain)
  PATCH  /incidents/{id}        — correction d'un incident
  DELETE /incidents/{id}        — suppression définitive
  POST   /incidents/scraper-now — déclenchement manuel scraping RSS + HTML
  POST   /incidents/enrichir    — déclenchement manuel NLP + géocodage (P8.2)

Tag Swagger : "incidents"
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyse.incidents_nlp import enrichir_incidents
from app.core.config import get_settings
from app.db.session import get_db, SessionLocal
from app.models.models import Incident, SourceIncident, Troncon, TypeIncident, SeveriteIncident, TypesIncident
from app.sources.parsers.rss_parser import scraper_toutes_sources


# Logger dédié — visible dans Railway sous le tag "paa.incidents"
logger = logging.getLogger("paa.incidents")

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


def _enum_value(field: Any) -> str | None:
    """Retourne la valeur d'un enum SQLAlchemy en tolérant les chaînes brutes.

    Certaines lignes anciennes en base ont `type_incident` ou `severite`
    stockés comme str (pas converti en Enum à la lecture). Sans ce garde
    `.value` lève AttributeError et casse tout l'endpoint /incidents.
    """
    if field is None:
        return None
    return field.value if hasattr(field, "value") else str(field)


def _incident_to_out(inc: Incident) -> IncidentOut:
    """Convertit un modèle SQLAlchemy `Incident` vers le schéma de sortie.

    En cas de champ corrompu en base (cas observé en prod), log explicite
    de l'id + nom de champ + valeur brute, puis remontée vers l'appelant
    qui la transforme en HTTP 500 enrichi.
    """
    try:
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
            type_incident=_enum_value(inc.type_incident),
            severite=_enum_value(inc.severite),
            actif=inc.actif,
            verifie=inc.verifie,
            fiabilite_source=inc.fiabilite_source,
        )
    except Exception:
        logger.exception(
            "Echec serialisation incident id=%s "
            "(source_nom=%r type_incident=%r severite=%r) — voir traceback ci-dessus.",
            inc.id, inc.source_nom, inc.type_incident, inc.severite,
        )
        raise


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

    # Incidents actifs : publication < seuil configurable (défaut 30 j)
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
        if (maintenant - pub_utc).total_seconds() < get_settings().incident_actif_heures * 3600:
            nb_actifs += 1

        cle_type = _enum_value(type_inc) or "inconnu"
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
    actif_seulement: bool = Query(False, description="Si True, retourne uniquement les incidents récents (seuil configurable, défaut 30 j)"),
    troncon_id: int | None = Query(None, description="Filtre sur le tronçon impacté"),
    type_incident: str | None = Query(None, description="Filtre sur le type (accident, embouteillage, …)"),
    limit: int = Query(50, ge=1, le=200, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    db: Session = Depends(get_db),
) -> IncidentsPage:
    """Liste et filtre les incidents."""
    logger.info(
        "GET /incidents — actif_seulement=%s troncon_id=%s type_incident=%r limit=%d offset=%d",
        actif_seulement, troncon_id, type_incident, limit, offset,
    )

    q = select(Incident).order_by(Incident.horodatage_publication.desc())

    if troncon_id is not None:
        q = q.where(Incident.troncon_id == troncon_id)

    if type_incident:
        # type_incident est maintenant une VARCHAR libre — filtre direct sur la chaîne
        q = q.where(Incident.type_incident == type_incident)

    try:
        tous: list[Incident] = list(db.execute(q).scalars())
    except Exception:
        logger.exception("Echec SQL lors de la lecture des incidents.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur SQL lors de la lecture des incidents — voir les logs serveur.",
        )

    # Filtre actif en Python (propriété calculée, pas requêtable en SQL)
    if actif_seulement:
        tous = [i for i in tous if i.actif]

    total = len(tous)

    # Sérialisation incident-par-incident : isole l'erreur sur 1 ligne corrompue
    # plutôt que de planter toute la liste (cas observé en prod le 2026-06-29).
    items: list[IncidentOut] = []
    nb_skip = 0
    for i in tous[offset: offset + limit]:
        try:
            items.append(_incident_to_out(i))
        except Exception:
            nb_skip += 1
            logger.exception(
                "Incident id=%s ignore — donnees corrompues, voir traceback. "
                "type_incident=%r severite=%r source_nom=%r",
                i.id, i.type_incident, i.severite, i.source_nom,
            )

    if nb_skip:
        logger.warning(
            "GET /incidents : %d incident(s) ignore(s) sur %d a cause de donnees corrompues.",
            nb_skip, total,
        )

    logger.info(
        "GET /incidents OK — total=%d retourne=%d ignore=%d",
        total, len(items), nb_skip,
    )
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
        q = q.where(Incident.type_incident == type_incident)

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
        actif_val = (maintenant - pub_utc).total_seconds() < get_settings().incident_actif_heures * 3600
        writer.writerow([
            inc.id,
            inc.titre,
            inc.source_nom,
            _enum_value(inc.type_incident) or "",
            _enum_value(inc.severite) or "",
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

    from app.sources.parsers.html_parser import scraper_toutes_sources_html

    async def _scraper():
        nb_rss = await scraper_toutes_sources(db)
        nb_html = await scraper_toutes_sources_html(db)
        nb_enrichis = await enrichir_incidents(db)
        db.close()
        logger.info(
            "Scraping manuel : %d RSS + %d HTML → %d enrichis.",
            nb_rss, nb_html, nb_enrichis,
        )

    background_tasks.add_task(_scraper)
    return {"message": "Scraping RSS + HTML lancé en arrière-plan."}


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


# ---------------------------------------------------------------------------
# GESTION DES SOURCES DE SCRAPING — migration 0014
# ---------------------------------------------------------------------------


class SourceIn(BaseModel):
    """Payload de création / mise à jour d'une source de scraping."""
    nom: str = Field(..., min_length=2, max_length=80,
                     description="Identifiant court unique (slug). Ex: 'fraternite_matin'.")
    libelle: str = Field(..., min_length=2, max_length=200,
                         description="Nom affiché à l'utilisateur.")
    url: str = Field(..., min_length=5, max_length=500,
                     description="URL du flux RSS ou de la page HTML.")
    type: str = Field("rss", pattern="^(rss|html)$")
    actif: bool = True
    fiabilite: float = Field(0.7, ge=0.0, le=1.0)


class SourceOut(SourceIn):
    id: int
    ajoute_le: datetime


@router.get(
    "/sources",
    summary="Liste les sources de scraping configurées",
    response_model=list[SourceOut],
)
def lister_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    sources = db.execute(
        select(SourceIncident).order_by(SourceIncident.id)
    ).scalars().all()
    return [
        SourceOut(
            id=s.id, nom=s.nom, libelle=s.libelle, url=s.url, type=s.type,
            actif=s.actif, fiabilite=s.fiabilite, ajoute_le=s.ajoute_le,
        )
        for s in sources
    ]


@router.post(
    "/sources",
    summary="Ajouter une nouvelle source de scraping",
    description=(
        "La source devient active au prochain cycle de collecte d'incidents "
        "(toutes les 30 min). Le scraper RSS supporte la plupart des flux "
        "standard. Le type HTML est réservé aux sources sans flux RSS."
    ),
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def creer_source(payload: SourceIn, db: Session = Depends(get_db)) -> SourceOut:
    existant = db.execute(
        select(SourceIncident).where(SourceIncident.nom == payload.nom)
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(409, f"Une source nommée {payload.nom!r} existe déjà.")
    s = SourceIncident(
        nom=payload.nom, libelle=payload.libelle, url=payload.url,
        type=payload.type, actif=payload.actif, fiabilite=payload.fiabilite,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return SourceOut(
        id=s.id, nom=s.nom, libelle=s.libelle, url=s.url, type=s.type,
        actif=s.actif, fiabilite=s.fiabilite, ajoute_le=s.ajoute_le,
    )


class SourcePatch(BaseModel):
    """Payload partiel pour PATCH — tous les champs optionnels."""
    nom: str | None = None
    libelle: str | None = None
    url: str | None = None
    type: str | None = None
    actif: bool | None = None
    fiabilite: float | None = Field(None, ge=0.0, le=1.0)


@router.patch(
    "/sources/{source_id}",
    summary="Modifier une source (notamment activer/désactiver)",
    response_model=SourceOut,
)
def modifier_source(source_id: int, payload: SourcePatch,
                    db: Session = Depends(get_db)) -> SourceOut:
    s = db.get(SourceIncident, source_id)
    if s is None:
        raise HTTPException(404, f"Source id={source_id} introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(s, champ, valeur)
    db.commit()
    db.refresh(s)
    return SourceOut(
        id=s.id, nom=s.nom, libelle=s.libelle, url=s.url, type=s.type,
        actif=s.actif, fiabilite=s.fiabilite, ajoute_le=s.ajoute_le,
    )


@router.delete(
    "/sources/{source_id}",
    summary="Supprimer définitivement une source de scraping",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_source(source_id: int, db: Session = Depends(get_db)) -> Response:
    s = db.get(SourceIncident, source_id)
    if s is None:
        raise HTTPException(404, f"Source id={source_id} introuvable.")
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# GESTION DES TYPES D'INCIDENTS — migration 0015
# ---------------------------------------------------------------------------


class TypeIncidentIn(BaseModel):
    """Payload de création d'un type d'incident."""
    slug: str = Field(..., min_length=2, max_length=50,
                      description="Identifiant interne unique. Ex : 'incendie'.")
    libelle: str = Field(..., min_length=2, max_length=200,
                         description="Libellé affiché. Ex : 'Incendie / explosion'.")
    regex: str = Field(..., min_length=1,
                       description="Expression régulière Python de détection (insensible à la casse).")
    actif: bool = True


class TypeIncidentOut(TypeIncidentIn):
    id: int
    cree_le: datetime

    model_config = {"from_attributes": True}


class TypeIncidentPatch(BaseModel):
    """Payload partiel pour PATCH."""
    libelle: str | None = None
    regex: str | None = None
    actif: bool | None = None


@router.get(
    "/types",
    summary="Liste les types d'incidents configurés",
    description=(
        "Retourne tous les types d'incidents actifs (et inactifs) "
        "configurés dans la table types_incidents. "
        "La liste est utilisée par le classificateur NLP et les filtres UI."
    ),
    response_model=list[TypeIncidentOut],
)
def lister_types(db: Session = Depends(get_db)) -> list[TypeIncidentOut]:
    types = db.execute(
        select(TypesIncident).order_by(TypesIncident.id)
    ).scalars().all()
    return [TypeIncidentOut.model_validate(t) for t in types]


@router.post(
    "/types",
    summary="Ajouter un nouveau type d'incident",
    description=(
        "Crée un nouveau type d'incident avec sa regex de détection. "
        "Le classificateur NLP l'utilisera au prochain cycle d'enrichissement."
    ),
    response_model=TypeIncidentOut,
    status_code=status.HTTP_201_CREATED,
)
def creer_type(payload: TypeIncidentIn, db: Session = Depends(get_db)) -> TypeIncidentOut:
    existant = db.execute(
        select(TypesIncident).where(TypesIncident.slug == payload.slug)
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(409, f"Un type nommé {payload.slug!r} existe déjà.")
    # Valider la regex avant insertion
    try:
        import re as _re
        _re.compile(payload.regex)
    except _re.error as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Regex invalide : {exc}",
        )
    t = TypesIncident(
        slug=payload.slug, libelle=payload.libelle,
        regex=payload.regex, actif=payload.actif,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return TypeIncidentOut.model_validate(t)


@router.patch(
    "/types/{type_id}",
    summary="Modifier un type d'incident (libellé, regex, actif)",
    response_model=TypeIncidentOut,
)
def modifier_type(type_id: int, payload: TypeIncidentPatch,
                  db: Session = Depends(get_db)) -> TypeIncidentOut:
    t = db.get(TypesIncident, type_id)
    if t is None:
        raise HTTPException(404, f"Type id={type_id} introuvable.")
    if payload.regex is not None:
        try:
            import re as _re
            _re.compile(payload.regex)
        except _re.error as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Regex invalide : {exc}",
            )
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(t, champ, valeur)
    db.commit()
    db.refresh(t)
    return TypeIncidentOut.model_validate(t)


@router.delete(
    "/types/{type_id}",
    summary="Supprimer un type d'incident",
    description=(
        "Supprime le type définitivement. Les incidents déjà classifiés "
        "avec ce slug conservent leur valeur — seul le futur enrichissement "
        "est affecté. Le type 'autre' ne peut pas être supprimé."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_type(type_id: int, db: Session = Depends(get_db)) -> Response:
    t = db.get(TypesIncident, type_id)
    if t is None:
        raise HTTPException(404, f"Type id={type_id} introuvable.")
    if t.slug == "autre":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le type 'autre' est le fallback par défaut — il ne peut pas être supprimé.",
        )
    db.delete(t)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# GET /incidents/{id}  — déclaré APRÈS /sources et /types pour éviter que
# FastAPI matche ces routes statiques sur /{incident_id:int} (422 int_parsing).
# ---------------------------------------------------------------------------


@router.get(
    "/{incident_id:int}",
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
# CRUD manuel des incidents
#
# Le scraping alimente la table automatiquement, mais un opérateur du port
# doit pouvoir saisir un incident constaté sur le terrain (avant toute reprise
# par la presse), corriger une classification erronée ou retirer un article
# hors sujet que les filtres ont laissé passer.
# ---------------------------------------------------------------------------


class IncidentCreation(BaseModel):
    """Incident saisi manuellement depuis l'interface."""

    titre: str = Field(..., min_length=3, max_length=500)
    resume: str | None = Field(None, max_length=5000)
    source_url: str | None = Field(
        None,
        max_length=2000,
        description=(
            "Lien vers l'article d'origine. Laissé vide pour un constat terrain : "
            "une référence interne unique est alors générée."
        ),
    )
    source_nom: str = Field("saisie_manuelle", max_length=50)
    horodatage_publication: datetime | None = Field(
        None, description="Date de l'incident (UTC). Par défaut : maintenant."
    )
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    lieu_extrait: str | None = Field(None, max_length=200)
    troncon_id: int | None = None
    type_incident: str | None = Field(None, max_length=50)
    severite: str | None = Field(None, description="mineur | moyen | grave | inconnu")
    verifie: bool = False


class IncidentModification(BaseModel):
    """Champs modifiables d'un incident — tous optionnels (PATCH partiel)."""

    titre: str | None = Field(None, min_length=3, max_length=500)
    resume: str | None = Field(None, max_length=5000)
    source_url: str | None = Field(None, max_length=2000)
    source_nom: str | None = Field(None, max_length=50)
    horodatage_publication: datetime | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    lieu_extrait: str | None = Field(None, max_length=200)
    troncon_id: int | None = None
    type_incident: str | None = Field(None, max_length=50)
    severite: str | None = None
    verifie: bool | None = None
    fiabilite_source: float | None = Field(None, ge=0, le=1)


_SEVERITES_VALIDES = {"mineur", "moyen", "grave", "inconnu"}


def _valider_severite(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    if valeur not in _SEVERITES_VALIDES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Sévérité invalide. Valeurs acceptées : "
                + ", ".join(sorted(_SEVERITES_VALIDES))
            ),
        )
    return valeur


def _valider_type(valeur: str | None, db: Session) -> str | None:
    """Vérifie que le slug existe dans la table des types configurables."""
    if valeur is None:
        return None
    existe = db.execute(
        select(TypesIncident.slug).where(TypesIncident.slug == valeur)
    ).scalar_one_or_none()
    if existe is None:
        connus = db.execute(select(TypesIncident.slug)).scalars().all()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Type d'incident inconnu : {valeur!r}. "
                f"Types disponibles : {', '.join(sorted(connus)) or 'aucun'}."
            ),
        )
    return valeur


def _valider_troncon(troncon_id: int | None, db: Session) -> int | None:
    if troncon_id is None:
        return None
    if db.get(Troncon, troncon_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tronçon {troncon_id} introuvable.",
        )
    return troncon_id


@router.post(
    "",
    summary="Créer un incident manuellement",
    description=(
        "Enregistre un incident constaté sur le terrain ou signalé hors presse. "
        "Sans URL source, une référence interne unique est générée pour "
        "respecter la contrainte d'unicité qui sert à la déduplication du "
        "scraping."
    ),
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
)
def creer_incident(
    payload: IncidentCreation,
    db: Session = Depends(get_db),
) -> IncidentOut:
    maintenant = datetime.now(timezone.utc)
    source_url = (payload.source_url or "").strip()
    if not source_url:
        # Référence interne : unique et reconnaissable dans les exports.
        source_url = f"interne://fluidis/incident/{maintenant.timestamp():.6f}"

    doublon = db.execute(
        select(Incident).where(Incident.source_url == source_url)
    ).scalar_one_or_none()
    if doublon is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Un incident portant cette URL source existe déjà "
                f"(id={doublon.id})."
            ),
        )

    incident = Incident(
        titre=payload.titre.strip(),
        resume=(payload.resume or "").strip() or None,
        source_url=source_url,
        source_nom=payload.source_nom.strip() or "saisie_manuelle",
        horodatage_publication=payload.horodatage_publication or maintenant,
        horodatage_collecte=maintenant,
        lat=payload.lat,
        lon=payload.lon,
        lieu_extrait=payload.lieu_extrait,
        troncon_id=_valider_troncon(payload.troncon_id, db),
        type_incident=_valider_type(payload.type_incident, db),
        severite=_valider_severite(payload.severite),
        verifie=payload.verifie,
        # Une saisie humaine est considérée comme fiable : elle provient d'un
        # agent du port, pas d'un article filtré automatiquement.
        fiabilite_source=1.0,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    logger.info("Incident créé manuellement id=%s titre=%r", incident.id, incident.titre)
    return _incident_to_out(incident)


@router.patch(
    "/{incident_id:int}",
    summary="Modifier un incident",
    description=(
        "Met à jour les champs fournis. Sert notamment à corriger une "
        "classification automatique erronée (type, sévérité, tronçon rattaché) "
        "ou à marquer un incident comme vérifié."
    ),
    response_model=IncidentOut,
)
def modifier_incident(
    incident_id: int,
    payload: IncidentModification,
    db: Session = Depends(get_db),
) -> IncidentOut:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} introuvable.",
        )

    champs = payload.model_dump(exclude_unset=True)
    if "type_incident" in champs:
        champs["type_incident"] = _valider_type(champs["type_incident"], db)
    if "severite" in champs:
        champs["severite"] = _valider_severite(champs["severite"])
    if "troncon_id" in champs:
        champs["troncon_id"] = _valider_troncon(champs["troncon_id"], db)
    if "source_url" in champs and champs["source_url"]:
        conflit = db.execute(
            select(Incident).where(
                Incident.source_url == champs["source_url"],
                Incident.id != incident_id,
            )
        ).scalar_one_or_none()
        if conflit is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cette URL source est déjà utilisée par l'incident {conflit.id}.",
            )

    for nom, valeur in champs.items():
        setattr(incident, nom, valeur)
    db.commit()
    db.refresh(incident)
    logger.info("Incident %s modifié — champs=%s", incident_id, sorted(champs))
    return _incident_to_out(incident)


@router.delete(
    "/{incident_id:int}",
    summary="Supprimer un incident",
    description=(
        "Suppression définitive. Contrairement aux tronçons, dont l'historique "
        "de mesures impose une suppression logique, un incident est une "
        "référence bibliographique sans donnée dépendante : le retirer ne crée "
        "aucun trou dans les séries."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_incident(
    incident_id: int,
    db: Session = Depends(get_db),
) -> Response:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} introuvable.",
        )
    titre = incident.titre
    db.delete(incident)
    db.commit()
    logger.info("Incident %s supprimé — titre=%r", incident_id, titre)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
