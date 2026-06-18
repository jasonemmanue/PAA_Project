# PAA-Traverse

> Application web qui mesure **combien de temps il faut aujourd'hui** pour relier
> les trois axes routiers stratégiques du Port Autonome d'Abidjan, et qui en garde
> l'historique pour aider les gestionnaires à anticiper les bouchons.

*Projet réalisé pour un hackathon — client : Port Autonome d'Abidjan (PAA).*

---

## Sommaire

1. [À quoi ça sert ?](#1--à-quoi-ça-sert-)
2. [Comment ça marche en images](#2--comment-ça-marche-en-images)
3. [Ce qui est livré dans la phase P1](#3--ce-qui-est-livré-dans-la-phase-p1)
4. [Démarrer le projet sur ma machine](#4--démarrer-le-projet-sur-ma-machine)
5. [Vérifier que tout fonctionne (tests)](#5--vérifier-que-tout-fonctionne-tests)
6. [Comprendre les fichiers du projet](#6--comprendre-les-fichiers-du-projet)
7. [Petit glossaire technique](#7--petit-glossaire-technique)
8. [Problèmes fréquents et solutions](#8--problèmes-fréquents-et-solutions)
9. [La suite du projet](#9--la-suite-du-projet)

---

## 1 · À quoi ça sert ?

Le Port Autonome d'Abidjan veut **savoir en temps réel** combien de temps mettent
les camions et véhicules pour rejoindre la zone portuaire depuis trois points
stratégiques de la ville :

| Axe officiel | Distance | Temps idéal (à 50 km/h, sans bouchon) |
|---|---|---|
| **CARENA** *(Plateau)* ⇄ Pharmacie Palm Beach | ~14,9 km | ≈ 17 min 53 s |
| **Toyota CFAO** *(Treichville)* ⇄ Pharmacie Palm Beach | ~8,0 km | ≈ 9 min 36 s |
| **Agence SODECI** *(Zone 4)* ⇄ Pharmacie Palm Beach | ~8,3 km | ≈ 9 min 58 s |

Chaque axe est mesuré **dans les deux sens** (aller ET retour), car le trafic
est rarement le même selon qu'on entre ou qu'on sort de la zone du port. Cela
fait **6 tronçons** au total.

Le but final de l'application (à la fin des 7 phases) :

- afficher une **carte interactive** de ces 6 tronçons, colorés selon l'état du trafic ;
- montrer des **graphiques** de l'évolution des temps de parcours ;
- **identifier les heures et zones de congestion** récurrentes ;
- aider à **recommander un créneau optimal** pour acheminer une marchandise au port.

---

## 2 · Comment ça marche en images

```
                  ┌──────────────────────────────────────────┐
                  │   Tableau de bord (page web — phase P4)  │
                  │   Carte + graphiques + recommandations   │
                  └──────────────────────────────────────────┘
                                      ▲
                                      │  consulte
                                      │
                  ┌──────────────────────────────────────────┐
                  │   API du projet (notre backend FastAPI)  │
                  │   « Quel est le temps actuel sur l'axe » │
                  └──────────────────────────────────────────┘
                       ▲                              │
            consulte   │                              │ écrit chaque mesure
                       │                              ▼
        ┌─────────────────────┐         ┌─────────────────────────────────┐
        │  Google Routes API  │         │  Base de données PostgreSQL     │
        │  (trafic en direct) │         │  Historique de toutes les       │
        └─────────────────────┘         │  mesures faites sur chaque axe  │
                                        └─────────────────────────────────┘
                       ▲
                       │
       ┌─────────────────────────────────────────────────────────────────────┐
       │  OSRM (notre propre moteur de routage)                              │
       │  Sert à dessiner le tracé exact sur la carte et à calculer le       │
       │  "temps idéal" sans bouchon — comme un GPS hors-ligne.              │
       └─────────────────────────────────────────────────────────────────────┘
```

**En résumé :** un programme va régulièrement demander à Google « combien de
temps mettrais-je sur cet itinéraire maintenant ? », stocke la réponse en
base de données, et une page web vient lire ces données pour les afficher.

---

## 3 · Ce qui est livré dans la phase P1

Le projet est découpé en **7 phases** (cf. [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases)).
La phase **P1 — Fondations** est terminée. Voici ce que ça veut dire concrètement :

### ✅ L'infrastructure tourne

Cinq petits programmes (qu'on appelle des **services**) tournent côte à côte
dans des **conteneurs Docker** — pensez à Docker comme à des cartons
préemballés qui contiennent chacun un logiciel prêt à fonctionner, sans rien
casser sur votre PC.

| Service     | Rôle                                                              | URL d'accès                |
|-------------|-------------------------------------------------------------------|----------------------------|
| `db`        | Base de données PostgreSQL où on stocke tout l'historique         | `localhost:5432`           |
| `redis`     | Mémoire ultra-rapide pour les données temporaires (cache)         | `localhost:6379`           |
| `osrm`      | Notre GPS interne (sait dessiner les tracés sur la carte d'Abidjan) | `http://localhost:5000`  |
| `backend`   | Le cœur de l'application (l'API FastAPI en Python)                | `http://localhost:8081`    |
| `frontend`  | La future page web (Next.js, encore vide en P1)                   | `http://localhost:3000`    |

### ✅ Le schéma de la base de données est créé

Quatre tables ont été conçues pour stocker proprement les données du projet :

| Table              | Ce qu'elle contient                                                              |
|--------------------|----------------------------------------------------------------------------------|
| `troncons`         | Les 6 axes officiels avec leur tracé exact                                       |
| `mesures`          | Toutes les mesures de temps de parcours, datées (sera remplie en **P2**)         |
| `profils_horaires` | Statistiques par jour-de-semaine + heure (calculé chaque nuit en **P3**)         |
| `releves_terrain`  | Mesures faites manuellement avec un GPS sur le terrain (vérification en **P5**)  |

### ✅ Les 6 tronçons sont chargés et leur tracé dessiné

Au démarrage, on a inséré les 6 axes dans la table `troncons`. Puis on a
demandé à OSRM (notre GPS interne) de **calculer le tracé exact de chaque axe**
sur les routes d'Abidjan. Résultat dans la base :

| ID | Tronçon                                            | Distance (mesurée par OSRM) | Couleur sur la carte |
|----|----------------------------------------------------|-----------------------------|----------------------|
| 1  | CARENA → Pharmacie Palm Beach                      | 11 823 m                    | bleu foncé           |
| 2  | Pharmacie Palm Beach → CARENA                      | 13 163 m                    | bleu clair           |
| 3  | Toyota CFAO → Pharmacie Palm Beach                 | 10 003 m                    | rouge foncé          |
| 4  | Pharmacie Palm Beach → Toyota CFAO                 |  9 984 m                    | rouge clair          |
| 5  | Agence SODECI → Pharmacie Palm Beach               |  8 324 m                    | vert foncé           |
| 6  | Pharmacie Palm Beach → Agence SODECI               |  8 986 m                    | vert clair           |

> 💡 Les distances mesurées par OSRM peuvent différer des distances officielles
> car OSRM choisit l'itinéraire automobile réel, et c'est cet itinéraire-là que
> Google et toutes les autres sources mesurent. Cohérence avant tout.

### ✅ L'API expose 3 routes utiles

L'**API**, c'est une porte d'entrée qu'on appelle avec une URL. Voici celles
qui existent à ce stade :

| URL                                       | Ce qu'elle fait                                                  |
|-------------------------------------------|------------------------------------------------------------------|
| `GET /health`                             | Dit simplement « je suis en ligne » — sert au monitoring         |
| `GET /diag/osrm/{id}`                     | Donne la distance OSRM et le **temps idéal à 50 km/h** d'un tronçon |
| `GET /diag/google/{id}`                   | Donne le temps actuel **en direct** d'après Google (avec/sans trafic) |

> Une documentation interactive auto-générée est disponible : http://localhost:8081/docs

### ❌ TomTom a été retiré du projet

Au départ on prévoyait d'utiliser TomTom comme deuxième source de données.
Après test, **TomTom n'a aucune couverture cartographique à Abidjan** : ses
serveurs répondent « point trop éloigné du segment le plus proche » sur
chacun des 18 points testés. On l'a donc **complètement retiré** plutôt que
de garder du code inutile (cf. [CLAUDE.md § 2.5](CLAUDE.md)).

### Ce qui n'est **pas encore** fait (et c'est normal)

- ❌ Pas de **collecte automatique** des mesures (arrive en **P2**)
- ❌ Pas de **carte** ni de **graphiques** visibles (arrive en **P4**)
- ❌ Pas d'**indicateurs** type FHWA (arrive en **P3**)
- ❌ Pas de **prédiction** ni de **recommandations** (arrive en **P6**)

---

## 4 · Démarrer le projet sur ma machine

> ⚠️ Toutes les commandes ci-dessous se lancent dans **PowerShell sur Windows**,
> à la racine du projet (`C:\Users\…\paa-traverse`), pas dans un sous-dossier.

### Étape 1 — Installer Docker Desktop

[Télécharger Docker Desktop](https://www.docker.com/products/docker-desktop/) et
le lancer une fois. Tant que la baleine bleue 🐳 est visible en bas à droite,
Docker est prêt.

### Étape 2 — Préparer les fichiers de configuration

Le fichier `.env` contient les **mots de passe et clés d'API**. Il n'est pas
versionné sur Git pour des raisons de sécurité. On le crée à partir du modèle :

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Puis on ouvre `backend/.env` dans un éditeur et on remplit :

| Variable                | À quoi ça sert                                          | Comment l'obtenir                       |
|-------------------------|---------------------------------------------------------|-----------------------------------------|
| `POSTGRES_PASSWORD`     | Mot de passe de la base de données                      | Inventer un mot de passe long           |
| `API_SECRET_KEY`        | Clé secrète interne du backend                          | Inventer une chaîne aléatoire de ≥ 32 caractères |
| `GOOGLE_ROUTES_API_KEY` | Clé qui autorise l'appel à Google Routes                | Créer sur [Google Cloud Console](https://console.cloud.google.com/) |

> ⚠️ Si vous modifiez `POSTGRES_PASSWORD`, n'oubliez pas de le copier aussi
> dans la ligne `DATABASE_URL` juste en dessous.

### Étape 3 — Préparer le GPS interne OSRM (à faire une seule fois)

OSRM a besoin d'une carte d'Abidjan pour fonctionner. On télécharge donc la
carte d'OpenStreetMap, puis on la prépare en 3 étapes automatiquement :

```powershell
./osrm-data/prepare.ps1
```

Cette opération prend environ **3 à 5 minutes** (~80 Mo à télécharger). À la
fin, le dossier `osrm-data/` contiendra une dizaine de fichiers
`ivory-coast-latest.osrm.*`.

### Étape 4 — Démarrer les 5 services

```powershell
docker compose up -d
```

`-d` veut dire *"en arrière-plan"* (sinon vous verriez les logs défiler).

Vérifiez ensuite que tout est démarré :

```powershell
docker compose ps
```

Vous devez voir **5 services** en statut `running`. Les deux premiers (`db` et
`redis`) doivent en plus afficher `(healthy)`.

### Étape 5 — Initialiser la base de données

Trois commandes à enchaîner — elles sont idempotentes (on peut les relancer
sans casser quoi que ce soit) :

```powershell
# (a) Créer les 4 tables dans PostgreSQL
docker compose exec backend alembic upgrade head

# (b) Insérer les 6 tronçons officiels
docker compose exec backend python -m app.seed_troncons

# (c) Demander à OSRM de calculer le tracé exact de chaque tronçon
docker compose exec backend python -m app.complete_troncons
```

Si chaque commande affiche un message de succès (par ex. `6/6 tronçons mis à
jour`), **tout est prêt**.

---

## 5 · Vérifier que tout fonctionne (tests)

### Test 1 — Le backend répond

```powershell
curl http://localhost:8081/health
```

✅ Attendu : `{"status":"ok"}`

### Test 2 — La base contient bien les 6 tronçons avec leur tracé

```powershell
docker compose exec db psql -U paa -d paa_traffic -c "SELECT id, nom, distance_m FROM troncons ORDER BY id;"
```

✅ Attendu : 6 lignes (CARENA, Toyota CFAO, SODECI, et leurs retours respectifs).

### Test 3 — OSRM répond et calcule un temps de référence

```powershell
curl http://localhost:8081/diag/osrm/3
```

Le `3` = tronçon Toyota CFAO → Palm Beach (référence du cahier des charges).

✅ Attendu : un JSON contenant `"temps_reference_min_s":"12 min 00 s"` et la
distance en mètres. Ce **temps de référence** est calculé en imaginant qu'on
roule à 50 km/h **sans aucun bouchon** — c'est notre point de comparaison.

### Test 4 — Google Routes répond en direct

```powershell
curl http://localhost:8081/diag/google/3
```

✅ Attendu : un JSON avec :
- `duree_trafic_s` : temps **avec** le trafic actuel
- `duree_sans_trafic_s` : temps **si la route était fluide**
- `ratio_trafic_sur_fluide` : un nombre ≥ 1,0 indiquant la « densité du
  bouchon » (1,0 = aucun bouchon ; 1,5 = 50 % plus long que la normale).

### Test 5 — La documentation interactive

Ouvre dans le navigateur : http://localhost:8081/docs

✅ Tu vois 3 routes, chacune testable avec un bouton « Try it out ».

### Tout est OK ? La phase P1 est validée ✅

---

## 6 · Comprendre les fichiers du projet

```
paa-traverse/
├── README.md              ← ce fichier
├── CLAUDE.md              ← le contexte complet du projet (à lire en premier)
├── docker-compose.yml     ← définit les 5 services qui doivent tourner ensemble
├── backend/               ← le code Python (l'API)
│   ├── .env.example       ← modèle des secrets à remplir
│   ├── Dockerfile         ← recette pour fabriquer l'image Docker du backend
│   ├── requirements.txt   ← liste des bibliothèques Python utilisées
│   ├── alembic/           ← scripts de création/évolution de la base de données
│   └── app/
│       ├── main.py        ← point d'entrée de l'API
│       ├── core/config.py ← chargement des variables d'environnement
│       ├── db/session.py  ← connexion à PostgreSQL
│       ├── models/        ← description des 4 tables (en Python)
│       ├── api/diag.py    ← les routes /diag/osrm et /diag/google
│       ├── sources/       ← appels vers Google Routes et OSRM
│       ├── seed_troncons.py     ← script d'insertion des 6 tronçons
│       └── complete_troncons.py ← script qui complète les tracés via OSRM
├── frontend/              ← future page web (Next.js — vide en P1)
└── osrm-data/             ← cartes d'Abidjan pour le GPS interne
    ├── prepare.ps1        ← script de préparation OSRM (Windows)
    └── prepare.sh         ← script de préparation OSRM (Linux/macOS)
```

---

## 7 · Petit glossaire technique

| Mot                  | Explication simple                                                                                            |
|----------------------|---------------------------------------------------------------------------------------------------------------|
| **API**              | « Une porte d'entrée informatique » : un programme qui répond à des questions précises via des URL.           |
| **Backend**          | La partie « invisible » qui calcule et stocke les données (par opposition au **frontend**, la page web).      |
| **Conteneur Docker** | Un mini-ordinateur virtuel et isolé contenant un seul logiciel prêt à l'emploi.                               |
| **Base de données**  | Tableur géant et ultra-rapide qui garde des données structurées en tables.                                    |
| **PostgreSQL**       | La marque de base de données qu'on utilise (gratuite, populaire, fiable).                                     |
| **Migration**        | Une instruction qui modifie la structure de la base (ajout d'une table, d'une colonne…).                      |
| **Alembic**          | L'outil qui exécute les migrations dans l'ordre, sans casser les données existantes.                          |
| **Cache (Redis)**    | Stockage temporaire ultra-rapide pour éviter de refaire 100× le même calcul.                                  |
| **OSRM**             | Notre GPS hors-ligne (Open Source Routing Machine) : calcule des itinéraires sur la carte d'Abidjan.          |
| **Polyline**         | Représentation compacte d'un tracé sur la carte (une suite de lat/lon encodée en quelques caractères).        |
| **`localhost`**      | Votre propre ordinateur, vu depuis lui-même. Toutes les URL commençant par `localhost:` sont locales.         |
| **Port** (ex. 8081)  | Le « numéro de porte » d'un service sur votre ordinateur. `:8081` désigne le backend, `:3000` le frontend.    |
| **`.env`**           | Fichier texte contenant les secrets (mots de passe, clés). **Ne jamais le partager ni le mettre sur Git.**    |

---

## 8 · Problèmes fréquents et solutions

### « Le port 8000 est déjà utilisé / je n'arrive pas à démarrer le backend »

Windows réserve la plage 7981–8080 (vérifiable avec
`netsh interface ipv4 show excludedportrange protocol=tcp`). C'est pour ça
qu'on utilise **`:8081`** et non `:8000`. Si vous voyez encore une erreur de
port, regardez `docker-compose.yml` : la ligne `"8081:8000"` peut être changée
en `"8082:8000"` (puis adapter `frontend/.env.local`).

### « OSRM affiche `Required files are missing` »

Vous avez sauté l'étape 3 du démarrage. Lancez `./osrm-data/prepare.ps1` puis
`docker compose restart osrm`.

### « `service "backend" is not running` quand je tape `docker compose exec backend …` »

Le backend a planté ou n'a jamais démarré. Vérifiez avec :

```powershell
docker compose ps                       # est-il listé ?
docker compose logs backend --tail 30   # quel est le dernier message d'erreur ?
docker compose up -d backend            # tenter de le relancer
```

### « DNS / `No address associated with hostname` »

Docker Desktop sur Windows perd parfois le DNS après un `restart`. Le plus
fiable : `docker compose down` puis `docker compose up -d` (un redémarrage
complet rétablit le réseau).

### « Je suis dans `backend/` mais `docker compose up` ne marche pas »

Le fichier `docker-compose.yml` est à la **racine** du projet. Faites
`cd ..` pour remonter d'un dossier, puis relancez la commande.

### « Je veux tout effacer et repartir de zéro »

```powershell
docker compose down -v   # supprime les conteneurs ET les volumes (base de données vidée)
```

Puis recommencer depuis l'étape 4 du démarrage.

---

## 9 · La suite du projet

Sept phases au total (voir [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases)).

| Phase | Objectif                                              | État          |
|:-----:|-------------------------------------------------------|---------------|
| **P1**| **Fondations** (infrastructure, modèle de données)    | ✅ **terminée** |
| P2    | Robot qui collecte automatiquement les mesures        | À démarrer    |
| P3    | Calcul des indicateurs de congestion (FHWA)           | À venir       |
| P4    | Tableau de bord avec carte et graphiques              | À venir       |
| P5    | Validation hebdomadaire par relevés GPS terrain       | À venir       |
| P6    | Prédiction du temps optimal d'acheminement            | À venir       |
| P7    | Tests, déploiement, support de présentation           | À venir       |

À la fin de P7, l'application sera prête pour la démo au jury du hackathon.
