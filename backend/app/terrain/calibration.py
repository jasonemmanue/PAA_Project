"""Facteur de calibration par tronçon — moyenne mobile des écarts terrain/API.

Définition : pour chaque tronçon, on calcule la moyenne des `ecart_relatif`
des N derniers relevés terrain. Cette moyenne est le **facteur de
calibration** : si elle vaut +0,12, cela signifie que la mesure Google sous-
estime systématiquement le temps réel de 12 % sur ce tronçon.

Le frontend l'utilise dans la page Fiabilité pour signaler une dérive
éventuelle et, à terme, calibrer les prédictions P6.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ReleveTerrain, Troncon


FENETRE_DEFAUT = 4  # 4 dernières sessions = ~1 mois de relevés hebdomadaires


@dataclass(frozen=True)
class CalibrationTroncon:
    troncon_id: int
    troncon_nom: str
    nb_releves: int
    ecart_moyen: float | None  # moyenne des ecart_relatif
    ecart_courant: float | None  # le plus récent (dernier relevé)
    fenetre: int


def calibration_par_troncon(
    db: Session,
    *,
    fenetre: int = FENETRE_DEFAUT,
) -> list[CalibrationTroncon]:
    """Pour chaque tronçon actif, calcule la moyenne des N derniers écarts.

    Les relevés sans `ecart_relatif` (mesure API absente au moment du passage)
    sont ignorés du calcul mais comptés dans `nb_releves` total.
    """
    troncons = list(
        db.execute(
            select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
        ).scalars()
    )

    resultats: list[CalibrationTroncon] = []
    for t in troncons:
        releves = list(
            db.execute(
                select(ReleveTerrain)
                .where(ReleveTerrain.troncon_id == t.id)
                .order_by(ReleveTerrain.horodatage_passage.desc().nullslast())
                .limit(fenetre)
            ).scalars()
        )
        ecarts = [r.ecart_relatif for r in releves if r.ecart_relatif is not None]
        ecart_moyen = sum(ecarts) / len(ecarts) if ecarts else None
        ecart_courant = ecarts[0] if ecarts else None
        resultats.append(CalibrationTroncon(
            troncon_id=t.id,
            troncon_nom=t.nom,
            nb_releves=len(releves),
            ecart_moyen=ecart_moyen,
            ecart_courant=ecart_courant,
            fenetre=fenetre,
        ))
    return resultats
