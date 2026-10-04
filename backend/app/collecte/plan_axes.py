"""Plan de collecte Google : un appel par axe (CLAUDE.md § 39).

Avant le 2026-10-04, chaque couple (tronçon codifié, sens) donnait un appel
Google — 27 appels par cycle, soit 648 requêtes/jour, au-dessus du plafond
gratuit. Désormais un axe découpé en tronçons est mesuré par **une seule**
requête dont les étapes intermédiaires sont les bornes de ses tronçons :
Google renvoie un *leg* par portion, avec sa durée sous trafic et ses
couleurs. Chaque leg correspondant à un tronçon devient une mesure de ce
tronçon pour cet axe — sans perte de granularité ni de fréquence.

Construction de la chaîne d'un axe :
  - tronçons triés selon `axe_sous_troncons.ordre` (ordre DEESP par axe) ;
  - sens de chaque tronçon déduit par continuité du tracé
    (`sens_par_continuite`) ;
  - si la sortie d'un tronçon et l'entrée du suivant sont à moins de
    `TOLERANCE_JONCTION_M`, elles fusionnent en un seul point ; sinon le leg
    qui les relie est un « raccord » non mesuré (sa valeur est ignorée).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import SousTroncon, Troncon, axe_sous_troncons
from app.sources.coordonnees import PointGPS
from app.sources.google_routes import NB_ETAPES_INTERMEDIAIRES_MAX
from app.sources.polyline import calculer_sens_par_axe, distance_haversine_m

# Écart maximal entre la fin d'un tronçon et le début du suivant pour
# considérer qu'ils se touchent (bornes relevées par GPX, cf. § 21).
TOLERANCE_JONCTION_M = 50

# Nombre maximal de points d'une requête : origine + destination + étapes.
_NB_POINTS_MAX = NB_ETAPES_INTERMEDIAIRES_MAX + 2


@dataclass
class AppelChaine:
    """Une requête Google : `points` consécutifs, `legs[i]` = id du tronçon
    mesuré par la portion `points[i] → points[i+1]` (None = raccord)."""
    points: list[PointGPS]
    legs: list[int | None]


@dataclass
class PlanAxe:
    """Requêtes nécessaires pour mesurer tous les tronçons d'un axe."""
    axe_id: int
    appels: list[AppelChaine] = field(default_factory=list)
    sous_troncon_ids: list[int] = field(default_factory=list)


@dataclass
class PlanCollecte:
    """Plan complet d'un cycle."""
    axes_sans_troncon: list[Troncon]
    plans_axes: list[PlanAxe]

    @property
    def nb_appels(self) -> int:
        return len(self.axes_sans_troncon) + sum(len(p.appels) for p in self.plans_axes)

    @property
    def nb_resultats(self) -> int:
        return len(self.axes_sans_troncon) + sum(
            len(p.sous_troncon_ids) for p in self.plans_axes
        )


def sens_par_continuite(axe: Troncon, sous_ordonnes: list[SousTroncon]) -> dict[int, str]:
    """Sens de parcours de chaque tronçon d'un axe, par continuité du tracé.

    Le premier tronçon est orienté depuis l'origine de l'axe ; chaque suivant
    entre par l'extrémité la plus proche de la sortie du précédent.

    Plus fiable que `calculer_sens_par_axe` (distance à l'origine de l'axe)
    pour les tronçons courts presque perpendiculaires à l'axe : T1B
    (Toyota CFAO → Seamen's) ressortait « direct » sur l'axe retour
    Palm Beach → Toyota, alors qu'il y est parcouru de Seamen's vers Toyota.
    """
    sens: dict[int, str] = {}
    position = (axe.lat_origine, axe.lon_origine)
    for sous in sous_ordonnes:
        if position[0] is None or position[1] is None:
            sens[sous.id] = calculer_sens_par_axe(
                axe.lat_origine, axe.lon_origine,
                sous.lat_debut, sous.lon_debut, sous.lat_fin, sous.lon_fin,
            )
        else:
            d_debut = distance_haversine_m(position[0], position[1], sous.lat_debut, sous.lon_debut)
            d_fin = distance_haversine_m(position[0], position[1], sous.lat_fin, sous.lon_fin)
            sens[sous.id] = "direct" if d_debut <= d_fin else "inverse"
        position = (
            (sous.lat_fin, sous.lon_fin) if sens[sous.id] == "direct"
            else (sous.lat_debut, sous.lon_debut)
        )
    return sens


def _chaine_axe(axe: Troncon, sous_ordonnes: list[SousTroncon]) -> AppelChaine:
    """Chaîne de points complète d'un axe (avant découpage éventuel)."""
    points: list[PointGPS] = []
    legs: list[int | None] = []
    sens = sens_par_continuite(axe, sous_ordonnes)
    for sous in sous_ordonnes:
        debut = PointGPS(sous.lat_debut, sous.lon_debut)
        fin = PointGPS(sous.lat_fin, sous.lon_fin)
        entree, sortie = (fin, debut) if sens[sous.id] == "inverse" else (debut, fin)
        if not points:
            points.append(entree)
        elif distance_haversine_m(
            points[-1].lat, points[-1].lon, entree.lat, entree.lon,
        ) > TOLERANCE_JONCTION_M:
            # Les deux tronçons ne se touchent pas : on insère un raccord
            # dont la mesure ne sera attribuée à aucun tronçon.
            points.append(entree)
            legs.append(None)
        points.append(sortie)
        legs.append(sous.id)
    return AppelChaine(points=points, legs=legs)


def _decouper(chaine: AppelChaine) -> list[AppelChaine]:
    """Découpe une chaîne trop longue pour une seule requête Google."""
    if len(chaine.points) <= _NB_POINTS_MAX:
        return [chaine]
    morceaux: list[AppelChaine] = []
    debut = 0
    nb_legs_max = _NB_POINTS_MAX - 1
    while debut < len(chaine.legs):
        fin = min(debut + nb_legs_max, len(chaine.legs))
        morceaux.append(AppelChaine(
            points=chaine.points[debut:fin + 1],
            legs=chaine.legs[debut:fin],
        ))
        debut = fin
    return morceaux


def construire_plan_collecte(db: Session) -> PlanCollecte:
    """Construit le plan de collecte du cycle à partir de l'état de la base."""
    axes_actifs: list[Troncon] = list(db.execute(
        select(Troncon).where(
            Troncon.actif.is_(True),
            Troncon.lat_origine.is_not(None),
            Troncon.lon_origine.is_not(None),
            Troncon.lat_destination.is_not(None),
            Troncon.lon_destination.is_not(None),
        ).order_by(Troncon.id)
    ).scalars())
    sous_actifs: dict[int, SousTroncon] = {
        s.id: s for s in db.execute(
            select(SousTroncon).where(
                SousTroncon.actif.is_(True),
                SousTroncon.lat_debut.is_not(None),
                SousTroncon.lon_debut.is_not(None),
                SousTroncon.lat_fin.is_not(None),
                SousTroncon.lon_fin.is_not(None),
            )
        ).scalars()
    }
    liens = db.execute(
        select(
            axe_sous_troncons.c.axe_id,
            axe_sous_troncons.c.sous_troncon_id,
            axe_sous_troncons.c.ordre,
        )
    ).all()

    # Rattachements axe → [(ordre, sous)] ; repli sur le parent principal
    # pour les tronçons antérieurs à la table M2M (migration 0016).
    par_axe: dict[int, list[tuple[int, SousTroncon]]] = {}
    sous_lies: set[int] = set()
    for axe_id, sous_id, ordre in liens:
        sous = sous_actifs.get(sous_id)
        if sous is None:
            continue
        par_axe.setdefault(axe_id, []).append((ordre or 0, sous))
        sous_lies.add(sous_id)
    for sous in sous_actifs.values():
        if sous.id not in sous_lies:
            par_axe.setdefault(sous.troncon_id, []).append((sous.ordre or 0, sous))

    axes_sans_troncon: list[Troncon] = []
    plans: list[PlanAxe] = []
    for axe in axes_actifs:
        rattaches = par_axe.get(axe.id)
        if not rattaches:
            axes_sans_troncon.append(axe)
            continue
        sous_ordonnes = [s for _, s in sorted(rattaches, key=lambda x: (x[0], x[1].id))]
        chaine = _chaine_axe(axe, sous_ordonnes)
        plans.append(PlanAxe(
            axe_id=axe.id,
            appels=_decouper(chaine),
            sous_troncon_ids=[s.id for s in sous_ordonnes],
        ))

    return PlanCollecte(axes_sans_troncon=axes_sans_troncon, plans_axes=plans)


def appels_google_par_cycle(db: Session) -> int:
    """Nombre de requêtes Google émises par un cycle de collecte."""
    return construire_plan_collecte(db).nb_appels
