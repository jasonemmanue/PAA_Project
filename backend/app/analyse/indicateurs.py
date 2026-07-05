"""Indicateurs de congestion alignés sur la méthodologie DEESP.

⚠️  **Refonte 2026-06-22** — alignement strict sur le rapport DEESP/DEEF
    (« Évaluation du temps de traversée octobre 2025 »).

Avant : on calculait TTI / PTI / BTI (FHWA) et on classait les tronçons
en fluide / dense / congestionné en fonction d'un ratio
`duree_trafic / T_ref`. Ce ratio était une **approximation numérique** du
critère couleur DEESP — pas le critère officiel.

Maintenant : la qualification fluide / congestionné vient **exclusivement
des couleurs Google Maps** (champ `mesures.est_congestionne`, alimenté par
les `speedReadingIntervals` de l'API Google Routes). Le rapport ne
distingue d'ailleurs pas de classe « dense » intermédiaire — on est
fidèle au texte.

On conserve la production des 5 indicateurs **temps** publiés par le
rapport (cf. § 4.5.4) :

  - **temps minimal** (Tableaux 3-7)   : min des `duree_trafic_s`
  - **temps moyen**   (Tableaux 8-11)  : moyenne des moyennes journalières
  - **temps maximal** (Tableaux 12-15) : max des `duree_trafic_s`
  - **temps de référence 50 km/h**     : `distance / 50 km/h`
  - **taux de congestion**             : nb_mesures congestionnées /
                                          nb_mesures totales (selon le
                                          critère couleur DEESP)

Ces indicateurs alimentent les vues période courante / mois / semaine /
jour de la page Indicateurs. Les durées sans trafic et le TTI **ne sont
plus exposés** dans cette interface — ils restent stockés en base mais
n'apparaissent plus dans les réponses publiques.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyse.congestion import (
    ClasseCongestionDEESP,
    classer_congestion,
)
from app.core.config import get_settings
from app.models.models import Mesure, ProfilHoraire, Troncon


logger = logging.getLogger("paa.analyse")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


Granularite = Literal["hour", "day"]


@dataclass
class IndicateursTroncon:
    """Snapshot d'indicateurs DEESP pour un tronçon sur une fenêtre temporelle.

    Tous les temps sont en **secondes**. Le frontend convertit en minutes
    pour l'affichage (cf. § 4.5.4 du rapport).
    """
    troncon_id: int
    troncon_nom: str
    debut_utc: str
    fin_utc: str

    # Volumes
    nb_mesures: int                  # mesures avec duree_trafic_s renseigné
    nb_aberrantes_ignorees: int
    nb_mesures_congestionnees: int   # mesures avec est_congestionne=True
    nb_mesures_fluides: int          # mesures avec est_congestionne=False
    nb_mesures_couleur_indeterminee: int  # est_congestionne IS NULL

    # Temps de référence officiel (rapport, Tableau 1)
    temps_reference_50kmh_s: float

    # Indicateurs temps DEESP (Tableaux 3-15) — en secondes
    min_s: float | None
    moyenne_s: float | None
    max_s: float | None

    # Qualification couleur DEESP — agrégat sur la fenêtre
    taux_congestion: float | None       # nb_congestionne / nb_total (0..1)
    classe_congestion: ClasseCongestionDEESP
    pourcentage_rouge_moyen: float | None
    pourcentage_orange_moyen: float | None
    pourcentage_vert_moyen: float | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classe_depuis_moyennes(
    pct_rouge: float | None,
    pct_orange: float | None,
    pct_vert: float | None,
    nb_total: int,
) -> ClasseCongestionDEESP:
    """Classe la fenêtre globale à partir des pourcentages moyens couleur.

    Si aucune mesure n'a de couleur exploitable → indéterminée.
    Sinon : on applique la règle DEESP sur la moyenne agrégée.
    """
    if nb_total == 0 or (pct_rouge is None and pct_orange is None and pct_vert is None):
        return "indetermine"
    return classer_congestion(pct_rouge, pct_orange, pct_vert).classe


# ---------------------------------------------------------------------------
# Calcul principal des indicateurs sur une fenêtre temporelle
# ---------------------------------------------------------------------------


def calcul_indicateurs(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    inclure_aberrantes: bool = False,
    heure_debut: int = 0,
    heure_fin: int = 24,
    sous_troncon_id: int | None = None,
    type_jour: str = "tous",
) -> IndicateursTroncon:
    """Calcule les indicateurs DEESP pour un tronçon sur [debut, fin].

    Conserve uniquement les indicateurs publiés par le rapport :
    temps min / moyen / max, taux de congestion (couleur).

    Si `sous_troncon_id` est fourni, on restreint aux mesures fines
    portant sur ce sous-tronçon codifié (T1A, T2A…) — la référence
    50 km/h est alors calculée sur SA distance propre.
    """
    from app.models.models import SousTroncon  # import local pour éviter la boucle
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    sous = None
    if sous_troncon_id is not None:
        sous = db.get(SousTroncon, sous_troncon_id)
        if sous is None or sous.troncon_id != troncon_id:
            raise LookupError(
                f"Sous-tronçon id={sous_troncon_id} introuvable "
                f"ou pas rattaché à l'axe {troncon_id}."
            )

    ref_dist = sous.distance_m if sous is not None else troncon.distance_m
    ref_vit = 50.0 if sous is not None else troncon.vitesse_ref_kmh
    t_ref_50 = ref_dist / (ref_vit / 3.6)

    # Chargement des mesures de la fenêtre (succès uniquement).
    # Quand on interroge un axe (sous_troncon_id=None), on exclut les
    # mesures portant sur un sous-tronçon — elles ont des durées courtes
    # (portion d'axe) qui contamineraient les min/moyen/max de l'axe entier.
    requete = select(Mesure).where(
        Mesure.troncon_id == troncon_id,
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
        Mesure.duree_trafic_s.is_not(None),
    )
    if sous_troncon_id is not None:
        requete = requete.where(Mesure.sous_troncon_id == sous_troncon_id)
    else:
        requete = requete.where(Mesure.sous_troncon_id.is_(None))
    mesures: list[Mesure] = list(db.execute(requete).scalars())

    # Filtre par plage horaire locale et type de jour si nécessaire
    filtrer_heure = not (heure_debut == 0 and heure_fin == 24)
    filtrer_type_jour = type_jour in ("jour_ouvrable", "week_end")
    if filtrer_heure or filtrer_type_jour:
        fuseau = ZoneInfo(get_settings().tz)
        resultat = []
        for m in mesures:
            h_local = m.horodatage.astimezone(fuseau)
            if filtrer_heure and not (heure_debut <= h_local.hour < heure_fin):
                continue
            if filtrer_type_jour:
                est_ouvrable = h_local.weekday() < 5
                if type_jour == "jour_ouvrable" and not est_ouvrable:
                    continue
                if type_jour == "week_end" and est_ouvrable:
                    continue
            resultat.append(m)
        mesures = resultat

    aberrantes = [m for m in mesures if m.aberrante]
    valides = mesures if inclure_aberrantes else [m for m in mesures if not m.aberrante]

    if not valides:
        return IndicateursTroncon(
            troncon_id=troncon.id,
            troncon_nom=(
                f"{troncon.nom} : {sous.nom_court} ({sous.code})"
                if sous is not None else troncon.nom
            ),
            debut_utc=debut_utc.isoformat(),
            fin_utc=fin_utc.isoformat(),
            nb_mesures=0,
            nb_aberrantes_ignorees=len(aberrantes) if not inclure_aberrantes else 0,
            nb_mesures_congestionnees=0,
            nb_mesures_fluides=0,
            nb_mesures_couleur_indeterminee=0,
            temps_reference_50kmh_s=round(t_ref_50, 2),
            min_s=None, moyenne_s=None, max_s=None,
            taux_congestion=None,
            classe_congestion="indetermine",
            pourcentage_rouge_moyen=None,
            pourcentage_orange_moyen=None,
            pourcentage_vert_moyen=None,
        )

    durees = [float(m.duree_trafic_s) for m in valides]
    min_s = min(durees)
    moyenne_s = statistics.fmean(durees)
    max_s = max(durees)

    # Compteurs par classe DEESP (lecture directe du booléen pré-calculé)
    nb_congestionne = sum(1 for m in valides if m.est_congestionne is True)
    nb_fluide = sum(1 for m in valides if m.est_congestionne is False)
    nb_indetermine = sum(1 for m in valides if m.est_congestionne is None)

    nb_qualifie = nb_congestionne + nb_fluide
    taux_congestion = (
        round(nb_congestionne / nb_qualifie, 3) if nb_qualifie > 0 else None
    )

    # Moyennes des pourcentages couleur (sur les mesures qualifiées)
    rouges = [m.pourcentage_rouge for m in valides if m.pourcentage_rouge is not None]
    oranges = [m.pourcentage_orange for m in valides if m.pourcentage_orange is not None]
    verts = [m.pourcentage_vert for m in valides if m.pourcentage_vert is not None]
    pct_r_moy = round(statistics.fmean(rouges), 2) if rouges else None
    pct_o_moy = round(statistics.fmean(oranges), 2) if oranges else None
    pct_v_moy = round(statistics.fmean(verts), 2) if verts else None

    classe = _classe_depuis_moyennes(pct_r_moy, pct_o_moy, pct_v_moy, nb_qualifie)

    return IndicateursTroncon(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        debut_utc=debut_utc.isoformat(),
        fin_utc=fin_utc.isoformat(),
        nb_mesures=len(mesures),
        nb_aberrantes_ignorees=len(aberrantes) if not inclure_aberrantes else 0,
        nb_mesures_congestionnees=nb_congestionne,
        nb_mesures_fluides=nb_fluide,
        nb_mesures_couleur_indeterminee=nb_indetermine,
        temps_reference_50kmh_s=round(t_ref_50, 2),
        min_s=round(min_s, 2),
        moyenne_s=round(moyenne_s, 2),
        max_s=round(max_s, 2),
        taux_congestion=taux_congestion,
        classe_congestion=classe,
        pourcentage_rouge_moyen=pct_r_moy,
        pourcentage_orange_moyen=pct_o_moy,
        pourcentage_vert_moyen=pct_v_moy,
    )


# ---------------------------------------------------------------------------
# Heures de pointe (à partir des profils horaires)
# ---------------------------------------------------------------------------


def detecter_heures_pointe(
    db: Session,
    troncon_id: int,
    *,
    fenetre_jours: int = 30,
    facteur_pointe: float = 1.5,
) -> dict[str, object]:
    """Pour chaque jour de la semaine, retourne la liste des heures de pointe.

    Une heure est dite « de pointe » si la moyenne horaire des durées
    dépasse `facteur_pointe × T_ref(50 km/h)`. T_ref est la référence
    50 km/h (déterministe, indépendante des données — cohérent pour un
    seuil structurel, et c'est la référence du rapport, Tableau 1).
    """
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    t_ref_50 = troncon.distance_m / (troncon.vitesse_ref_kmh / 3.6)
    seuil_pointe_s = facteur_pointe * t_ref_50

    profils: list[ProfilHoraire] = list(
        db.execute(
            select(ProfilHoraire)
            .where(
                ProfilHoraire.troncon_id == troncon_id,
                ProfilHoraire.fenetre_jours == fenetre_jours,
            )
            .order_by(ProfilHoraire.jour_semaine, ProfilHoraire.heure)
        ).scalars()
    )

    noms_jours_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    par_jour: dict[str, list[int]] = {nom: [] for nom in noms_jours_fr}
    for p in profils:
        if p.moyenne is None:
            continue
        if p.moyenne > seuil_pointe_s:
            par_jour[noms_jours_fr[p.jour_semaine]].append(p.heure)

    return {
        "troncon_id": troncon.id,
        "troncon_nom": troncon.nom,
        "fenetre_jours": fenetre_jours,
        "temps_reference_50kmh_s": round(t_ref_50, 2),
        "seuil_heure_pointe_s": round(seuil_pointe_s, 2),
        "facteur_pointe": facteur_pointe,
        "heures_de_pointe": par_jour,
    }


# ---------------------------------------------------------------------------
# Série temporelle (article 4 du cahier des charges — évolution dans le temps)
# ---------------------------------------------------------------------------


def serie_temporelle(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    granularite: Granularite = "hour",
    inclure_aberrantes: bool = False,
    heure_debut: int = 0,
    heure_fin: int = 24,
    sous_troncon_id: int | None = None,
    type_jour: str = "tous",
) -> dict[str, object]:
    """Renvoie une série temporelle agrégée (heure ou jour) du temps de traversée.

    Chaque point contient le min, moyen, max (en secondes) et la classe
    de congestion DEESP basée sur le taux de mesures congestionnées dans
    le bucket. Pas de TTI : on est aligné sur les Tableaux 3-15 du rapport.
    """
    from app.models.models import SousTroncon  # import local
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    sous = None
    if sous_troncon_id is not None:
        sous = db.get(SousTroncon, sous_troncon_id)
        if sous is None or sous.troncon_id != troncon_id:
            raise LookupError(
                f"Sous-tronçon id={sous_troncon_id} introuvable "
                f"ou pas rattaché à l'axe {troncon_id}."
            )

    ref_dist = sous.distance_m if sous is not None else troncon.distance_m
    ref_vit = 50.0 if sous is not None else troncon.vitesse_ref_kmh
    t_ref_50 = ref_dist / (ref_vit / 3.6)
    fuseau_local = ZoneInfo(get_settings().tz)

    requete = select(Mesure).where(
        Mesure.troncon_id == troncon_id,
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
        Mesure.duree_trafic_s.is_not(None),
    )
    if sous_troncon_id is not None:
        requete = requete.where(Mesure.sous_troncon_id == sous_troncon_id)
    else:
        requete = requete.where(Mesure.sous_troncon_id.is_(None))
    if not inclure_aberrantes:
        requete = requete.where(Mesure.aberrante.is_(False))

    mesures: list[Mesure] = list(db.execute(requete).scalars())

    # Filtre par plage horaire locale et type de jour si nécessaire
    filtrer_heure = not (heure_debut == 0 and heure_fin == 24)
    filtrer_type_jour = type_jour in ("jour_ouvrable", "week_end")
    if filtrer_heure or filtrer_type_jour:
        resultat = []
        for m in mesures:
            h_local = m.horodatage.astimezone(fuseau_local)
            if filtrer_heure and not (heure_debut <= h_local.hour < heure_fin):
                continue
            if filtrer_type_jour:
                est_ouvrable = h_local.weekday() < 5
                if type_jour == "jour_ouvrable" and not est_ouvrable:
                    continue
                if type_jour == "week_end" and est_ouvrable:
                    continue
            resultat.append(m)
        mesures = resultat

    buckets: dict[datetime, list[Mesure]] = defaultdict(list)
    for m in mesures:
        instant_local = m.horodatage.astimezone(fuseau_local)
        if granularite == "hour":
            cle = instant_local.replace(minute=0, second=0, microsecond=0)
        else:
            cle = instant_local.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets[cle].append(m)

    points = []
    for instant_local in sorted(buckets):
        seau = buckets[instant_local]
        durees = [float(m.duree_trafic_s) for m in seau]
        nb_congestionne = sum(1 for m in seau if m.est_congestionne is True)
        nb_fluide = sum(1 for m in seau if m.est_congestionne is False)
        nb_qualifie = nb_congestionne + nb_fluide
        taux = (
            round(nb_congestionne / nb_qualifie, 3) if nb_qualifie > 0 else None
        )
        # La classe d'un bucket reprend la règle DEESP : congestionné si la
        # mesure médiane du bucket est congestionnée (majorité).
        if nb_qualifie == 0:
            classe: ClasseCongestionDEESP = "indetermine"
        elif nb_congestionne > nb_fluide:
            classe = "congestionne"
        else:
            classe = "fluide"
        points.append({
            "instant_local": instant_local.isoformat(),
            "instant_utc": instant_local.astimezone(timezone.utc).isoformat(),
            "min_s": round(min(durees), 2),
            "moyenne_s": round(statistics.fmean(durees), 2),
            "max_s": round(max(durees), 2),
            "taux_congestion": taux,
            "classe_congestion": classe,
            "nb_mesures": len(seau),
        })

    nom_affichage = (
        f"{troncon.nom} : {sous.nom_court} ({sous.code})"
        if sous is not None else troncon.nom
    )
    return {
        "troncon_id": troncon.id,
        "troncon_nom": nom_affichage,
        "granularite": granularite,
        "temps_reference_50kmh_s": round(t_ref_50, 2),
        "debut_utc": debut_utc.isoformat(),
        "fin_utc": fin_utc.isoformat(),
        "nb_points": len(points),
        "points": points,
    }


# ---------------------------------------------------------------------------
# Indicateurs glissants par jour
# ---------------------------------------------------------------------------


def indicateurs_par_jour(
    db: Session,
    troncon_id: int,
    *,
    nb_jours: int,
    inclure_aberrantes: bool = False,
    heure_debut: int = 0,
    heure_fin: int = 24,
    sous_troncon_id: int | None = None,
    type_jour: str = "tous",
) -> dict[str, object]:
    """Calcule les indicateurs DEESP jour par jour sur les N derniers jours.

    Format pensé pour un tableau frontend : une ligne par jour calendrier
    local Africa/Abidjan, du plus récent au plus ancien.
    """
    fuseau_local = ZoneInfo(get_settings().tz)
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    maintenant_local = datetime.now(tz=fuseau_local)
    jours: list[dict[str, object]] = []
    for n in range(nb_jours):
        jour_local: date = (maintenant_local - timedelta(days=n)).date()
        debut_local = datetime.combine(jour_local, datetime.min.time(), tzinfo=fuseau_local)
        fin_local = datetime.combine(jour_local, datetime.max.time(), tzinfo=fuseau_local)
        snapshot = calcul_indicateurs(
            db,
            troncon_id,
            debut_local.astimezone(timezone.utc),
            fin_local.astimezone(timezone.utc),
            inclure_aberrantes=inclure_aberrantes,
            heure_debut=heure_debut,
            heure_fin=heure_fin,
            sous_troncon_id=sous_troncon_id,
            type_jour=type_jour,
        )
        jours.append({
            "date_locale": jour_local.isoformat(),
            "nb_mesures": snapshot.nb_mesures,
            "min_s": snapshot.min_s,
            "moyenne_s": snapshot.moyenne_s,
            "max_s": snapshot.max_s,
            "taux_congestion": snapshot.taux_congestion,
            "classe_congestion": snapshot.classe_congestion,
            "temps_reference_50kmh_s": snapshot.temps_reference_50kmh_s,
        })
    return {
        "troncon_id": troncon.id,
        "troncon_nom": troncon.nom,
        "nb_jours": nb_jours,
        "fuseau": get_settings().tz,
        "jours": jours,
    }
