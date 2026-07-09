# FLUIDIS — Scraping, base de données et scripts CRUD pour la Console Railway

> Ce document explique le fonctionnement du scraping d'incidents, puis décrit
> la procédure complète pour écrire et exécuter des scripts Python de
> modification de la base de données depuis la **Console Railway**.

---

## Partie 1 — Principe du scraping d'incidents

### Vue d'ensemble

Le système scrappe automatiquement des articles de presse ivoirienne toutes les
**30 minutes**, via APScheduler. Il ne collecte que les articles décrivant un
incident de circulation **dans la zone portuaire d'Abidjan**.

```
Flux RSS (presse CI)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 1 — Récupération RSS                             │
│  httpx → GET flux RSS → feedparser → liste d'articles   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 2 — Double filtre obligatoire                    │
│                                                         │
│  Article retenu UNIQUEMENT SI :                         │
│   ✅ contient un mot-clé TYPE (nature de l'incident)    │
│      ET                                                 │
│   ✅ contient un mot-clé ZONE (lieu dans le périmètre)  │
│                                                         │
│  Exemple rejeté :                                       │
│   « Travaux à Yakassé-Feyassé » → TYPE ✅ / ZONE ❌    │
│                                                         │
│  Exemple accepté :                                      │
│   « Accident à Treichville » → TYPE ✅ / ZONE ✅       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 3 — Insertion en base (déduplication auto)       │
│  INSERT INTO incidents … ON CONFLICT (source_url) DO    │
│  NOTHING → un même article ne peut être inséré 2 fois   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼ (job suivant — toutes les 30 min)
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 4 — Enrichissement NLP                           │
│                                                         │
│  Pour chaque incident non enrichi :                     │
│   a) extraire_lieu()    → cherche un lieu dans le texte │
│      (dictionnaire de 60+ lieux du périmètre portuaire) │
│   b) classifier_type()  → accident / embouteillage /    │
│      route_barree / travaux / autre (par regex)         │
│   c) classifier_severite() → grave / moyen / mineur /   │
│      inconnu (par regex)                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 5 — Géocodage                                    │
│                                                         │
│  Si un lieu a été extrait :                             │
│   1. Cherche dans _COORDS_FIXES (60+ lieux hardcodés)   │
│      → réponse instantanée, aucun appel réseau          │
│   2. Si non trouvé → appel Nominatim OSM                │
│      → filtre bbox portuaire [5.20–5.37, -4.05–-3.96]  │
│   3. Si le point est hors bbox → lat/lon = NULL         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ÉTAPE 6 — Attribution du tronçon                       │
│  Haversine sur les 6+ tronçons actifs                   │
│  → troncon_id = tronçon dont une extrémité est          │
│    à moins de 300 m du point géocodé                    │
└─────────────────────────────────────────────────────────┘
```

### Mots-clés TYPE (exemples)

`accident`, `collision`, `accrochage`, `embouteillage`, `bouchon`,
`route barrée`, `travaux`, `camion`, `poids lourd`, `déviation`…

### Mots-clés ZONE (exemples)

`CARENA`, `Palm Beach`, `Treichville`, `pont HB`, `Houphouët`,
`Port d'Abidjan`, `Vridi`, `Zone 4`, `Toyota CFAO`, `Seamen`…

### Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `backend/app/sources/parsers/rss_parser.py` | Scraping RSS, double filtre, insertion |
| `backend/app/analyse/incidents_nlp.py` | Extraction NLP, géocodage, attribution tronçon |
| `backend/app/collecte/scheduler.py` | Job APScheduler toutes les 30 min |
| `backend/app/api/incidents.py` | Endpoints REST (GET, POST, export CSV) |

### Sources RSS actives

| Source | Fiabilité |
|--------|-----------|
| Fraternité Matin | 0.90 |
| Abidjan.net | 0.80 |
| AIP (Agence Ivoirienne de Presse) | 0.85 |
| RFI Afrique | 0.75 |

> **Note DNS Railway :** les sites ivoiriens (fraternitematin.ci, abidjan.net,
> koaci.com) sont souvent bloqués par le DNS des serveurs Railway (hébergés aux
> USA). Seules AIP et RFI passent de façon fiable. Vous pouvez ajouter de
> nouvelles sources via la page Incidents → « Gérer les sources ».

---

## Partie 2 — Procédure pour écrire un script CRUD pour la Console Railway

### Pourquoi cette approche ?

La **Console Railway** est un terminal interactif ouvert directement dans le
conteneur du service `backend`. Elle a accès à la base de données PostgreSQL
via les variables d'environnement Railway (`DATABASE_URL`, etc.).

On ne peut pas exécuter du SQL brut (`psql`) directement — il faut passer par
**Python + SQLAlchemy**, qui est déjà installé et configuré dans le conteneur.

### Structure de base d'un script

Tout script CRUD pour Railway suit ce patron :

```python
#!/usr/bin/env python3
"""Description courte du script — ce qu'il fait et pourquoi."""

from sqlalchemy import select, update, delete
from app.db.session import SessionLocal
from app.models.models import NomDuModele   # importer le(s) modèle(s) nécessaire(s)

def main():
    # 1. Ouvrir une session SQLAlchemy
    with SessionLocal() as db:

        # 2. Faire vos opérations CRUD
        # ...

        # 3. Sauvegarder (OBLIGATOIRE pour INSERT / UPDATE / DELETE)
        db.commit()

    print("Terminé.")

if __name__ == "__main__":
    main()
```

### Comment exécuter depuis la Console Railway

1. Aller sur [railway.app](https://railway.app) → votre projet → service **backend**
2. Cliquer sur l'onglet **Console**
3. Taper :

```bash
python -m scripts.nom_de_votre_script
```

> Le module doit se trouver dans `backend/scripts/nom_de_votre_script.py`
> et être **commité** et **déployé** avant d'être exécutable.

### Déployer un nouveau script

```powershell
# Windows PowerShell, depuis la racine du projet
git add backend/scripts/mon_script.py
git commit -m "feat: script CRUD mon_script"
cd backend
railway up --service backend
cd ..
```

Puis l'exécuter depuis la Console Railway.

---

## Partie 3 — Opérations CRUD par table (exemples complets)

### Modèles disponibles

```python
from app.models.models import (
    Troncon,           # axes et tronçons (carte)
    SousTroncon,       # tronçons codifiés (T1A, T2, etc.)
    Mesure,            # mesures de temps de parcours
    Incident,          # incidents détectés par le scraper
    TypesIncident,     # types d'incidents configurables
    SourceIncident,    # sources RSS configurables
    ReleveTerrain,     # relevés GPX terrain
    SegmentTerrain,    # segments GPX libres
)
```

### READ — Lire des données

```python
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.models import Incident

with SessionLocal() as db:
    # Lire tous les incidents actifs
    incidents = db.execute(
        select(Incident).where(Incident.actif.is_(True)).limit(10)
    ).scalars().all()

    for inc in incidents:
        print(f"[{inc.id}] {inc.titre[:60]} | {inc.type_incident} | {inc.severite}")
```

### CREATE — Insérer un enregistrement

```python
from app.db.session import SessionLocal
from app.models.models import SourceIncident
from datetime import datetime, timezone

with SessionLocal() as db:
    nouvelle_source = SourceIncident(
        nom="google_news_ci",
        libelle="Google News Côte d'Ivoire",
        url="https://news.google.com/rss/search?q=accident+Abidjan&hl=fr&gl=CI&ceid=CI:fr",
        type="rss",
        actif=True,
        fiabilite=0.70,
        ajoute_le=datetime.now(tz=timezone.utc),
    )
    db.add(nouvelle_source)
    db.commit()
    print(f"Source créée avec l'id {nouvelle_source.id}")
```

### UPDATE — Modifier un enregistrement

```python
from sqlalchemy import update
from app.db.session import SessionLocal
from app.models.models import Incident

with SessionLocal() as db:
    # Corriger le type d'un incident spécifique (id connu)
    db.execute(
        update(Incident)
        .where(Incident.id == 42)
        .values(type_incident="accident", severite="grave")
    )
    db.commit()
    print("Incident 42 mis à jour.")
```

### DELETE logique — Archiver (recommandé)

```python
from sqlalchemy import update
from app.db.session import SessionLocal
from app.models.models import SourceIncident

with SessionLocal() as db:
    # Désactiver une source (suppression logique — toujours préférer ça)
    db.execute(
        update(SourceIncident)
        .where(SourceIncident.nom == "koaci")
        .values(actif=False)
    )
    db.commit()
    print("Source koaci désactivée.")
```

### DELETE physique — Supprimer définitivement

```python
from sqlalchemy import delete
from app.db.session import SessionLocal
from app.models.models import Incident

with SessionLocal() as db:
    # Supprimer les incidents marqués comme doublon
    n = db.execute(
        delete(Incident).where(Incident.titre.like("[DOUBLON]%"))
    ).rowcount
    db.commit()
    print(f"{n} doublon(s) supprimé(s).")
```

---

## Partie 4 — Le script de démonstration en place dans le projet

Le fichier `backend/scripts/crud_demo.py` (déjà commité) illustre tous ces
cas avec une interface interactive. Vous pouvez le lancer depuis la Console
Railway :

```bash
# Afficher l'état général de la base
python -m scripts.crud_demo --action lire

# Ajouter une source RSS
python -m scripts.crud_demo --action ajouter-source \
    --nom "google_news_ci" \
    --libelle "Google News Côte d'Ivoire" \
    --url "https://news.google.com/rss/search?q=accident+Abidjan&hl=fr&gl=CI&ceid=CI:fr"

# Désactiver une source
python -m scripts.crud_demo --action desactiver-source --nom "koaci"

# Supprimer les doublons
python -m scripts.crud_demo --action supprimer-doublons

# Forcer l'enrichissement NLP des incidents non classifiés
python -m scripts.crud_demo --action enrichir

# Corriger le type d'un incident
python -m scripts.crud_demo --action corriger-incident --id 42 --type accident --severite grave

# Archiver un axe/tronçon par id
python -m scripts.crud_demo --action archiver-troncon --id 8

# Lister les types d'incidents configurés
python -m scripts.crud_demo --action lire-types
```

---

## Partie 5 — Modèle de script vierge

Copiez ce patron pour créer votre propre script de modification :

```python
"""Description : ce que ce script fait et pourquoi.

Utilisation (Console Railway du service backend) :
    python -m scripts.mon_script
"""

from __future__ import annotations

import sys
from sqlalchemy import select, update, delete
from app.db.session import SessionLocal
# Importez uniquement les modèles dont vous avez besoin :
# from app.models.models import Incident, Troncon, SourceIncident, ...


def main() -> int:
    with SessionLocal() as db:
        # ── Lecture ────────────────────────────────────────────────
        # lignes = db.execute(select(MonModele).where(...)).scalars().all()

        # ── Insertion ──────────────────────────────────────────────
        # db.add(MonModele(champ1=valeur1, champ2=valeur2))

        # ── Modification ───────────────────────────────────────────
        # db.execute(update(MonModele).where(...).values(champ=valeur))

        # ── Suppression logique ────────────────────────────────────
        # db.execute(update(MonModele).where(...).values(actif=False))

        # ── Suppression physique ───────────────────────────────────
        # n = db.execute(delete(MonModele).where(...)).rowcount

        db.commit()   # NE PAS OUBLIER — sans commit rien n'est sauvegardé

    print("Script terminé avec succès.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## Récapitulatif rapide

| Opération | SQLAlchemy | Commit requis ? |
|-----------|-----------|----------------|
| Lire | `db.execute(select(...)).scalars()` | Non |
| Insérer | `db.add(MonObjet(...))` | **Oui** |
| Modifier | `db.execute(update(...).values(...))` | **Oui** |
| Archiver | `update(...).values(actif=False)` | **Oui** |
| Supprimer | `db.execute(delete(...))` | **Oui** |

> **Règle d'or :** préférez toujours l'archivage (`actif=False`) à la
> suppression physique pour conserver l'historique des mesures et des
> incidents. La suppression physique n'est justifiée que pour les doublons
> avérés ou les données de test.
