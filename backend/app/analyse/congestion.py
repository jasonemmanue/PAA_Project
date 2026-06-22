"""Critère de congestion DEESP — module central.

Référence : *Rapport DEESP/DEEF — Évaluation du temps de traversée*
(rapport_oct2025.docx), section **METHODOLOGIE**, juste avant le Tableau 2.

Citation exacte (rapport, p. 5) :
    « Avec l'application « GOOGLE MAPS », ont été considérés comme tronçons
    embouteillés, les tronçons tracés en ROUGE et ceux tracés en ORANGE sur
    une longue distance (moitié du tronçon concerné). Il a été constaté,
    après que les équipes aient parcouru les différents axes, que les
    tronçons tracés en ORANGE sur une courte distance ne sont pas liés à
    des embouteillages mais à des arrêts dus aux feux tricolores ou à
    certaines manœuvres. »

Implémentation : on lit l'enum `Speed` retourné par Google Routes API dans
`travelAdvisory.speedReadingIntervals` (cf. `app/sources/google_routes.py`)
et on applique la règle ci-dessus à la lettre.

⚠️  Aucun ratio TTI/temps n'est utilisé ici. La qualification de
    congestion vient EXCLUSIVEMENT des couleurs Google Maps, comme dans
    le rapport. Le ratio `duree_trafic / T_ref` reste calculable ailleurs
    (pour les agrégats min/moyen/max), mais n'entre PAS dans la
    qualification fluide/congestionné.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# Seuil officiel DEESP : un tronçon est congestionné si l'ORANGE couvre au
# moins 50 % de sa longueur. Le rapport dit textuellement « la moitié du
# tronçon concerné ».
SEUIL_ORANGE_LONG_PCT = 50.0


# Trois classes seulement (le rapport ne distingue pas « dense ») :
#   - "fluide"        : vert + orange court → trafic OK
#   - "congestionne"  : rouge OU orange ≥ 50 % → embouteillage
#   - "indetermine"   : Google n'a pas renvoyé d'info couleur (trou de mesure
#                       partiel) — on n'invente pas de verdict.
ClasseCongestionDEESP = Literal["fluide", "congestionne", "indetermine"]


@dataclass(frozen=True)
class VerdictCongestion:
    """Résumé du verdict couleur DEESP pour un tronçon à un instant donné."""
    classe: ClasseCongestionDEESP
    pourcentage_rouge: float | None
    pourcentage_orange: float | None
    pourcentage_vert: float | None
    motif: str  # phrase humaine pour les popups / logs


def classer_congestion(
    pourcentage_rouge: float | None,
    pourcentage_orange: float | None,
    pourcentage_vert: float | None = None,
) -> VerdictCongestion:
    """Renvoie le verdict couleur DEESP à partir des trois pourcentages.

    Règles :
      1. Si tout est NULL → indéterminé (Google n'a pas qualifié le tracé).
      2. Si rouge > 0 → congestionné (« tronçon tracé en rouge »).
      3. Sinon si orange ≥ 50 % → congestionné (« orange sur une longue distance »).
      4. Sinon → fluide.
    """
    if pourcentage_rouge is None and pourcentage_orange is None and pourcentage_vert is None:
        return VerdictCongestion(
            classe="indetermine",
            pourcentage_rouge=None,
            pourcentage_orange=None,
            pourcentage_vert=None,
            motif="Google Maps n'a pas retourné de couleur trafic pour ce tronçon.",
        )

    rouge = pourcentage_rouge or 0.0
    orange = pourcentage_orange or 0.0
    vert = pourcentage_vert if pourcentage_vert is not None else max(
        0.0, 100.0 - rouge - orange
    )

    if rouge > 0:
        return VerdictCongestion(
            classe="congestionne",
            pourcentage_rouge=rouge,
            pourcentage_orange=orange,
            pourcentage_vert=vert,
            motif=(
                f"Tronçon tracé en rouge sur {rouge:.1f} % de sa longueur "
                f"(critère DEESP : rouge → congestionné)."
            ),
        )

    if orange >= SEUIL_ORANGE_LONG_PCT:
        return VerdictCongestion(
            classe="congestionne",
            pourcentage_rouge=rouge,
            pourcentage_orange=orange,
            pourcentage_vert=vert,
            motif=(
                f"Tronçon tracé en orange sur {orange:.1f} % de sa longueur "
                f"(critère DEESP : orange long ≥ {SEUIL_ORANGE_LONG_PCT:.0f} % → "
                f"congestionné)."
            ),
        )

    # Le rapport précise : « les tronçons tracés en orange sur une courte
    # distance ne sont pas liés à des embouteillages mais à des arrêts dus
    # aux feux tricolores ou à certaines manœuvres. »
    if orange > 0:
        motif = (
            f"Orange court ({orange:.1f} % du tracé) — non considéré comme "
            f"embouteillage par le rapport DEESP (feux ou manœuvres)."
        )
    else:
        motif = f"Tracé fluide ({vert:.1f} % vert)."

    return VerdictCongestion(
        classe="fluide",
        pourcentage_rouge=rouge,
        pourcentage_orange=orange,
        pourcentage_vert=vert,
        motif=motif,
    )


# Code couleur métier pour le frontend (Leaflet, KPI, popups). Seules
# 3 valeurs — pas de "dense" intermédiaire, conformément au rapport.
COULEURS_DEESP: dict[ClasseCongestionDEESP, str] = {
    "fluide":       "#2ECC71",  # vert clair
    "congestionne": "#E74C3C",  # rouge vif
    "indetermine":  "#95A5A6",  # gris (pas de donnée couleur)
}


LIBELLES_DEESP_FR: dict[ClasseCongestionDEESP, str] = {
    "fluide":       "Fluide",
    "congestionne": "Congestionné",
    "indetermine":  "Indéterminé",
}


LIBELLES_DEESP_EN: dict[ClasseCongestionDEESP, str] = {
    "fluide":       "Free-flowing",
    "congestionne": "Congested",
    "indetermine":  "Undetermined",
}
