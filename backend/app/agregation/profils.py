"""Agrégation nocturne des mesures en profils horaires (phase P2).

Pour chaque (tronçon, jour_semaine, heure, fenêtre_jours) :
  - moyenne, médiane, min, max, p95, nb_mesures
  - détection des aberrants par la méthode de l'écart interquartile :
    une mesure est marquée `aberrante = TRUE` si sa `duree_trafic_s` tombe
    hors de [Q1 − 1,5 · IQR ; Q3 + 1,5 · IQR] dans son bucket.

Conventions :
  - Les mesures aberrantes sont **conservées en base** et **incluses** dans
    nb_mesures (transparence) mais **exclues** du recalcul des agrégats
    (moyenne, médiane, …) — cf. CLAUDE.md § 5.3 (aucune donnée inventée).
  - Le calcul tourne sur les **3 fenêtres glissantes** 30 / 60 / 90 jours
    en une seule passe : on charge les mesures sur 90 jours, puis on filtre
    en mémoire pour les 3 sous-fenêtres. Évite 3 allers-retours SQL.
  - Le jour de la semaine et l'heure sont calculés dans le fuseau métier
    `Africa/Abidjan` (l'horodatage SQL est en UTC).
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import Mesure, ProfilHoraire, Troncon


logger = logging.getLogger("paa.agregation")


# Fenêtres glissantes calculées à chaque exécution. La plus large doit être
# en tête : on charge une fois pour 90 j, puis on dérive 60 et 30 par filtrage.
FENETRES_JOURS: tuple[int, ...] = (90, 60, 30)


# ---------------------------------------------------------------------------
# Détection IQR (Q1 − 1,5·IQR ; Q3 + 1,5·IQR)
# ---------------------------------------------------------------------------


def _bornes_iqr(valeurs: list[float]) -> tuple[float, float] | None:
    """Retourne (borne_basse, borne_haute) au sens IQR, ou None si trop peu de points.

    Au moins 4 points sont nécessaires pour calculer des quartiles sensés.
    En deçà, on ne flag personne (faute de base statistique).
    """
    if len(valeurs) < 4:
        return None
    # statistics.quantiles(n=4) renvoie 3 points de coupure : Q1, Q2 (médiane), Q3.
    q1, _q2, q3 = statistics.quantiles(valeurs, n=4, method="inclusive")
    iqr = q3 - q1
    return (q1 - 1.5 * iqr, q3 + 1.5 * iqr)


# ---------------------------------------------------------------------------
# Calcul des agrégats pour un bucket (mesures non aberrantes uniquement)
# ---------------------------------------------------------------------------


def _agreger_bucket(durees: list[float]) -> dict[str, float | None]:
    """Calcule les 5 stats sur une liste de durées (déjà filtrée des aberrants)."""
    if not durees:
        return {
            "moyenne": None,
            "mediane": None,
            "min": None,
            "max": None,
            "p95": None,
        }
    durees_triees = sorted(durees)
    if len(durees_triees) >= 2:
        # quantiles(n=20)[18] = bord supérieur du 19e vingtile = p95
        p95 = statistics.quantiles(durees_triees, n=20, method="inclusive")[18]
    else:
        p95 = float(durees_triees[0])
    return {
        "moyenne": round(statistics.fmean(durees_triees), 2),
        "mediane": round(statistics.median(durees_triees), 2),
        "min": float(durees_triees[0]),
        "max": float(durees_triees[-1]),
        "p95": round(p95, 2),
    }


# ---------------------------------------------------------------------------
# Coeur du calcul : un cycle complet d'agrégation
# ---------------------------------------------------------------------------


def _id_bucket(troncon_id: int, jour_semaine: int, heure: int) -> tuple[int, int, int]:
    """Clé hashable utilisée pour regrouper les mesures par bucket."""
    return (troncon_id, jour_semaine, heure)


def executer_agregation(
    session: Session | None = None,
) -> dict[str, int]:
    """Exécute un cycle complet d'agrégation et persiste les résultats.

    Étapes :
      1. Charge l'ensemble des mesures valides (duree_trafic_s NOT NULL) sur
         la fenêtre maximale (90 jours glissants à partir de maintenant UTC).
      2. Pour chaque (tronçon, jour_local, heure_local), calcule les bornes IQR
         puis identifie les mesures aberrantes.
      3. Écrit le flag `aberrante` en base (UPDATE ciblé sur leurs ids).
      4. Pour les 3 fenêtres 30/60/90 j, calcule moyenne / médiane / min / max
         / p95 / nb_mesures (en excluant les aberrantes du calcul).
      5. Remplace intégralement les lignes existantes de `profils_horaires`
         (DELETE + INSERT en masse) pour garantir la cohérence stricte avec
         le snapshot de mesures courant.

    Retourne un résumé pour les logs et l'endpoint /agregation/run.
    """
    fuseau_local = ZoneInfo(get_settings().tz)
    instant_utc = datetime.now(tz=timezone.utc)
    seuil_utc_min = instant_utc - timedelta(days=max(FENETRES_JOURS))

    propre_session = session is None
    if propre_session:
        session = SessionLocal()

    try:
        # ------------------------------------------------------------------
        # 1. Chargement des mesures valides sur 90 j
        # ------------------------------------------------------------------
        mesures: list[Mesure] = list(
            session.execute(
                select(Mesure).where(
                    Mesure.horodatage >= seuil_utc_min,
                    Mesure.duree_trafic_s.is_not(None),
                )
            ).scalars()
        )

        if not mesures:
            logger.warning(
                "Agrégation : aucune mesure valide trouvée dans les %d derniers jours.",
                max(FENETRES_JOURS),
            )

        # ------------------------------------------------------------------
        # 2. Regroupement par bucket (tronçon, jour_local, heure_local)
        #    avec l'âge en jours pour le filtrage par fenêtre.
        # ------------------------------------------------------------------
        # bucket -> list[(mesure_id, duree_s, age_jours)]
        buckets: dict[tuple[int, int, int], list[tuple[int, float, float]]] = defaultdict(list)
        for m in mesures:
            local = m.horodatage.astimezone(fuseau_local)
            jour = local.weekday()  # 0 = lundi
            heure = local.hour
            age_jours = (instant_utc - m.horodatage).total_seconds() / 86_400.0
            buckets[_id_bucket(m.troncon_id, jour, heure)].append(
                (m.id, float(m.duree_trafic_s), age_jours)
            )

        # ------------------------------------------------------------------
        # 3. Détection IQR + collecte des ids aberrants
        # ------------------------------------------------------------------
        ids_aberrants: set[int] = set()
        for bucket_id, entrees in buckets.items():
            durees = [e[1] for e in entrees]
            bornes = _bornes_iqr(durees)
            if bornes is None:
                continue
            basse, haute = bornes
            for mid, duree, _age in entrees:
                if duree < basse or duree > haute:
                    ids_aberrants.add(mid)

        # ------------------------------------------------------------------
        # 4. MAJ du flag `aberrante` : on remet d'abord toutes les mesures
        #    de la fenêtre à FALSE puis on flag les nouvelles aberrantes.
        #    Cette idempotence évite qu'une mesure perde son aberrance si
        #    de nouvelles données la rendent finalement normale.
        # ------------------------------------------------------------------
        ids_dans_fenetre = [m.id for m in mesures]
        if ids_dans_fenetre:
            session.execute(
                update(Mesure)
                .where(Mesure.id.in_(ids_dans_fenetre))
                .values(aberrante=False)
            )
        if ids_aberrants:
            session.execute(
                update(Mesure)
                .where(Mesure.id.in_(ids_aberrants))
                .values(aberrante=True)
            )

        # ------------------------------------------------------------------
        # 5. Calcul des agrégats par fenêtre — on exclut les aberrantes.
        # ------------------------------------------------------------------
        # (troncon_id, jour, heure, fenetre_jours) -> dict des stats
        agregats: dict[tuple[int, int, int, int], dict[str, float | int | None]] = {}

        for fenetre in FENETRES_JOURS:
            for bucket_id, entrees in buckets.items():
                # Filtre fenêtre + non aberrante
                durees_filtrees = [
                    duree
                    for (mid, duree, age) in entrees
                    if age <= fenetre and mid not in ids_aberrants
                ]
                nb_mesures_total = sum(1 for (_, _, age) in entrees if age <= fenetre)
                if nb_mesures_total == 0:
                    continue  # rien à publier pour ce bucket × cette fenêtre

                stats = _agreger_bucket(durees_filtrees)
                cle = (*bucket_id, fenetre)
                agregats[cle] = {
                    **stats,
                    "nb_mesures": nb_mesures_total,  # inclut les aberrantes (traçabilité)
                }

        # ------------------------------------------------------------------
        # 6. Remplacement intégral de profils_horaires
        #    DELETE puis INSERT en masse — simple et cohérent.
        # ------------------------------------------------------------------
        session.execute(delete(ProfilHoraire))
        session.flush()

        for (troncon_id, jour, heure, fenetre), stats in agregats.items():
            session.add(
                ProfilHoraire(
                    troncon_id=troncon_id,
                    jour_semaine=jour,
                    heure=heure,
                    fenetre_jours=fenetre,
                    moyenne=stats["moyenne"],
                    mediane=stats["mediane"],
                    min=stats["min"],
                    max=stats["max"],
                    p95=stats["p95"],
                    nb_mesures=stats["nb_mesures"],
                )
            )

        session.commit()

        resume = {
            "nb_mesures_analysees": len(mesures),
            "nb_aberrantes": len(ids_aberrants),
            "nb_buckets": len(buckets),
            "nb_lignes_profils": len(agregats),
            "fenetres_jours": list(FENETRES_JOURS),
        }
        logger.info(
            "Agrégation terminée — %d mesures, %d aberrantes, %d buckets, "
            "%d lignes profils écrites (fenêtres %s).",
            resume["nb_mesures_analysees"],
            resume["nb_aberrantes"],
            resume["nb_buckets"],
            resume["nb_lignes_profils"],
            FENETRES_JOURS,
        )
        return resume

    except Exception:
        if propre_session:
            session.rollback()
        raise
    finally:
        if propre_session:
            session.close()
