"""Plage horaire de collecte Google — réglable depuis l'interface (CLAUDE.md § 39).

La fenêtre `[heure_debut, heure_fin[` (heure locale Africa/Abidjan) borne
toute requête Google : hors de cette plage, aucun cycle de collecte ne tourne
et aucun créneau n'est attendu dans les agrégations (pas de report de valeur
de jour sur la nuit).

Source de vérité : la ligne `plage_collecte` de `parametres_application`
(migration 0018). Repli sur COLLECT_START_HOUR / COLLECT_END_HOUR tant que la
ligne n'existe pas — ou si la table n'a pas encore été migrée.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import ParametreApplication

logger = logging.getLogger("paa.collecte")

CLE_PLAGE_COLLECTE = "plage_collecte"


@dataclass(frozen=True)
class PlageCollecte:
    """Fenêtre horaire locale `[heure_debut, heure_fin[`, heures entières."""
    heure_debut: int
    heure_fin: int

    @property
    def nb_heures(self) -> int:
        return max(0, self.heure_fin - self.heure_debut)

    @property
    def est_24h(self) -> bool:
        return self.heure_debut == 0 and self.heure_fin == 24

    def contient(self, heure_locale: int) -> bool:
        return self.heure_debut <= heure_locale < self.heure_fin

    @property
    def libelle(self) -> str:
        """Format historique « 7h-19h » parsé par la barre de pilotage."""
        return f"{self.heure_debut}h-{self.heure_fin}h"


def valider_plage(heure_debut: int, heure_fin: int) -> PlageCollecte:
    """Lève ValueError si la plage est incohérente."""
    if not (0 <= heure_debut <= 23):
        raise ValueError("heure_debut doit être comprise entre 0 et 23.")
    if not (1 <= heure_fin <= 24):
        raise ValueError("heure_fin doit être comprise entre 1 et 24.")
    if heure_debut >= heure_fin:
        raise ValueError("heure_debut doit être strictement inférieure à heure_fin.")
    return PlageCollecte(heure_debut, heure_fin)


def _plage_par_defaut() -> PlageCollecte:
    settings = get_settings()
    try:
        return valider_plage(settings.collect_start_hour, settings.collect_end_hour)
    except ValueError:
        return PlageCollecte(0, 24)


def lire_plage_collecte(db: Session | None = None) -> PlageCollecte:
    """Plage de collecte en vigueur (base de données, sinon variables d'env)."""
    session = db or SessionLocal()
    try:
        ligne = session.get(ParametreApplication, CLE_PLAGE_COLLECTE)
        if ligne is None:
            return _plage_par_defaut()
        return valider_plage(
            int(ligne.valeur.get("heure_debut")), int(ligne.valeur.get("heure_fin")),
        )
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        # Table absente (migration 0018 non appliquée) ou valeur corrompue :
        # on ne bloque jamais la collecte, on retombe sur la configuration.
        logger.warning("Plage de collecte illisible en base (%s) — repli config.", exc)
        if db is not None:
            session.rollback()
        return _plage_par_defaut()
    finally:
        if db is None:
            session.close()


def enregistrer_plage_collecte(db: Session, plage: PlageCollecte) -> None:
    """UPSERT de la plage de collecte."""
    valeur = {"heure_debut": plage.heure_debut, "heure_fin": plage.heure_fin}
    ligne = db.get(ParametreApplication, CLE_PLAGE_COLLECTE)
    if ligne is None:
        db.add(ParametreApplication(cle=CLE_PLAGE_COLLECTE, valeur=valeur))
    else:
        ligne.valeur = valeur
    db.commit()
