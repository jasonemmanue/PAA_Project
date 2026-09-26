"""Extraction des données applicatives alimentant le Rapport DEESP officiel.

Toutes les valeurs produites ici proviennent exclusivement des mesures
collectées (table `mesures`, source Google Routes), filtrées sur la période et
le créneau horaire choisis par l'opérateur sur la page Rapport.

Conformément à la règle d'intégrité du projet (CLAUDE.md § 5.3), aucune valeur
n'est inventée : un tronçon sans mesure sur la fenêtre produit `None`, que le
générateur rend par un tiret.

Correspondance avec les tableaux du rapport :

  - Tableau 1          → `temps_theoriques` (réexporté depuis `rapport_paa`)
  - Tableau 2          → `legende_troncons`
  - Tableau 3          → `congestion_par_sens`
  - Tableaux 4-7       → `temps` avec agregat="min"
  - Tableaux 8-10      → `moyennes_journalieres`
  - Tableau 11         → `temps` avec agregat="moyen"
  - Tableaux 12-15     → `temps` avec agregat="max"
  - Tableau 16         → `congestion_par_sens`
  - Tableau 17         → `temps` (les trois agrégats)
  - Graphiques 1-12    → `series_graphiques`
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyse import rapport_paa
from app.analyse.aggregation import agreger_durees_par_creneau, axe_a_sous_troncons
from app.core.config import get_settings
from app.models.models import Mesure, SourceMesure, SousTroncon, Troncon


logger = logging.getLogger("paa.rapport.donnees")


# Ordre d'affichage des jours dans les 12 graphiques du rapport.
JOURS_SEMAINE = (
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
)

# Libellés français des mois, pour les titres et la page de garde.
MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensCirculation:
    """Un tronçon dirigé, décrit avec le vocabulaire du rapport DEESP."""

    troncon_id: int
    axe: str       # libellé de l'axe, insensible au sens (« CARENA - Pharmacie Palm Beach »)
    sens: str      # "aller" ou "retour"
    libelle: str   # libellé orienté (« Pharmacie Palm Beach - CARENA »)
    distance_km: float
    temps_reference_s: int


@dataclass
class LigneMoyenneJournaliere:
    """Une ligne des Tableaux 8-10 : le temps moyen d'une journée donnée."""

    jour: date
    libelle: str            # ex. « 01-févr »
    est_week_end: bool
    aller_mn: int | None
    retour_mn: int | None


@dataclass
class ContexteRapport:
    """Toutes les données applicatives nécessaires à la génération du rapport."""

    campagne: str
    debut: date
    fin: date
    heure_debut: int
    heure_fin: int

    # Tronçons dirigés actifs, ordonnés axe par axe (aller puis retour)
    sens_circulation: list[SensCirculation] = field(default_factory=list)
    # Axes distincts, dans l'ordre d'apparition
    axes: list[str] = field(default_factory=list)

    # Tableau 1
    temps_theoriques: list[rapport_paa.TempsTheorique] = field(default_factory=list)
    # Tableau 2 — (axe, libellé du tronçon codifié, code)
    legende_troncons: list[tuple[str, str, str]] = field(default_factory=list)

    # Tableaux 4-7 / 11 / 12-15 / 17 — clé (libellé sens, agrégat, type de jour)
    temps: dict[tuple[str, str, str], int | None] = field(default_factory=dict)
    # Nombre de mesures ayant servi au calcul, par (libellé sens, type de jour)
    nb_mesures: dict[tuple[str, str], int] = field(default_factory=dict)

    # Tableaux 8-10 — clé = libellé de l'axe
    moyennes_journalieres: dict[str, list[LigneMoyenneJournaliere]] = field(
        default_factory=dict
    )

    # Graphiques 1-12 — clé (libellé sens, agrégat)
    # Valeur : (libellés des semaines, matrice [semaine][jour] en minutes)
    series_graphiques: dict[tuple[str, str], tuple[list[str], list[list[int | None]]]] = (
        field(default_factory=dict)
    )

    # Tableaux 3 et 16 — clé = "aller" | "retour"
    congestion_par_sens: dict[str, list[rapport_paa.CongestionHoraire]] = field(
        default_factory=dict
    )

    nb_mesures_total: int = 0

    # -- Aides de lecture --------------------------------------------------

    def libelle_periode(self) -> str:
        """« 01 au 28 Février 2026 » — formulation utilisée dans la méthodologie."""
        mois = MOIS_FR[self.fin.month - 1].capitalize()
        if self.debut.month == self.fin.month and self.debut.year == self.fin.year:
            return f"{self.debut.day:02d} au {self.fin.day:02d} {mois} {self.fin.year}"
        mois_debut = MOIS_FR[self.debut.month - 1].capitalize()
        return (
            f"{self.debut.day:02d} {mois_debut} {self.debut.year} au "
            f"{self.fin.day:02d} {mois} {self.fin.year}"
        )

    def libelle_mois(self) -> str:
        """« Février » — titre de couverture."""
        return MOIS_FR[self.fin.month - 1].capitalize()

    def libelle_campagne(self) -> str:
        """« Février 2026 » — légende des sources sous chaque tableau."""
        return f"{self.libelle_mois()} {self.fin.year}"

    def libelle_creneau(self) -> str:
        """« 7h à 19h » ou « 24h/24 » selon le créneau retenu."""
        if self.heure_debut == 0 and self.heure_fin >= 24:
            return "24h/24"
        return f"{self.heure_debut}h à {self.heure_fin}h"

    def sens_de(self, sens: str) -> list[SensCirculation]:
        return [s for s in self.sens_circulation if s.sens == sens]

    def valeur(self, libelle: str, agregat: str, type_jour: str) -> int | None:
        return self.temps.get((libelle, agregat, type_jour))


# ---------------------------------------------------------------------------
# Identification des sens de circulation
# ---------------------------------------------------------------------------


def _sens_de_troncon(nom: str) -> str:
    """Déduit « aller » ou « retour » du libellé orienté d'un tronçon.

    Convention DEESP : Palm Beach est la destination de l'aller sur les trois
    axes officiels. Pour un axe ajouté via l'administration, on retient le
    sens 1 (celui dont le libellé est en ordre alphabétique croissant) comme
    aller, ce qui reste stable d'une génération à l'autre.
    """
    parties = [p.strip() for p in nom.split("→")]
    if len(parties) != 2:
        return "aller"
    origine, destination = parties
    if "Palm Beach" in destination:
        return "aller"
    if "Palm Beach" in origine:
        return "retour"
    return "aller" if origine <= destination else "retour"


def _libelle_oriente(nom: str) -> str:
    """« CARENA → Pharmacie Palm Beach » devient « CARENA - Pharmacie Palm Beach »."""
    return " - ".join(p.strip() for p in nom.split("→"))


def construire_sens_circulation(db: Session) -> list[SensCirculation]:
    """Liste les tronçons dirigés actifs, groupés par axe (aller puis retour)."""
    troncons = list(
        db.execute(
            select(Troncon)
            .where(Troncon.actif.is_(True), Troncon.est_axe.is_(True))
            .order_by(Troncon.id)
        ).scalars()
    )
    resultats: list[SensCirculation] = []
    for t in troncons:
        resultats.append(
            SensCirculation(
                troncon_id=t.id,
                axe=rapport_paa._libelle_axe(t.nom),
                sens=_sens_de_troncon(t.nom),
                libelle=_libelle_oriente(t.nom),
                distance_km=round(t.distance_ref_m / 1000.0, 1),
                temps_reference_s=int(round(t.temps_reference_s())),
            )
        )
    # Regroupement par axe, aller avant retour — reproduit l'ordre du rapport.
    ordre_axes: list[str] = []
    for s in resultats:
        if s.axe not in ordre_axes:
            ordre_axes.append(s.axe)
    return sorted(
        resultats,
        key=lambda s: (ordre_axes.index(s.axe), 0 if s.sens == "aller" else 1),
    )


# ---------------------------------------------------------------------------
# Durées brutes par date
# ---------------------------------------------------------------------------


def _durees_par_date(
    db: Session,
    troncon_ids: list[int],
    debut_utc: datetime,
    fin_utc: datetime,
    heure_debut: int,
    heure_fin: int,
) -> dict[int, dict[date, list[int]]]:
    """Retourne, par tronçon et par date locale, la liste des durées en secondes.

    Les axes décomposés en tronçons codifiés passent par l'agrégation
    (temps de l'axe = somme des tronçons du créneau, cf. CLAUDE.md § 24) ;
    les autres sont lus directement.
    """
    fuseau = ZoneInfo(get_settings().tz)
    resultat: dict[int, dict[date, list[int]]] = {
        tid: defaultdict(list) for tid in troncon_ids
    }

    ids_directs = [tid for tid in troncon_ids if not axe_a_sous_troncons(db, tid)]
    if ids_directs:
        mesures = db.execute(
            select(Mesure).where(
                Mesure.source == SourceMesure.google,
                Mesure.troncon_id.in_(ids_directs),
                Mesure.sous_troncon_id.is_(None),
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).scalars()
        for m in mesures:
            local = m.horodatage.astimezone(fuseau)
            if not rapport_paa._dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            resultat[m.troncon_id][local.date()].append(m.duree_trafic_s)

    for tid in troncon_ids:
        if tid in ids_directs:
            continue
        for horodatage, duree_s, _source in agreger_durees_par_creneau(
            db, tid, debut_utc, fin_utc, source_google_only=True
        ):
            local = (
                horodatage.astimezone(fuseau)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
            )
            if not rapport_paa._dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            resultat[tid][local.date()].append(duree_s)

    return resultat


# ---------------------------------------------------------------------------
# Assemblage du contexte
# ---------------------------------------------------------------------------


def construire_contexte(
    db: Session,
    campagne: str,
    debut_utc: datetime,
    fin_utc: datetime,
    heure_debut: int,
    heure_fin: int,
) -> ContexteRapport:
    """Assemble l'ensemble des données applicatives du rapport pour la période."""
    fuseau = ZoneInfo(get_settings().tz)
    debut_local = debut_utc.astimezone(fuseau).date()
    fin_local = fin_utc.astimezone(fuseau).date()

    contexte = ContexteRapport(
        campagne=campagne,
        debut=debut_local,
        fin=fin_local,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
    )

    contexte.sens_circulation = construire_sens_circulation(db)
    for s in contexte.sens_circulation:
        if s.axe not in contexte.axes:
            contexte.axes.append(s.axe)

    contexte.temps_theoriques = rapport_paa.temps_theoriques(db)
    contexte.legende_troncons = _legende_troncons(db, contexte)

    durees = _durees_par_date(
        db,
        [s.troncon_id for s in contexte.sens_circulation],
        debut_utc,
        fin_utc,
        heure_debut,
        heure_fin,
    )

    _remplir_temps(contexte, durees)
    _remplir_moyennes_journalieres(contexte, durees)
    _remplir_series_graphiques(contexte, durees)

    congestions = rapport_paa.troncons_congestionnes(
        db, debut_utc, fin_utc, heure_debut=heure_debut, heure_fin=heure_fin
    )
    contexte.congestion_par_sens = _repartir_congestions(contexte, congestions)

    contexte.nb_mesures_total = sum(
        len(liste) for par_date in durees.values() for liste in par_date.values()
    )
    logger.info(
        "Contexte rapport %s — %d sens, %d mesures, congestion aller=%d retour=%d",
        campagne,
        len(contexte.sens_circulation),
        contexte.nb_mesures_total,
        len(contexte.congestion_par_sens.get("aller", [])),
        len(contexte.congestion_par_sens.get("retour", [])),
    )
    return contexte


def _legende_troncons(db: Session, contexte: ContexteRapport) -> list[tuple[str, str, str]]:
    """Tableau 2 — tronçons codifiés (T1A, T1C…) regroupés par axe.

    Un tronçon partagé entre plusieurs axes n'apparaît qu'une fois, sous le
    premier axe qui le référence, comme dans le rapport de référence.
    """
    lignes: list[tuple[str, str, str]] = []
    codes_vus: set[str] = set()
    for sens in contexte.sens_circulation:
        sous_troncons = list(
            db.execute(
                select(SousTroncon)
                .where(
                    SousTroncon.troncon_id == sens.troncon_id,
                    SousTroncon.actif.is_(True),
                )
                .order_by(SousTroncon.ordre)
            ).scalars()
        )
        for st in sous_troncons:
            if st.code in codes_vus:
                continue
            codes_vus.add(st.code)
            lignes.append((sens.axe, st.nom_court, st.code))
    return lignes


def _remplir_temps(
    contexte: ContexteRapport, durees: dict[int, dict[date, list[int]]]
) -> None:
    """Calcule min / moyen / max par sens × type de jour (Tableaux 4-17).

    Le temps moyen suit la méthode DEESP : moyenne des moyennes journalières,
    et non moyenne brute de toutes les mesures.
    """
    for sens in contexte.sens_circulation:
        par_date = durees.get(sens.troncon_id, {})
        groupes: dict[str, list[list[int]]] = {"jour_ouvrable": [], "week_end": []}
        for jour, valeurs in par_date.items():
            if not valeurs:
                continue
            groupes[rapport_paa._type_jour(jour)].append(valeurs)

        for type_jour, jours in groupes.items():
            if not jours:
                for agregat in ("min", "moyen", "max"):
                    contexte.temps[(sens.libelle, agregat, type_jour)] = None
                contexte.nb_mesures[(sens.libelle, type_jour)] = 0
                continue
            toutes = [v for jour in jours for v in jour]
            moyennes_journalieres = [statistics.fmean(jour) for jour in jours]
            contexte.temps[(sens.libelle, "min", type_jour)] = int(round(min(toutes) / 60))
            contexte.temps[(sens.libelle, "max", type_jour)] = int(round(max(toutes) / 60))
            contexte.temps[(sens.libelle, "moyen", type_jour)] = int(
                round(statistics.fmean(moyennes_journalieres) / 60)
            )
            contexte.nb_mesures[(sens.libelle, type_jour)] = len(toutes)


def _remplir_moyennes_journalieres(
    contexte: ContexteRapport, durees: dict[int, dict[date, list[int]]]
) -> None:
    """Construit les Tableaux 8-10 — une ligne par jour du mois, aller et retour."""
    for axe in contexte.axes:
        aller = next(
            (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "aller"),
            None,
        )
        retour = next(
            (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "retour"),
            None,
        )
        lignes: list[LigneMoyenneJournaliere] = []
        jour = contexte.debut
        while jour <= contexte.fin:
            def moyenne(sens: SensCirculation | None) -> int | None:
                if sens is None:
                    return None
                valeurs = durees.get(sens.troncon_id, {}).get(jour) or []
                if not valeurs:
                    return None
                return int(round(statistics.fmean(valeurs) / 60))

            lignes.append(
                LigneMoyenneJournaliere(
                    jour=jour,
                    libelle=f"{jour.day:02d}-{MOIS_FR[jour.month - 1][:4]}",
                    est_week_end=jour.weekday() >= 5,
                    aller_mn=moyenne(aller),
                    retour_mn=moyenne(retour),
                )
            )
            jour = date.fromordinal(jour.toordinal() + 1)
        contexte.moyennes_journalieres[axe] = lignes


def _remplir_series_graphiques(
    contexte: ContexteRapport, durees: dict[int, dict[date, list[int]]]
) -> None:
    """Construit les 12 graphiques — semaines en séries, jours en catégories.

    Chaque barre porte le minimum (Graphiques 1-6) ou le maximum
    (Graphiques 7-12) observé ce jour-là, comme dans le rapport de référence.
    """
    # Découpage de la période en semaines calendaires ISO, numérotées S1, S2…
    semaines: list[tuple[int, int]] = []
    jour = contexte.debut
    while jour <= contexte.fin:
        cle = jour.isocalendar()[:2]
        if cle not in semaines:
            semaines.append(cle)
        jour = date.fromordinal(jour.toordinal() + 1)
    libelles_semaines = [f"S{i + 1}" for i in range(len(semaines))]

    for sens in contexte.sens_circulation:
        par_date = durees.get(sens.troncon_id, {})
        for agregat, fonction in (("min", min), ("max", max)):
            matrice: list[list[int | None]] = [
                [None] * len(JOURS_SEMAINE) for _ in semaines
            ]
            for jour, valeurs in par_date.items():
                if not valeurs:
                    continue
                cle = jour.isocalendar()[:2]
                if cle not in semaines:
                    continue
                ligne = semaines.index(cle)
                colonne = jour.weekday()
                valeur_jour = int(round(fonction(valeurs) / 60))
                actuelle = matrice[ligne][colonne]
                # Deux dates ne peuvent pas partager (semaine ISO, jour) ;
                # la garde ci-dessous n'est là que par sûreté.
                matrice[ligne][colonne] = (
                    valeur_jour
                    if actuelle is None
                    else int(fonction(actuelle, valeur_jour))
                )
            contexte.series_graphiques[(sens.libelle, agregat)] = (
                libelles_semaines,
                matrice,
            )


def _repartir_congestions(
    contexte: ContexteRapport,
    congestions: list[rapport_paa.CongestionHoraire],
) -> dict[str, list[rapport_paa.CongestionHoraire]]:
    """Répartit les tronçons congestionnés entre sens « aller » et « retour »."""
    sens_par_troncon = {s.troncon_id: s.sens for s in contexte.sens_circulation}
    repartition: dict[str, list[rapport_paa.CongestionHoraire]] = {
        "aller": [],
        "retour": [],
    }
    for congestion in congestions:
        sens = sens_par_troncon.get(congestion.troncon_id, "aller")
        repartition[sens].append(congestion)
    for liste in repartition.values():
        liste.sort(key=lambda c: (c.heure, c.sous_troncon_code or ""))
    return repartition
