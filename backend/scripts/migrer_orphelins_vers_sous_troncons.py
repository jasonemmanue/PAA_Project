"""Migration one-shot des tronçons orphelins vers `sous_troncons`.

Contexte : le refactor 2026-06-30 (commit 2458aff) a supprimé la notion de
« tronçon supplémentaire », mais deux entrées historiques étaient toujours
stockées dans la table `troncons` avec `est_axe=false` :

  - id 8 : AGL-Grand Moulin
  - id 9 : Palmbeach - Outillage Port

Elles doivent être des sous-tronçons codifiés (table `sous_troncons`),
rattachés à un axe parent.

Ce script est **idempotent** :
  - S'il n'y a plus d'orphelin est_axe=false actif, il ne fait rien.
  - Si un sous_troncon avec le code cible existe déjà pour l'axe cible,
    il saute la création et se contente d'archiver l'orphelin.

Mapping choisi pour la démo (peut être adapté via la constante ci-dessous) :
  - AGL-Grand Moulin           → axe 1 (CARENA → Palm Beach), code T1A
  - Palmbeach - Outillage Port → axe 2 (Palm Beach → CARENA), code T2A

Utilisation (Console Railway du service backend) :
    python -m scripts.migrer_orphelins_vers_sous_troncons
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.models import SousTroncon, Troncon
from app.sources.polyline import distance_cumulee_m, encoder_polyline


# ---------------------------------------------------------------------------
# Mapping orphelin → (troncon parent, code DEESP)
# Clé : nom exact de l'orphelin en base (insensible à la casse pour matcher)
# ---------------------------------------------------------------------------
MAPPING_ORPHELINS: dict[str, tuple[int, str]] = {
    "agl-grand moulin":            (1, "T1A"),
    "palmbeach - outillage port":  (2, "T2A"),
}


def _prochain_ordre(session: Session, troncon_id: int) -> int:
    ordre_max = session.execute(
        select(SousTroncon.ordre)
        .where(SousTroncon.troncon_id == troncon_id)
        .order_by(SousTroncon.ordre.desc())
        .limit(1)
    ).scalar_one_or_none()
    return (ordre_max or 0) + 1


def _migrer_un_orphelin(session: Session, orphelin: Troncon) -> str:
    cle = (orphelin.nom or "").strip().lower()
    if cle not in MAPPING_ORPHELINS:
        return f"[SKIP] id={orphelin.id} nom={orphelin.nom!r} : pas dans le mapping"

    parent_id, code = MAPPING_ORPHELINS[cle]
    parent = session.get(Troncon, parent_id)
    if parent is None or not parent.actif:
        return f"[ERR ] id={orphelin.id} : axe parent id={parent_id} introuvable/archivé"

    # Existe déjà ? (idempotence)
    existant = session.execute(
        select(SousTroncon).where(
            SousTroncon.troncon_id == parent_id,
            SousTroncon.code == code,
            SousTroncon.actif.is_(True),
        )
    ).scalar_one_or_none()
    if existant is not None:
        # On archive l'orphelin sans recréer le sous-tronçon
        if orphelin.actif:
            orphelin.actif = False
            return (
                f"[OK  ] id={orphelin.id} nom={orphelin.nom!r} : "
                f"sous_troncon {code} déjà présent sur axe {parent_id}, "
                f"orphelin archivé"
            )
        return (
            f"[SKIP] id={orphelin.id} : orphelin déjà archivé, "
            f"sous_troncon {code} déjà présent sur axe {parent_id}"
        )

    # Coordonnées de l'orphelin (obligatoires pour créer le sous_troncon)
    if (
        orphelin.lat_origine is None
        or orphelin.lon_origine is None
        or orphelin.lat_destination is None
        or orphelin.lon_destination is None
    ):
        return f"[ERR ] id={orphelin.id} : coordonnées incomplètes, migration impossible"

    points = [
        (orphelin.lat_origine, orphelin.lon_origine),
        (orphelin.lat_destination, orphelin.lon_destination),
    ]
    polyline = orphelin.polyline or encoder_polyline(points)
    distance = orphelin.distance_m or distance_cumulee_m(points)

    sous = SousTroncon(
        troncon_id=parent_id,
        code=code,
        nom_court=orphelin.nom,
        ordre=_prochain_ordre(session, parent_id),
        lat_debut=orphelin.lat_origine,
        lon_debut=orphelin.lon_origine,
        lat_fin=orphelin.lat_destination,
        lon_fin=orphelin.lon_destination,
        polyline=polyline,
        distance_m=int(distance),
        actif=True,
    )
    session.add(sous)
    # Archive l'orphelin — la table conserve la ligne pour l'historique
    orphelin.actif = False
    return (
        f"[OK  ] id={orphelin.id} nom={orphelin.nom!r} → "
        f"sous_troncon {code} sur axe {parent_id} ({parent.nom}), "
        f"orphelin archivé"
    )


def migrer() -> int:
    with SessionLocal() as session:
        orphelins = list(
            session.execute(
                select(Troncon).where(
                    Troncon.est_axe.is_(False),
                    Troncon.actif.is_(True),
                )
            ).scalars()
        )

        if not orphelins:
            print("[OK  ] Aucun orphelin actif — rien à faire.")
            return 0

        print(f"Orphelins actifs trouvés : {len(orphelins)}")
        for orphelin in orphelins:
            print(f"  - id={orphelin.id} nom={orphelin.nom!r}")

        for orphelin in orphelins:
            msg = _migrer_un_orphelin(session, orphelin)
            print(msg)

        session.commit()
        print("\nCommit effectué.")
        return 0


if __name__ == "__main__":
    sys.exit(migrer())
