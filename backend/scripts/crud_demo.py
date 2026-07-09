"""Script CRUD de démonstration — toutes les tables principales de FLUIDIS.

Couvre : incidents, sources_incidents, types_incidents, troncons.
Peut être étendu à n'importe quelle table via le patron du § 5 de CRUD_CONSOLE.md.

Utilisation (Console Railway du service backend) :
    python -m scripts.crud_demo --action lire
    python -m scripts.crud_demo --action lire-types
    python -m scripts.crud_demo --action ajouter-source --nom xxx --libelle "Libellé" --url https://...
    python -m scripts.crud_demo --action desactiver-source --nom xxx
    python -m scripts.crud_demo --action corriger-incident --id 42 --type accident --severite grave
    python -m scripts.crud_demo --action supprimer-doublons
    python -m scripts.crud_demo --action enrichir
    python -m scripts.crud_demo --action archiver-troncon --id 8
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models.models import (
    Incident,
    SourceIncident,
    SousTroncon,
    Troncon,
    TypesIncident,
)


# ---------------------------------------------------------------------------
# Actions READ
# ---------------------------------------------------------------------------


def _lire(db) -> None:
    """Affiche un résumé de l'état général de la base."""
    nb_incidents = db.execute(select(func.count()).select_from(Incident)).scalar_one()
    nb_actifs = db.execute(
        select(func.count()).select_from(Incident).where(Incident.actif.is_(True))
    ).scalar_one()
    nb_troncons = db.execute(
        select(func.count()).select_from(Troncon).where(Troncon.actif.is_(True))
    ).scalar_one()
    nb_sous = db.execute(
        select(func.count()).select_from(SousTroncon).where(SousTroncon.actif.is_(True))
    ).scalar_one()
    nb_sources = db.execute(
        select(func.count()).select_from(SourceIncident).where(SourceIncident.actif.is_(True))
    ).scalar_one()

    print("─── État de la base FLUIDIS ───────────────────────────")
    print(f"  Incidents totaux          : {nb_incidents}")
    print(f"  Incidents actifs (<30j)   : {nb_actifs}")
    print(f"  Axes / tronçons actifs    : {nb_troncons}")
    print(f"  Sous-tronçons actifs      : {nb_sous}")
    print(f"  Sources RSS actives       : {nb_sources}")
    print()

    # 10 derniers incidents
    derniers = db.execute(
        select(Incident)
        .order_by(Incident.horodatage_collecte.desc())
        .limit(10)
    ).scalars().all()

    print("─── 10 derniers incidents collectés ───────────────────")
    for inc in derniers:
        horodatage = inc.horodatage_publication.strftime("%d/%m %H:%M") \
            if inc.horodatage_publication else "?"
        print(
            f"  [{inc.id:>5}] {horodatage}  {inc.type_incident or '?':>15}  "
            f"{inc.severite.value if inc.severite else '?':>7}  "
            f"{inc.titre[:55]}"
        )


def _lire_types(db) -> None:
    """Liste les types d'incidents configurés dans la DB."""
    types = db.execute(select(TypesIncident).order_by(TypesIncident.id)).scalars().all()
    if not types:
        print("Aucun type configuré en base. (Table types_incidents vide.)")
        return

    print("─── Types d'incidents configurés ──────────────────────")
    for t in types:
        actif = "✅" if t.actif else "❌"
        print(f"  {actif} [{t.id}] {t.slug:<20} → {t.libelle}")
        print(f"         regex : {t.regex[:80]}")


def _lire_sources(db) -> None:
    """Liste les sources RSS configurées."""
    sources = db.execute(select(SourceIncident).order_by(SourceIncident.id)).scalars().all()
    if not sources:
        print("Aucune source en base. (Table sources_incidents vide.)")
        return

    print("─── Sources RSS configurées ────────────────────────────")
    for s in sources:
        actif = "✅" if s.actif else "❌"
        print(f"  {actif} [{s.id}] {s.nom:<25} fiabilité={s.fiabilite:.2f}")
        print(f"         {s.url}")


# ---------------------------------------------------------------------------
# Actions CREATE
# ---------------------------------------------------------------------------


def _ajouter_source(db, nom: str, libelle: str, url: str) -> None:
    """Insère une nouvelle source RSS dans sources_incidents."""
    existante = db.execute(
        select(SourceIncident).where(SourceIncident.nom == nom)
    ).scalar_one_or_none()

    if existante is not None:
        print(f"[SKIP] La source '{nom}' existe déjà (id={existante.id}, actif={existante.actif}).")
        return

    nouvelle = SourceIncident(
        nom=nom,
        libelle=libelle,
        url=url,
        type="rss",
        actif=True,
        fiabilite=0.70,
        ajoute_le=datetime.now(tz=timezone.utc),
    )
    db.add(nouvelle)
    db.commit()
    print(f"[OK  ] Source '{nom}' créée (id={nouvelle.id}).")


# ---------------------------------------------------------------------------
# Actions UPDATE
# ---------------------------------------------------------------------------


def _desactiver_source(db, nom: str) -> None:
    """Désactive (archivage logique) une source RSS par son nom."""
    source = db.execute(
        select(SourceIncident).where(SourceIncident.nom == nom)
    ).scalar_one_or_none()

    if source is None:
        print(f"[ERR ] Source '{nom}' introuvable.")
        return

    if not source.actif:
        print(f"[SKIP] Source '{nom}' déjà inactive.")
        return

    source.actif = False
    db.commit()
    print(f"[OK  ] Source '{nom}' (id={source.id}) désactivée.")


def _corriger_incident(db, incident_id: int, type_inc: str | None, severite: str | None) -> None:
    """Corrige le type et/ou la sévérité d'un incident par son id."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        print(f"[ERR ] Incident id={incident_id} introuvable.")
        return

    print(f"[INFO] Avant : type={incident.type_incident}  sévérité={incident.severite}")

    valeurs = {}
    if type_inc:
        valeurs["type_incident"] = type_inc
    if severite:
        valeurs["severite"] = severite

    if not valeurs:
        print("[SKIP] Aucune valeur à modifier (--type et --severite non fournis).")
        return

    db.execute(
        update(Incident).where(Incident.id == incident_id).values(**valeurs)
    )
    db.commit()
    print(f"[OK  ] Incident id={incident_id} mis à jour : {valeurs}")


def _archiver_troncon(db, troncon_id: int) -> None:
    """Archive un axe ou sous-tronçon (suppression logique : actif=False)."""
    troncon = db.get(Troncon, troncon_id)
    if troncon is not None:
        if not troncon.actif:
            print(f"[SKIP] Axe id={troncon_id} ({troncon.nom!r}) déjà archivé.")
        else:
            troncon.actif = False
            db.commit()
            print(f"[OK  ] Axe id={troncon_id} ({troncon.nom!r}) archivé.")
        return

    sous = db.get(SousTroncon, troncon_id)
    if sous is not None:
        if not sous.actif:
            print(f"[SKIP] Sous-tronçon id={troncon_id} ({sous.code}) déjà archivé.")
        else:
            sous.actif = False
            db.commit()
            print(f"[OK  ] Sous-tronçon id={troncon_id} ({sous.code}) archivé.")
        return

    print(f"[ERR ] Aucun axe ni sous-tronçon trouvé avec id={troncon_id}.")


# ---------------------------------------------------------------------------
# Actions DELETE
# ---------------------------------------------------------------------------


def _supprimer_doublons(db) -> None:
    """Supprime définitivement les incidents marqués [DOUBLON]."""
    nb = db.execute(
        select(func.count()).select_from(Incident).where(Incident.titre.like("[DOUBLON]%"))
    ).scalar_one()

    if nb == 0:
        print("[OK  ] Aucun doublon à supprimer.")
        return

    print(f"[INFO] {nb} doublon(s) trouvé(s). Suppression en cours…")
    n = db.execute(
        delete(Incident).where(Incident.titre.like("[DOUBLON]%"))
    ).rowcount
    db.commit()
    print(f"[OK  ] {n} doublon(s) supprimé(s).")


# ---------------------------------------------------------------------------
# Action ENRICHIR (NLP + géocodage)
# ---------------------------------------------------------------------------


def _enrichir() -> None:
    """Déclenche l'enrichissement NLP des incidents non encore classifiés.

    Equivalent manuel du job APScheduler d'enrichissement.
    Utile quand on vient d'ajouter des incidents via import ou que le job
    a échoué.
    """
    from app.analyse.incidents_nlp import enrichir_incidents

    with SessionLocal() as db:
        nb = asyncio.run(enrichir_incidents(db))
        print(f"[OK  ] {nb} incident(s) enrichi(s) (NLP + géocodage + attribution tronçon).")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Script CRUD FLUIDIS — à exécuter depuis la Console Railway.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python -m scripts.crud_demo --action lire
  python -m scripts.crud_demo --action lire-types
  python -m scripts.crud_demo --action lire-sources
  python -m scripts.crud_demo --action ajouter-source --nom google_news_ci --libelle "Google News CI" --url https://...
  python -m scripts.crud_demo --action desactiver-source --nom koaci
  python -m scripts.crud_demo --action corriger-incident --id 42 --type accident --severite grave
  python -m scripts.crud_demo --action archiver-troncon --id 8
  python -m scripts.crud_demo --action supprimer-doublons
  python -m scripts.crud_demo --action enrichir
""",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "lire",
            "lire-types",
            "lire-sources",
            "ajouter-source",
            "desactiver-source",
            "corriger-incident",
            "archiver-troncon",
            "supprimer-doublons",
            "enrichir",
        ],
        help="Action à effectuer.",
    )
    parser.add_argument("--nom",     help="Nom de la source (slug unique).")
    parser.add_argument("--libelle", help="Libellé lisible de la source.")
    parser.add_argument("--url",     help="URL du flux RSS.")
    parser.add_argument("--id",      type=int, help="ID de l'enregistrement cible.")
    parser.add_argument("--type",    dest="type_inc",
                        choices=["accident", "embouteillage", "route_barree", "travaux", "autre"],
                        help="Type d'incident (pour --action corriger-incident).")
    parser.add_argument("--severite",
                        choices=["grave", "moyen", "mineur", "inconnu"],
                        help="Sévérité (pour --action corriger-incident).")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # L'enrichissement est asynchrone — traité à part
    if args.action == "enrichir":
        _enrichir()
        return 0

    with SessionLocal() as db:
        if args.action == "lire":
            _lire(db)

        elif args.action == "lire-types":
            _lire_types(db)

        elif args.action == "lire-sources":
            _lire_sources(db)

        elif args.action == "ajouter-source":
            if not args.nom or not args.libelle or not args.url:
                print("[ERR ] --nom, --libelle et --url sont obligatoires pour ajouter-source.")
                return 1
            _ajouter_source(db, args.nom, args.libelle, args.url)

        elif args.action == "desactiver-source":
            if not args.nom:
                print("[ERR ] --nom est obligatoire pour desactiver-source.")
                return 1
            _desactiver_source(db, args.nom)

        elif args.action == "corriger-incident":
            if args.id is None:
                print("[ERR ] --id est obligatoire pour corriger-incident.")
                return 1
            _corriger_incident(db, args.id, args.type_inc, args.severite)

        elif args.action == "archiver-troncon":
            if args.id is None:
                print("[ERR ] --id est obligatoire pour archiver-troncon.")
                return 1
            _archiver_troncon(db, args.id)

        elif args.action == "supprimer-doublons":
            _supprimer_doublons(db)

    return 0


if __name__ == "__main__":
    sys.exit(main())
