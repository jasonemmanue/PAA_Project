"""Assemblage des segments terrain en temps de traversée par tronçon.

Un segment terrain couvre une SOUS-PORTION du tracé officiel (entre deux
landmarks intermédiaires comme "CARENA→GMA" ou "DGI→Terminus 19").
Ce module regroupe les segments d'une session et reconstitue le temps
total de traversée pour chaque tronçon officiel.

### Précision progressive

  Session 1  → 1 estimation par tronçon
  Session N  → moyenne de N estimations → convergence progressive
  Couverture → distance couverte / distance totale du tronçon (%)

### Principe aller = retour (approximation initiale)

  Quand un tronçon n'a pas de segments directs mais que son miroir
  (sens opposé) en a, on utilise le temps du miroir comme estimation.
  Cf. CLAUDE.md § 4.9.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import SegmentTerrain, Troncon
from app.terrain.decoupage import distance_haversine_m


logger = logging.getLogger("paa.terrain.assemblage")


# Identifiants des tronçons miroirs (aller ↔ retour par axe officiel)
# Supposé stable : les 6 tronçons officiels seront toujours id 1-6 d'après seed_troncons.
TRONCONS_MIROIRS: dict[int, int] = {
    1: 2,  # CARENA→Palm Beach ↔ Palm Beach→CARENA
    2: 1,
    3: 4,  # Toyota→Palm Beach ↔ Palm Beach→Toyota
    4: 3,
    5: 6,  # SODECI→Palm Beach ↔ Palm Beach→SODECI
    6: 5,
}


@dataclass
class EstimationSession:
    """Estimation du temps de traversée pour une session terrain donnée."""
    date_session: date
    session_id: str | None
    nb_segments: int
    duree_totale_s: int           # somme des durées des segments
    distance_couverte_m: float    # distance GPS cumulée des segments
    distance_troncon_m: int       # distance officielle du tronçon
    source: str                   # 'segments_directs' ou 'miroir_aller_retour'

    @property
    def couverture_pct(self) -> float:
        """Pourcentage de la distance du tronçon couvert par les segments."""
        if self.distance_troncon_m <= 0:
            return 0.0
        return min(100.0, self.distance_couverte_m / self.distance_troncon_m * 100.0)


@dataclass
class ResumeTempsTraversee:
    """Résumé consolidé des temps de traversée pour un tronçon."""
    troncon_id: int
    troncon_nom: str
    distance_m: int
    sessions: list[EstimationSession] = field(default_factory=list)

    @property
    def nb_sessions(self) -> int:
        return len(self.sessions)

    @property
    def temps_moyen_s(self) -> float | None:
        if not self.sessions:
            return None
        return sum(s.duree_totale_s for s in self.sessions) / len(self.sessions)

    @property
    def temps_min_s(self) -> float | None:
        if not self.sessions:
            return None
        return float(min(s.duree_totale_s for s in self.sessions))

    @property
    def temps_max_s(self) -> float | None:
        if not self.sessions:
            return None
        return float(max(s.duree_totale_s for s in self.sessions))

    @property
    def couverture_moyenne_pct(self) -> float:
        if not self.sessions:
            return 0.0
        return sum(s.couverture_pct for s in self.sessions) / len(self.sessions)

    @property
    def confiance(self) -> float:
        """
        Indice de confiance 0.0–1.0 combinant nombre de sessions et couverture.
          - 4 sessions à 100 % = confiance 1.0
          - 1 session à 64 % = confiance ≈ 0.16
        """
        if not self.sessions:
            return 0.0
        cov = self.couverture_moyenne_pct / 100.0
        nb = min(self.nb_sessions, 8)
        return round(cov * (nb / 8), 3)


def assembler_pour_troncon(
    db: Session,
    troncon_id: int,
    *,
    appliquer_miroir: bool = True,
    date_min: date | None = None,
    date_max: date | None = None,
) -> ResumeTempsTraversee:
    """Calcule les temps de traversée d'un tronçon depuis les segments terrain.

    Algo :
    1. Récupère tous les segments assignés au tronçon (filtre optionnel par date).
    2. Groupe par (date_session, session_id).
    3. Pour chaque groupe, somme les durées → une EstimationSession.
    4. Si aucun segment et `appliquer_miroir=True`, tente le tronçon miroir.
    """
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise ValueError(f"Tronçon {troncon_id} introuvable.")

    resume = ResumeTempsTraversee(
        troncon_id=troncon_id,
        troncon_nom=troncon.nom,
        distance_m=troncon.distance_m,
    )

    # --- Segments directs ---
    sessions_directes = _grouper_sessions(db, troncon_id, date_min, date_max)
    for estimation in sessions_directes:
        estimation.source = "segments_directs"
    resume.sessions.extend(sessions_directes)

    # --- Miroir aller/retour si aucun segment direct ---
    if not resume.sessions and appliquer_miroir:
        miroir_id = TRONCONS_MIROIRS.get(troncon_id)
        if miroir_id:
            sessions_miroir = _grouper_sessions(db, miroir_id, date_min, date_max)
            for estimation in sessions_miroir:
                estimation.source = "miroir_aller_retour"
                # Le tronçon miroir peut avoir une distance différente
                estimation.distance_troncon_m = troncon.distance_m
            resume.sessions.extend(sessions_miroir)
            if sessions_miroir:
                logger.info(
                    "Tronçon %d : estimation par miroir depuis tronçon %d (%d sessions)",
                    troncon_id, miroir_id, len(sessions_miroir),
                )

    return resume


def assembler_tous_troncons(
    db: Session,
    *,
    appliquer_miroir: bool = True,
    date_min: date | None = None,
    date_max: date | None = None,
) -> list[ResumeTempsTraversee]:
    """Calcule les temps de traversée pour tous les tronçons actifs."""
    troncons = db.execute(
        select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
    ).scalars().all()

    return [
        assembler_pour_troncon(
            db, t.id,
            appliquer_miroir=appliquer_miroir,
            date_min=date_min,
            date_max=date_max,
        )
        for t in troncons
    ]


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _grouper_sessions(
    db: Session,
    troncon_id: int,
    date_min: date | None,
    date_max: date | None,
) -> list[EstimationSession]:
    """Récupère et groupe les segments d'un tronçon par (date_session, session_id)."""
    q = (
        select(SegmentTerrain)
        .where(
            SegmentTerrain.troncon_id == troncon_id,
            SegmentTerrain.source_reelle.is_(True),
        )
        .order_by(SegmentTerrain.date_session, SegmentTerrain.horodatage_debut)
    )
    if date_min:
        q = q.where(SegmentTerrain.date_session >= date_min)
    if date_max:
        q = q.where(SegmentTerrain.date_session <= date_max)

    segments: list[SegmentTerrain] = db.execute(q).scalars().all()

    # Récupère la distance officielle du tronçon
    troncon = db.get(Troncon, troncon_id)
    distance_troncon_m = troncon.distance_m if troncon else 1

    # Groupe par (date_session, session_id)
    groupes: dict[tuple, list[SegmentTerrain]] = {}
    for seg in segments:
        cle = (seg.date_session, seg.session_id)
        groupes.setdefault(cle, []).append(seg)

    estimations: list[EstimationSession] = []
    for (date_sess, sess_id), segs in sorted(groupes.items()):
        duree_totale = sum(s.duree_s for s in segs)
        dist_couverte = sum(s.distance_m or 0.0 for s in segs)
        if duree_totale <= 0:
            continue
        estimations.append(EstimationSession(
            date_session=date_sess,
            session_id=sess_id,
            nb_segments=len(segs),
            duree_totale_s=duree_totale,
            distance_couverte_m=dist_couverte,
            distance_troncon_m=distance_troncon_m,
            source="segments_directs",
        ))

    return estimations


def calculer_distance_trace(lat_pts: list[float], lon_pts: list[float]) -> float:
    """Calcule la distance cumulée d'une liste de points GPS, en mètres."""
    total = 0.0
    for i in range(len(lat_pts) - 1):
        total += distance_haversine_m(
            lat_pts[i], lon_pts[i], lat_pts[i + 1], lon_pts[i + 1]
        )
    return total
