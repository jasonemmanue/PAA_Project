"""Module RAG — détection d'intention et récupération du contexte temps réel.

Flux :
  1. `detecter_intentions(question)` identifie les besoins de données
  2. Chaque récupérateur interroge directement la DB (pas d'appel HTTP interne)
  3. `construire_contexte_rag(question, db)` assemble le bloc texte injecté
     dans le prompt Claude avant la question de l'utilisateur
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.models import (
    Incident,
    Mesure,
    ProfilHoraire,
    SeveriteIncident,
    SourceMesure,
    Troncon,
)

_FUSEAU = ZoneInfo("Africa/Abidjan")

# ---------------------------------------------------------------------------
# Détection d'intentions — correspondance par mots-clés
# ---------------------------------------------------------------------------

_MOTS_TRAFIC = [
    "trafic", "congestion", "congestionné", "embouteillage", "fluide",
    "état", "carte", "actuel", "maintenant", "situation", "bouchon",
    "circulation", "rouge", "orange",
]
_MOTS_HEURE = [
    "heure", "quand", "optimal", "optimale", "partir", "livrer", "livraison",
    "créneau", "meilleur moment", "meilleure heure", "conseille",
    "recommande", "fenêtre", "horaire",
]
_MOTS_TEMPS = [
    "temps", "durée", "combien", "traversée", "minutes", "trajet", "long",
    "rapide", "lent", "trajet",
]
_MOTS_INCIDENTS = [
    "incident", "accident", "route barr", "travaux", "bouchon",
    "problème", "perturbation", "signalé", "alerte", "danger",
]
_MOTS_STATS = [
    "statistique", "indicateur", "analyse", "moyenne", "minimum", "maximum",
    "taux", "historique", "données", "rapport", "semaine", "mois",
    "performance", "évolution",
]


def detecter_intentions(question: str) -> set[str]:
    """Retourne l'ensemble des intentions détectées dans la question."""
    q = question.lower()
    intentions: set[str] = set()
    if any(m in q for m in _MOTS_TRAFIC):
        intentions.add("etat_trafic")
    if any(m in q for m in _MOTS_HEURE):
        intentions.add("heure_optimale")
    if any(m in q for m in _MOTS_TEMPS):
        intentions.add("temps_traversee")
    if any(m in q for m in _MOTS_INCIDENTS):
        intentions.add("incidents")
    if any(m in q for m in _MOTS_STATS):
        intentions.add("statistiques")
    return intentions


# ---------------------------------------------------------------------------
# Utilitaire de formatage
# ---------------------------------------------------------------------------

def _fmt(secondes: float | int | None) -> str:
    """Formate des secondes en 'X min Y s' lisible."""
    if secondes is None:
        return "—"
    mn = int(secondes // 60)
    s = int(secondes % 60)
    return f"{mn} min {s:02d} s" if s else f"{mn} min"


def _maintenant_local() -> datetime:
    return datetime.now(tz=_FUSEAU)


def _horodatage_utc(dt: datetime) -> datetime:
    """Normalise un datetime en UTC (gère naïf et conscient)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Récupérateurs de données
# ---------------------------------------------------------------------------

def recuperer_etat_trafic(db: Session) -> str:
    """État actuel de chaque tronçon actif (dernière mesure < 2h)."""
    maintenant_utc = datetime.now(tz=timezone.utc)
    fenetre = maintenant_utc - timedelta(hours=2)
    horodatage_str = _maintenant_local().strftime("%d/%m/%Y à %Hh%M")

    troncons = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    lignes = [f"ÉTAT DU TRAFIC — relevé le {horodatage_str} (heure Abidjan)"]

    for t in troncons:
        mesure = db.execute(
            select(Mesure)
            .where(
                Mesure.troncon_id == t.id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.isnot(None),
                Mesure.horodatage >= fenetre,
            )
            .order_by(desc(Mesure.horodatage))
            .limit(1)
        ).scalar_one_or_none()

        ref_s = t.distance_m / 1000 / 50 * 3600 if t.distance_m else None

        if mesure:
            age_min = int(
                (maintenant_utc - _horodatage_utc(mesure.horodatage)).total_seconds() / 60
            )
            if mesure.est_congestionne is True:
                etat = "CONGESTIONNÉ"
            elif mesure.est_congestionne is False:
                etat = "FLUIDE"
            else:
                etat = "INDÉTERMINÉ"

            couleurs = ""
            if mesure.pourcentage_rouge is not None:
                couleurs = (
                    f" [rouge {mesure.pourcentage_rouge:.0f}%,"
                    f" orange {mesure.pourcentage_orange:.0f}%,"
                    f" vert {mesure.pourcentage_vert:.0f}%]"
                )

            ecart = ""
            if ref_s and mesure.duree_trafic_s:
                pct = (mesure.duree_trafic_s - ref_s) / ref_s * 100
                signe = "+" if pct >= 0 else ""
                ecart = f", {signe}{pct:.0f}% vs référence"

            lignes.append(
                f"  T{t.id} — {t.nom} : {etat}{couleurs}"
                f" — {_fmt(mesure.duree_trafic_s)} (référence {_fmt(ref_s)}{ecart})"
                f" — mesure il y a {age_min} min"
            )
        else:
            lignes.append(
                f"  T{t.id} — {t.nom} : aucune mesure récente (> 2h) — référence théorique {_fmt(ref_s)}"
            )

    return "\n".join(lignes)


def recuperer_temps_traversee(db: Session) -> str:
    """Temps de traversée actuel de chaque tronçon (dernière mesure < 90 min)."""
    maintenant_utc = datetime.now(tz=timezone.utc)
    fenetre = maintenant_utc - timedelta(minutes=90)
    horodatage_str = _maintenant_local().strftime("%d/%m/%Y à %Hh%M")

    troncons = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    lignes = [f"TEMPS DE TRAVERSÉE — {horodatage_str}"]

    for t in troncons:
        mesure = db.execute(
            select(Mesure)
            .where(
                Mesure.troncon_id == t.id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.isnot(None),
                Mesure.horodatage >= fenetre,
            )
            .order_by(desc(Mesure.horodatage))
            .limit(1)
        ).scalar_one_or_none()

        ref_s = t.distance_m / 1000 / 50 * 3600 if t.distance_m else None

        if mesure:
            ecart = ""
            if ref_s and mesure.duree_trafic_s:
                pct = (mesure.duree_trafic_s - ref_s) / ref_s * 100
                signe = "+" if pct >= 0 else ""
                ecart = f" ({signe}{pct:.0f}% vs référence {_fmt(ref_s)})"
            lignes.append(f"  T{t.id} — {t.nom} : {_fmt(mesure.duree_trafic_s)}{ecart}")
        else:
            lignes.append(f"  T{t.id} — {t.nom} : aucune mesure récente — référence {_fmt(ref_s)}")

    return "\n".join(lignes)


def recuperer_heure_optimale(db: Session) -> str:
    """Top-3 créneaux les plus rapides par tronçon pour le type de jour actuel."""
    maintenant_local = _maintenant_local()
    est_ouvrable = maintenant_local.weekday() < 5
    type_jour_label = "jours ouvrables" if est_ouvrable else "week-end"
    jours_filtre = list(range(5)) if est_ouvrable else [5, 6]

    troncons = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    lignes = [
        f"CRÉNEAUX OPTIMAUX — {type_jour_label} (historique 30 jours, 24h/24)"
    ]

    for t in troncons:
        rows = db.execute(
            select(
                ProfilHoraire.heure,
                func.avg(ProfilHoraire.moyenne).label("moy"),
                func.min(ProfilHoraire.min).label("p_min"),
                func.max(ProfilHoraire.max).label("p_max"),
                func.sum(ProfilHoraire.nb_mesures).label("nb"),
            )
            .where(
                ProfilHoraire.troncon_id == t.id,
                ProfilHoraire.fenetre_jours == 30,
                ProfilHoraire.jour_semaine.in_(jours_filtre),
                ProfilHoraire.heure >= 0,
                ProfilHoraire.heure < 24,
                ProfilHoraire.nb_mesures > 0,
            )
            .group_by(ProfilHoraire.heure)
            .order_by(ProfilHoraire.heure)
        ).all()

        if not rows:
            lignes.append(
                f"  T{t.id} — {t.nom} : historique insuffisant (collecte en cours)"
            )
            continue

        creneaux = [
            {
                "heure": r.heure,
                "moy_s": float(r.moy or 0),
                "min_s": float(r.p_min or 0),
                "max_s": float(r.p_max or 0),
                "nb": int(r.nb or 0),
            }
            for r in rows
        ]
        top3 = sorted(creneaux, key=lambda c: c["moy_s"])[:3]
        top3_str = ", ".join(
            f"{c['heure']:02d}h-{c['heure']+1:02d}h"
            f" (moy {c['moy_s']/60:.0f} min, min {c['min_s']/60:.0f} min)"
            for c in top3
        )
        lignes.append(f"  T{t.id} — {t.nom} : TOP 3 → {top3_str}")

    return "\n".join(lignes)


def recuperer_incidents_actifs(db: Session) -> str:
    """Incidents récents dans la zone portuaire (seuil configurable, défaut 30 j)."""
    from app.core.config import get_settings
    seuil_h = get_settings().incident_actif_heures
    limite_utc = datetime.now(tz=timezone.utc) - timedelta(hours=seuil_h)

    incidents = db.execute(
        select(Incident)
        .where(Incident.horodatage_publication >= limite_utc)
        .order_by(desc(Incident.horodatage_publication))
        .limit(10)
    ).scalars().all()

    if not incidents:
        return (
            "INCIDENTS ACTIFS — aucun incident signalé dans la zone portuaire"
            " au cours des 30 derniers jours."
        )

    lignes = [f"INCIDENTS ACTIFS — {len(incidents)} incident(s) détecté(s)"]
    for inc in incidents:
        age_h = int(
            (datetime.now(tz=timezone.utc) - _horodatage_utc(inc.horodatage_publication))
            .total_seconds()
            / 3600
        )
        try:
            sev = (inc.severite.value if hasattr(inc.severite, "value") else str(inc.severite or "inconnu")).upper()
        except Exception:
            sev = "INCONNU"
        lieu = inc.lieu_extrait or "zone portuaire"
        titre_court = inc.titre[:80] + ("…" if len(inc.titre) > 80 else "")
        lignes.append(
            f"  [{sev}] {titre_court} — {lieu}"
            f" — il y a {age_h}h ({inc.source_nom})"
        )

    return "\n".join(lignes)


def recuperer_statistiques_semaine(db: Session) -> str:
    """Stats agrégées depuis le lundi de la semaine en cours pour tous les tronçons."""
    maintenant_utc = datetime.now(tz=timezone.utc)
    maintenant_local = _maintenant_local()

    debut_semaine_utc = datetime.combine(
        maintenant_local.date() - timedelta(days=maintenant_local.weekday()),
        time(0, 0),
        tzinfo=_FUSEAU,
    ).astimezone(timezone.utc)

    debut_str = debut_semaine_utc.astimezone(_FUSEAU).strftime("%d/%m")

    troncons = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    lignes = [f"STATISTIQUES SEMAINE EN COURS (depuis lundi {debut_str})"]

    for t in troncons:
        mesures = db.execute(
            select(Mesure.duree_trafic_s, Mesure.est_congestionne)
            .where(
                Mesure.troncon_id == t.id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.isnot(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_semaine_utc,
            )
        ).all()

        if not mesures:
            lignes.append(f"  T{t.id} — {t.nom} : aucune mesure cette semaine")
            continue

        durees = [m.duree_trafic_s for m in mesures]
        nb_qualifies = sum(1 for m in mesures if m.est_congestionne is not None)
        nb_cong = sum(1 for m in mesures if m.est_congestionne is True)
        taux = (nb_cong / nb_qualifies * 100) if nb_qualifies else 0

        lignes.append(
            f"  T{t.id} — {t.nom} : {len(durees)} mesures —"
            f" moy {statistics.fmean(durees)/60:.0f} min,"
            f" min {min(durees)/60:.0f} min,"
            f" max {max(durees)/60:.0f} min —"
            f" taux congestion {taux:.0f}%"
        )

    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

async def construire_contexte_rag(question: str, db: Session) -> str:
    """Détecte les intentions et assemble le bloc contexte pour Claude.

    Retourne une chaîne vide si aucune intention nécessitant des données
    temps réel n'est détectée (questions purement fonctionnelles).
    """
    intentions = detecter_intentions(question)

    if not intentions:
        return ""

    blocs: list[str] = []
    logger = __import__("logging").getLogger("paa.rag")

    # Ordre : état global → temps → heure → incidents → stats
    _RECUPERATEURS: list[tuple[str, object]] = [
        ("etat_trafic", recuperer_etat_trafic),
        ("temps_traversee", recuperer_temps_traversee),
        ("heure_optimale", recuperer_heure_optimale),
        ("incidents", recuperer_incidents_actifs),
        ("statistiques", recuperer_statistiques_semaine),
    ]

    for intention, fn in _RECUPERATEURS:
        if intention not in intentions:
            continue
        if intention == "temps_traversee" and "etat_trafic" in intentions:
            continue
        try:
            blocs.append(fn(db))  # type: ignore[operator]
        except Exception:
            logger.exception("RAG : échec du récupérateur %s", intention)

    if not blocs:
        return ""

    corps = "\n\n".join(blocs)
    return (
        "DONNÉES RÉELLES DE L'APPLICATION"
        " (extraites à l'instant depuis la base de données Railway) :\n"
        f"{corps}\n\n"
        "Utilise ces données pour répondre avec précision."
        " Si une valeur affiche « — » ou « aucune mesure récente »,"
        " dis-le clairement à l'utilisateur plutôt que d'estimer."
    )
