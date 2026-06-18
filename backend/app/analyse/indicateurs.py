"""Indicateurs de congestion normalisés (FHWA-like) — phase P3.

Définitions retenues (cf. *FHWA Travel Time Reliability: Making It There On Time, All The Time*) :

  - **TTI (Travel Time Index)** = temps_mesuré / temps_référence
      Vaut 1 si on roule en conditions fluides, > 1 dès qu'il y a perte de temps.

  - **PTI (Planning Time Index)** = P95(temps_mesuré) / temps_référence
      Mesure le temps qu'il faut « budgétiser » pour être à l'heure 95 % du temps.

  - **BTI (Buffer Time Index)** = (P95 − moyenne) / moyenne
      Marge proportionnelle qu'un usager doit prévoir au-dessus de la moyenne.

  - **P95 brut** : 95ᵉ percentile de duree_trafic_s sur la fenêtre.

  - **Fréquence de dépassement d'un seuil** :
      part des mesures dont duree_trafic_s > seuil. Le seuil est soit fourni
      explicitement (query), soit configuré dans .env (SEUIL_DEPASSEMENT_S),
      soit dérivé automatiquement : 1,5 × T_ref.

Cascade du « temps de référence » (par ordre de priorité, CLAUDE.md § 2.5) :
  1. **Google `duree_sans_trafic_s`** observée sur la même fenêtre (médiane).
  2. ~~TomTom `freeFlow`~~ — *retiré du projet, conservé pour mémoire dans le code*.
  3. **Temps de référence 50 km/h** dérivé de la distance officielle du tronçon.

Classification de congestion (configurable via .env) :
  - **fluide**       : TTI < TTI_SEUIL_DENSE          (défaut 1,3)
  - **dense**        : TTI_SEUIL_DENSE ≤ TTI ≤ TTI_SEUIL_CONGESTIONNE (défauts 1,3–2,0)
  - **congestionné** : TTI > TTI_SEUIL_CONGESTIONNE   (défaut 2,0)
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.models import Mesure, ProfilHoraire, Troncon


logger = logging.getLogger("paa.analyse")


# ---------------------------------------------------------------------------
# Types et constantes
# ---------------------------------------------------------------------------


ClasseCongestion = Literal["fluide", "dense", "congestionne", "indetermine"]
SourceTempsReference = Literal["google_freeflow_median", "tomtom_freeflow", "vitesse_ref_50kmh"]
Granularite = Literal["hour", "day"]


@dataclass(frozen=True)
class SeuilsCongestion:
    """Paramètres de classification par TTI — surchargeables par appel."""
    dense: float
    congestionne: float
    heure_pointe: float

    @classmethod
    def depuis_settings(cls, settings: Settings | None = None) -> "SeuilsCongestion":
        s = settings or get_settings()
        return cls(
            dense=s.tti_seuil_dense,
            congestionne=s.tti_seuil_congestionne,
            heure_pointe=s.tti_seuil_heure_pointe,
        )


@dataclass
class IndicateursCongestion:
    """Snapshot des indicateurs pour un tronçon sur une fenêtre temporelle."""
    troncon_id: int
    troncon_nom: str
    debut_utc: str
    fin_utc: str
    nb_mesures: int
    nb_aberrantes_ignorees: int

    # Temps de référence retenu
    temps_reference_s: float | None
    source_temps_reference: SourceTempsReference | None

    # Statistiques de base sur duree_trafic_s
    moyenne_s: float | None
    mediane_s: float | None
    p95_s: float | None
    min_s: float | None
    max_s: float | None

    # Indicateurs FHWA-like
    tti: float | None
    pti: float | None
    bti: float | None

    # Dépassement d'un seuil métier (en secondes)
    seuil_depassement_s: int | None
    frequence_depassement: float | None  # part entre 0 et 1

    # Classification
    classe_congestion: ClasseCongestion
    seuils_utilises: dict[str, float]


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _temps_reference(
    troncon: Troncon,
    durees_sans_trafic: list[int],
) -> tuple[float, SourceTempsReference]:
    """Choisit le temps de référence selon la cascade documentée.

    Cascade :
      1. Médiane des `duree_sans_trafic_s` Google sur la fenêtre courante
         (≥ 1 valeur valide).
      2. ~~TomTom freeFlow~~ — *retiré* (CLAUDE.md § 2.5). Le hook reste là
         pour le jour où une seconde source temps réel sera réintroduite.
      3. Fallback déterministe : `distance_m / (vitesse_ref_kmh / 3.6)`.
    """
    if durees_sans_trafic:
        return float(statistics.median(durees_sans_trafic)), "google_freeflow_median"
    # Hook TomTom volontairement absent — la source est retirée du projet.
    t_ref_50 = troncon.distance_m / (troncon.vitesse_ref_kmh / 3.6)
    return float(t_ref_50), "vitesse_ref_50kmh"


def _percentile(valeurs: list[float], rang: float) -> float | None:
    """P_rang d'un échantillon (rang ∈ [0,100]). None si série vide."""
    if not valeurs:
        return None
    if len(valeurs) == 1:
        return float(valeurs[0])
    # statistics.quantiles avec n=100 expose les 99 points de coupure ;
    # le P95 correspond à l'index 94 (méthode inclusive — comportement attendu).
    coupures = statistics.quantiles(valeurs, n=100, method="inclusive")
    index = max(0, min(98, int(round(rang)) - 1))
    return float(coupures[index])


def classifier_congestion(
    tti: float | None,
    seuils: SeuilsCongestion,
) -> ClasseCongestion:
    """Retourne la classe de congestion à partir d'un TTI et des seuils."""
    if tti is None:
        return "indetermine"
    if tti < seuils.dense:
        return "fluide"
    if tti <= seuils.congestionne:
        return "dense"
    return "congestionne"


# ---------------------------------------------------------------------------
# Calcul principal des indicateurs sur une fenêtre temporelle
# ---------------------------------------------------------------------------


def calcul_indicateurs(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    seuil_depassement_s: int | None = None,
    seuils: SeuilsCongestion | None = None,
    inclure_aberrantes: bool = False,
) -> IndicateursCongestion:
    """Calcule l'ensemble des indicateurs pour un tronçon sur [debut, fin]."""
    seuils = seuils or SeuilsCongestion.depuis_settings()
    settings = get_settings()

    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    # Chargement des mesures de la fenêtre (succès uniquement : trous ignorés)
    requete = select(Mesure).where(
        Mesure.troncon_id == troncon_id,
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
        Mesure.duree_trafic_s.is_not(None),
    )
    mesures: list[Mesure] = list(db.execute(requete).scalars())

    # Séparation aberrantes / valides
    aberrantes = [m for m in mesures if m.aberrante]
    valides = mesures if inclure_aberrantes else [m for m in mesures if not m.aberrante]

    if not valides:
        return IndicateursCongestion(
            troncon_id=troncon.id,
            troncon_nom=troncon.nom,
            debut_utc=debut_utc.isoformat(),
            fin_utc=fin_utc.isoformat(),
            nb_mesures=len(mesures),
            nb_aberrantes_ignorees=len(aberrantes) if not inclure_aberrantes else 0,
            temps_reference_s=None,
            source_temps_reference=None,
            moyenne_s=None, mediane_s=None, p95_s=None, min_s=None, max_s=None,
            tti=None, pti=None, bti=None,
            seuil_depassement_s=None,
            frequence_depassement=None,
            classe_congestion="indetermine",
            seuils_utilises=asdict(seuils),
        )

    # Cascade temps de référence (à partir des duree_sans_trafic_s observées)
    durees_libres = [
        m.duree_sans_trafic_s for m in valides if m.duree_sans_trafic_s is not None
    ]
    t_ref, source_ref = _temps_reference(troncon, durees_libres)

    durees = [float(m.duree_trafic_s) for m in valides]
    moyenne = statistics.fmean(durees)
    mediane = statistics.median(durees)
    p95 = _percentile(durees, 95)
    mini = min(durees)
    maxi = max(durees)

    # Indicateurs FHWA-like
    tti = round(moyenne / t_ref, 3) if t_ref > 0 else None
    pti = round(p95 / t_ref, 3) if (p95 is not None and t_ref > 0) else None
    bti = round((p95 - moyenne) / moyenne, 3) if (p95 is not None and moyenne > 0) else None

    # Seuil de dépassement : priorité au param → puis .env → puis 1,5 × T_ref
    if seuil_depassement_s is None:
        seuil_depassement_s = settings.seuil_depassement_s
    if seuil_depassement_s is None:
        seuil_depassement_s = int(round(1.5 * t_ref))
    nb_depassements = sum(1 for d in durees if d > seuil_depassement_s)
    frequence = round(nb_depassements / len(durees), 3)

    return IndicateursCongestion(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        debut_utc=debut_utc.isoformat(),
        fin_utc=fin_utc.isoformat(),
        nb_mesures=len(mesures),
        nb_aberrantes_ignorees=len(aberrantes) if not inclure_aberrantes else 0,
        temps_reference_s=round(t_ref, 2),
        source_temps_reference=source_ref,
        moyenne_s=round(moyenne, 2),
        mediane_s=round(mediane, 2),
        p95_s=round(p95, 2) if p95 is not None else None,
        min_s=round(mini, 2),
        max_s=round(maxi, 2),
        tti=tti,
        pti=pti,
        bti=bti,
        seuil_depassement_s=int(seuil_depassement_s),
        frequence_depassement=frequence,
        classe_congestion=classifier_congestion(tti, seuils),
        seuils_utilises=asdict(seuils),
    )


# ---------------------------------------------------------------------------
# Détection des heures de pointe à partir des profils horaires
# ---------------------------------------------------------------------------


def detecter_heures_pointe(
    db: Session,
    troncon_id: int,
    *,
    fenetre_jours: int = 30,
    seuils: SeuilsCongestion | None = None,
) -> dict[str, object]:
    """Pour chaque jour de la semaine, retourne la liste des heures de pointe.

    Méthode : une heure est dite « de pointe » si la moyenne horaire des
    durées de parcours dépasse `seuils.heure_pointe × T_ref`. T_ref est ici
    la référence 50 km/h (déterministe, indépendante des données — cohérent
    pour un seuil structurel).
    """
    seuils = seuils or SeuilsCongestion.depuis_settings()
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    t_ref_50 = troncon.distance_m / (troncon.vitesse_ref_kmh / 3.6)
    seuil_pointe_s = seuils.heure_pointe * t_ref_50

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

    # 0 = lundi, libellé FR pour l'affichage
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
        "seuil_heure_pointe_tti": seuils.heure_pointe,
        "heures_de_pointe": par_jour,
    }


# ---------------------------------------------------------------------------
# Série temporelle de l'indicateur « temps de traversée »
# (article 4 du cahier des charges — évolution dans le temps)
# ---------------------------------------------------------------------------


def serie_temporelle(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    granularite: Granularite = "hour",
    inclure_aberrantes: bool = False,
) -> dict[str, object]:
    """Renvoie une série temporelle agrégée (heure ou jour) du temps de traversée.

    Chaque point contient : `instant_utc`, `moyenne_s`, `mediane_s`,
    `p95_s`, `tti`, `classe_congestion`, `nb_mesures`. Le TTI est calculé
    contre T_ref(50 km/h) pour une comparabilité historique stable.
    """
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    seuils = SeuilsCongestion.depuis_settings()
    t_ref_50 = troncon.distance_m / (troncon.vitesse_ref_kmh / 3.6)
    fuseau_local = ZoneInfo(get_settings().tz)

    requete = select(Mesure).where(
        Mesure.troncon_id == troncon_id,
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
        Mesure.duree_trafic_s.is_not(None),
    )
    if not inclure_aberrantes:
        requete = requete.where(Mesure.aberrante.is_(False))

    mesures: list[Mesure] = list(db.execute(requete).scalars())

    # Regroupement en mémoire — volume attendu modeste (qq milliers de points/jour max)
    # Clé = bucket arrondi à l'heure ou au jour, en heure locale (lisible).
    buckets: dict[datetime, list[float]] = {}
    for m in mesures:
        instant_local = m.horodatage.astimezone(fuseau_local)
        if granularite == "hour":
            cle = instant_local.replace(minute=0, second=0, microsecond=0)
        else:  # "day"
            cle = instant_local.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets.setdefault(cle, []).append(float(m.duree_trafic_s))

    points = []
    for instant_local in sorted(buckets):
        durees = buckets[instant_local]
        moyenne = statistics.fmean(durees)
        mediane = statistics.median(durees)
        p95 = _percentile(durees, 95)
        tti_pt = round(moyenne / t_ref_50, 3) if t_ref_50 > 0 else None
        points.append({
            "instant_local": instant_local.isoformat(),
            "instant_utc": instant_local.astimezone(timezone.utc).isoformat(),
            "moyenne_s": round(moyenne, 2),
            "mediane_s": round(mediane, 2),
            "p95_s": round(p95, 2) if p95 is not None else None,
            "tti": tti_pt,
            "classe_congestion": classifier_congestion(tti_pt, seuils),
            "nb_mesures": len(durees),
        })

    return {
        "troncon_id": troncon.id,
        "troncon_nom": troncon.nom,
        "granularite": granularite,
        "temps_reference_s": round(t_ref_50, 2),
        "source_temps_reference": "vitesse_ref_50kmh",
        "debut_utc": debut_utc.isoformat(),
        "fin_utc": fin_utc.isoformat(),
        "nb_points": len(points),
        "points": points,
    }


# ---------------------------------------------------------------------------
# Indicateurs glissants par jour (utile pour /troncons/{id}/indicateurs?jours=7)
# ---------------------------------------------------------------------------


def indicateurs_par_jour(
    db: Session,
    troncon_id: int,
    *,
    nb_jours: int,
    inclure_aberrantes: bool = False,
) -> dict[str, object]:
    """Calcule les indicateurs (TTI + classe) jour par jour sur les N derniers jours.

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
        jour_local = (maintenant_local - timedelta(days=n)).date()
        debut_local = datetime.combine(jour_local, datetime.min.time(), tzinfo=fuseau_local)
        fin_local = datetime.combine(jour_local, datetime.max.time(), tzinfo=fuseau_local)
        snapshot = calcul_indicateurs(
            db,
            troncon_id,
            debut_local.astimezone(timezone.utc),
            fin_local.astimezone(timezone.utc),
            inclure_aberrantes=inclure_aberrantes,
        )
        jours.append({
            "date_locale": jour_local.isoformat(),
            "nb_mesures": snapshot.nb_mesures,
            "moyenne_s": snapshot.moyenne_s,
            "p95_s": snapshot.p95_s,
            "tti": snapshot.tti,
            "pti": snapshot.pti,
            "bti": snapshot.bti,
            "classe_congestion": snapshot.classe_congestion,
            "temps_reference_s": snapshot.temps_reference_s,
            "source_temps_reference": snapshot.source_temps_reference,
        })
    return {
        "troncon_id": troncon.id,
        "troncon_nom": troncon.nom,
        "nb_jours": nb_jours,
        "fuseau": get_settings().tz,
        "jours": jours,
    }
