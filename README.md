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
4. [Ce qui est livré dans la phase P2](#4--ce-qui-est-livré-dans-la-phase-p2)
5. [Ce qui est livré dans la phase P3](#5--ce-qui-est-livré-dans-la-phase-p3)
6. [Démarrer le projet sur ma machine](#6--démarrer-le-projet-sur-ma-machine)
7. [Vérifier que tout fonctionne (tests)](#7--vérifier-que-tout-fonctionne-tests)
8. [Comprendre les fichiers du projet](#8--comprendre-les-fichiers-du-projet)
9. [Petit glossaire technique](#9--petit-glossaire-technique)
10. [Problèmes fréquents et solutions](#10--problèmes-fréquents-et-solutions)
11. [La suite du projet](#11--la-suite-du-projet)

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

### Ce qui n'est **pas encore** fait à la fin de P1 (et c'est normal)

- ❌ Pas de **collecte automatique** des mesures *(arrive en P2)*
- ❌ Pas d'**indicateurs** type FHWA *(arrive en P3)*
- ❌ Pas de **carte** ni de **graphiques** visibles *(arrive en P4)*
- ❌ Pas de **prédiction** ni de **recommandations** *(arrive en P6)*

---

## 4 · Ce qui est livré dans la phase P2

> **L'idée en une phrase :** un **robot** tourne tout seul en arrière-plan, demande
> à Google le temps de parcours actuel sur chaque tronçon, l'**écrit en base**,
> et chaque nuit **calcule des statistiques** réutilisables pour des graphiques.

### ✅ Un robot mesure le trafic tout seul, en continu

Un **ordonnanceur** (APScheduler — pensez à un « réveil programmable » à
l'intérieur du backend) se réveille **toutes les 20 minutes**, **entre 7h et
19h** (fuseau Abidjan), et fait ceci pour chacun des 6 tronçons :

1. **Appelle Google Routes** en parallèle pour récupérer le temps actuel.
2. **Calcule la vitesse moyenne** (= distance officielle ÷ durée).
3. **Insère une ligne** dans la table `mesures` avec l'horodatage exact.
4. **Si Google échoue** : nouvelle tentative au bout de 1 s, puis 2 s, puis 4 s
   (*backoff exponentiel*). Au bout de 3 essais infructueux, on insère quand
   même une ligne **vide** (`duree_trafic_s = NULL`) — c'est ce qu'on appelle
   un **« trou de mesure »** : on garde la preuve qu'on a tenté, **sans jamais
   inventer de valeur**.

### ✅ Le quota Google est respecté automatiquement

Google facture chaque appel. Le projet a un **plafond strict de 250 requêtes
par jour**. Le robot calcule au démarrage combien de requêtes il enverra et
**affiche un avertissement** si la configuration dépasse la limite :

| Intervalle | Plage horaire | Requêtes / jour | Statut       |
|-----------:|---------------|----------------:|--------------|
| 15 min     | 7h–19h        | **288**         | ❌ trop      |
| **20 min** | **7h–19h**    | **216**         | ✅ **utilisé** |
| 30 min     | 7h–19h        | 144             | ✅ marge confortable |

### ✅ Chaque nuit, les mesures deviennent des statistiques exploitables

Un **deuxième job** tourne tous les soirs à **23h00**. Il regroupe les mesures
par **(tronçon, jour de la semaine, heure)** et calcule pour chaque case :

- la **moyenne**, la **médiane**, le **min**, le **max**, le **P95**
  (le P95 = la valeur que 95 % des temps ne dépassent pas — utile pour
  « combien de temps faut-il prévoir pour arriver à l'heure presque toujours ? ») ;
- le **nombre de mesures** utilisées.

Le calcul est fait en parallèle sur **3 fenêtres glissantes** : **30, 60 et
90 jours**. Pourquoi 3 fenêtres ? Pour comparer la situation récente
(« 30 jours ») à la tendance plus ancienne (« 90 jours ») et détecter une
amélioration ou une dégradation du trafic.

### ✅ Les valeurs aberrantes sont détectées, mais conservées

Si une mesure est très loin des autres pour la même case (panne d'un capteur
Google, accident…), elle pourrait fausser les statistiques. On utilise la
**méthode IQR** (écart interquartile) : on prend les 25 % et 75 % du milieu de
la distribution, et toute valeur trop éloignée est **marquée comme aberrante**
(colonne `aberrante = true`). Elle reste en base (pour la traçabilité) mais est
**exclue du calcul des statistiques**.

### ✅ De nouvelles routes API pour piloter et exporter

| URL                                     | Ce qu'elle fait                                                              |
|-----------------------------------------|------------------------------------------------------------------------------|
| `POST /collecte/start`                  | Démarre le robot (si arrêté)                                                 |
| `POST /collecte/stop`                   | Arrête le robot proprement                                                   |
| `GET  /collecte/status`                 | Combien de mesures aujourd'hui, prochaine exécution, estimation du quota     |
| `POST /collecte/run-once`               | Déclenche **un cycle immédiat** (utile pour la démo ou les tests)            |
| `POST /agregation/run`                  | Force le recalcul des profils horaires (utile après import de données)       |
| `GET  /troncons/{id}/profil?jour=mardi` | Renvoie une **courbe heure-par-heure** prête à tracer pour un jour donné     |
| `GET  /export/mesures?format=csv\|xlsx` | Télécharge les mesures brutes (filtres : tronçon, plage de dates)            |
| `GET  /export/profils?format=xlsx`      | Télécharge un classeur Excel **heure × jour** par tronçon (1 feuille / axe)  |

### Ce qui n'est **pas encore** fait à la fin de P2

- ❌ Pas encore d'**indicateurs FHWA** (TTI, PTI, BTI) — *arrive en P3*
- ❌ Pas encore de **carte** ni de **graphiques** visibles — *arrive en P4*

---

## 5 · Ce qui est livré dans la phase P3

> **L'idée en une phrase :** les mesures brutes sont transformées en
> **indicateurs internationaux de congestion** (norme FHWA), et l'API est
> **restructurée** pour que le futur tableau de bord puisse l'utiliser
> facilement, **avec une mise à jour en temps réel**.

### ✅ Trois indicateurs normalisés calculés pour chaque tronçon

Les services routiers du monde entier utilisent les mêmes 3 indicateurs (norme
**FHWA** — *Federal Highway Administration*). Le projet les calcule
automatiquement :

| Indicateur | Nom complet            | Formule                              | Ce qu'il dit                                                            |
|------------|------------------------|--------------------------------------|-------------------------------------------------------------------------|
| **TTI**    | Travel Time Index      | moyenne ÷ temps de référence         | « En moyenne, on met **X fois** le temps fluide. »                      |
| **PTI**    | Planning Time Index    | P95 ÷ temps de référence             | « Pour être à l'heure 95 % du temps, il faut prévoir **X fois** le fluide. » |
| **BTI**    | Buffer Time Index      | (P95 − moyenne) ÷ moyenne            | « En plus de la moyenne, prévoyez **+X %** de marge tampon. »           |

Le **temps de référence** suit une cascade automatique :

1. **Médiane Google `duree_sans_trafic_s`** observée sur la fenêtre courante
   (ce que Google estime quand la route est complètement fluide).
2. ~~TomTom~~ — *retiré du projet (cf. CLAUDE.md § 2.5).*
3. **Repli déterministe** : distance officielle ÷ 50 km/h.

### ✅ Une classification de congestion immédiatement lisible

À partir du TTI, chaque tronçon reçoit une **classe** (les seuils sont
**configurables** dans `.env`, valeurs par défaut FHWA) :

| TTI               | Classe          | Couleur sur la carte | Interprétation                                    |
|-------------------|-----------------|----------------------|---------------------------------------------------|
| < 1,3             | **fluide**      | 🟢 vert (`#2ecc71`)  | « Trafic normal, pas de bouchon. »                |
| 1,3 ≤ TTI ≤ 2,0   | **dense**       | 🟠 orange (`#f39c12`)| « Circulation ralentie, présence visible de trafic. » |
| > 2,0             | **congestionné**| 🔴 rouge (`#e74c3c`) | « Bouchon sévère, double du temps normal ou plus. » |
| (sans mesure)     | indéterminé     | ⚪ gris (`#95a5a6`)  | « Pas de donnée pour conclure. »                  |

> **Exemple chiffré (Toyota CFAO → Palm Beach, mesure du 18/06/2026 à 19h19) :**
> Temps réel observé = **1 642 s** (≈ 27 min). Temps de référence Google = 580 s
> (≈ 9 min 40 s). **TTI = 1 642 / 580 = 2,83** → classe **congestionné** 🔴.
> Le véhicule met **presque 3 fois** le temps qu'il mettrait à vide.

### ✅ Détection automatique des heures de pointe

Une fonction parcourt les profils horaires et **identifie automatiquement**,
pour chaque jour de la semaine, les heures où la moyenne dépasse
`1,5 × temps_référence` (seuil configurable). Résultat utilisable directement
sous la forme `{ "jeudi": [7, 8, 17, 18, 19], "vendredi": [...] }`.

### ✅ L'API est restructurée en 7 routeurs métier (pour Swagger)

Avant P3, toutes les routes étaient mélangées. Maintenant l'API est organisée
**par domaine fonctionnel**, ce qui rend la page `/docs` beaucoup plus lisible :

| Routeur          | Rôle                                                                    |
|------------------|-------------------------------------------------------------------------|
| **`/troncons`**  | Référentiel + dernier état + indicateurs sur période                    |
| **`/mesures`**   | Accès transversal aux mesures (filtres : tronçon, source, dates, trous) |
| **`/profils`**   | Profils horaires (24 points heure-par-heure)                            |
| **`/indicateurs`** | Séries temporelles + heures de pointe                                 |
| **`/collecte`**  | Pilotage du robot                                                       |
| **`/export`**    | CSV / XLSX                                                              |
| **`/carte`**     | État temps réel prêt pour Leaflet                                       |

### ✅ Une route « état temps réel » prête à afficher sur une carte

`GET /carte/etat` renvoie en **un seul appel** tout ce dont le frontend Leaflet
aura besoin pour afficher la carte avec le bon code couleur :

```json
{
  "horodatage_utc": "2026-06-18T19:35:00+00:00",
  "fuseau_affichage": "Africa/Abidjan",
  "seuils": { "tti_dense": 1.3, "tti_congestionne": 2.0 },
  "couleurs": { "fluide": "#2ecc71", "dense": "#f39c12",
                "congestionne": "#e74c3c", "indetermine": "#95a5a6" },
  "nb_troncons": 6,
  "troncons": [{
    "id": 3,
    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
    "polyline": "qnj_@rinW...",
    "tti": 2.831,
    "classe_congestion": "congestionne",
    "couleur_etat": "#e74c3c",
    "derniere_mesure": { "duree_trafic_s": 1642, "source": "google", ... }
  }]
}
```

### ✅ Un WebSocket pour pousser les mises à jour en temps réel

L'adresse `ws://localhost:8081/ws/etat` est un **canal permanent** entre le
serveur et le navigateur (différent d'une URL classique). Le serveur **pousse
spontanément** un nouveau message à chaque cycle de collecte — pas besoin de
recharger la page. Concrètement :

1. À l'ouverture : le serveur envoie un message `{"type": "snapshot", ...}` avec
   l'état complet **immédiatement**.
2. Toutes les 20 minutes (quand le robot tourne) : tous les clients connectés
   reçoivent un message `{"type": "maj", "donnees": {...}}` avec le nouvel état.
3. Le client peut envoyer le texte `"ping"` à tout moment ; le serveur répond
   `"pong"` (utile pour vérifier que la connexion est encore vivante).

> **À quoi ça sert concrètement ?** Quand le frontend (P4) sera prêt, la carte
> changera de couleur **dès qu'une nouvelle mesure arrive**, sans que
> l'utilisateur ait à appuyer sur F5.

### Ce qui n'est **pas encore** fait à la fin de P3

- ❌ Pas encore de **carte** ni de **graphiques** visibles — *arrive en P4*
- ❌ Pas encore de **prédiction** ni de **recommandations** — *arrive en P6*

---

## 6 · Démarrer le projet sur ma machine

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

## 7 · Vérifier que tout fonctionne (tests)

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

### Test 5 — La documentation interactive (mise à jour P3)

Ouvre dans le navigateur : http://localhost:8081/docs

✅ Tu vois maintenant **7 routeurs métier en français** (`tronçons`, `mesures`,
`profils`, `indicateurs`, `collecte`, `agrégation`, `export`, `carte`, plus le
WebSocket `temps réel`), chaque endpoint avec son résumé, sa description, et
un bouton « Try it out » pour l'essayer en direct.

### Test 6 — Le robot de collecte tourne (phase P2)

```powershell
# Déclenche un cycle immédiat sans attendre 20 minutes
irm -Method Post http://localhost:8081/collecte/run-once
```

✅ Attendu :
```
etat        : cycle_execute
nb_succes   : 6
nb_trous    : 0
nb_troncons : 6
nb_appels   : 6
```

Puis dans DBeaver (ou via `docker compose exec db psql`) :
```sql
SELECT id, troncon_id, horodatage, source, duree_trafic_s, vitesse_moyenne_kmh
FROM mesures ORDER BY horodatage DESC LIMIT 10;
```
✅ Attendu : 6 nouvelles lignes, source `google`, durées non nulles.

### Test 7 — Le statut du robot s'affiche correctement (phase P2)

```powershell
irm http://localhost:8081/collecte/status
```

✅ Attendu : un objet avec `actif: true`, la `prochaine_execution`, la
`prochaine_agregation` (≈ 23h00) et les compteurs du jour
(`nb_mesures_total`, `nb_succes`, `nb_trous`).

### Test 8 — L'agrégation des profils horaires fonctionne (phase P2)

```powershell
irm -Method Post http://localhost:8081/agregation/run
```

✅ Attendu :
```
etat                  : agregation_executee
nb_mesures_analysees  : 6
nb_aberrantes         : 0
nb_buckets            : 6
nb_lignes_profils     : 18   ← 6 buckets × 3 fenêtres (30/60/90 j)
fenetres_jours        : {90, 60, 30}
```

### Test 9 — Les indicateurs FHWA sont calculés (phase P3)

```powershell
$r = irm "http://localhost:8081/troncons/3/indicateurs?periode=7j"
$r.snapshot
```

✅ Attendu : un objet contenant `tti`, `pti`, `bti`, `classe_congestion`
(`fluide` / `dense` / `congestionne`), `temps_reference_s`, et la
`source_temps_reference` (`google_freeflow_median` ou `vitesse_ref_50kmh`).

### Test 10 — L'état temps réel de la carte est prêt (phase P3)

```powershell
irm http://localhost:8081/carte/etat | ConvertTo-Json -Depth 4
```

✅ Attendu : un objet `troncons` contenant **6 entrées** avec, pour chacune :
géométrie (`polyline`, extrémités), `derniere_mesure`, `tti`,
`classe_congestion` et `couleur_etat` (code hexadécimal prêt pour Leaflet).

### Test 11 — Les exports Excel s'ouvrent correctement (phase P2)

```powershell
irm "http://localhost:8081/export/profils?fenetre_jours=30" -OutFile profils_30j.xlsx
Invoke-Item profils_30j.xlsx
```

✅ Attendu : Excel s'ouvre avec une feuille **« Synthèse »** + une feuille par
tronçon, chacune en format **heure × jour** (24 lignes × 7 colonnes) avec
moyenne en minutes.

### Test 12 — Le WebSocket pousse les mises à jour (phase P3)

Le plus simple si tu n'as pas d'outil WebSocket : ouvre la console de ton
navigateur (F12) sur `http://localhost:8081/docs` et tape :

```javascript
const ws = new WebSocket("ws://localhost:8081/ws/etat");
ws.onmessage = e => console.log(JSON.parse(e.data));
```

✅ Attendu : un premier message `{type: "snapshot", donnees: {...}}` arrive
immédiatement. Puis, si tu déclenches un cycle avec `irm -Method Post
http://localhost:8081/collecte/run-once` dans un autre terminal, un second
message `{type: "maj", donnees: {...}}` apparaît dans la console.

### Tout est OK ? Les phases P1, P2 et P3 sont validées ✅

---

## 8 · Comprendre les fichiers du projet

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
│   │   └── versions/      ← migrations 0001 (initial), 0002 (P2 : aberrante + fenetre)
│   └── app/
│       ├── main.py        ← point d'entrée de l'API (lifespan + 9 routeurs)
│       ├── core/config.py ← chargement des variables d'environnement + seuils P3
│       ├── db/session.py  ← connexion à PostgreSQL
│       ├── models/        ← description des 4 tables (en Python)
│       ├── sources/       ← appels vers Google Routes et OSRM
│       ├── collecte/      ← (P2) robot APScheduler de collecte
│       │   └── scheduler.py        ← jobs collecte (20 min) + agrégation (23h)
│       ├── agregation/    ← (P2) recalcul nocturne des profils horaires
│       │   └── profils.py          ← IQR + fenêtres glissantes 30/60/90 j
│       ├── analyse/       ← (P3) indicateurs FHWA
│       │   └── indicateurs.py      ← TTI, PTI, BTI, P95, heures de pointe
│       ├── etat/          ← (P3) construction d'états métier réutilisables
│       │   └── carte.py            ← état temps réel (HTTP + WebSocket)
│       ├── realtime/      ← (P3) diffusion temps réel
│       │   └── diffusion.py        ← singleton WebSocket broadcaster
│       ├── api/
│       │   ├── troncons.py    ← /troncons (liste + détail + indicateurs + mesures)
│       │   ├── mesures.py     ← (P2) /mesures (filtres transversaux)
│       │   ├── profils.py     ← (P2) /profils/troncons/{id}
│       │   ├── indicateurs.py ← (P3) /indicateurs/troncons/{id}/serie + heures-pointe
│       │   ├── collecte.py    ← (P2) /collecte/start /stop /status /run-once
│       │   ├── agregation.py  ← (P2) /agregation/run
│       │   ├── export.py      ← (P2) /export/mesures /export/profils
│       │   ├── carte.py       ← (P3) /carte/etat + WebSocket /ws/etat
│       │   └── diag.py        ← /diag/osrm /diag/google
│       ├── seed_troncons.py     ← script d'insertion des 6 tronçons
│       └── complete_troncons.py ← script qui complète les tracés via OSRM
├── frontend/              ← future page web (Next.js — vide en P1)
└── osrm-data/             ← cartes d'Abidjan pour le GPS interne
    ├── prepare.ps1        ← script de préparation OSRM (Windows)
    └── prepare.sh         ← script de préparation OSRM (Linux/macOS)
```

---

## 9 · Petit glossaire technique

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
| **APScheduler**      | Bibliothèque Python qui programme des tâches répétitives — c'est notre « réveil programmable » interne (P2).  |
| **Backoff exponentiel** | Stratégie de nouvelle tentative qui attend de plus en plus longtemps entre chaque essai (1 s, 2 s, 4 s…).  |
| **Trou de mesure**   | Ligne dans `mesures` avec `duree_trafic_s = NULL` : « on a essayé, ça n'a pas marché, on garde la trace » (P2). |
| **IQR**              | *Interquartile Range* — méthode statistique pour détecter les valeurs très éloignées du reste (P2).            |
| **Fenêtre glissante**| Période qui « avance » avec le temps : « les 30 derniers jours » se redéfinit chaque jour (P2).               |
| **Profil horaire**   | Statistiques agrégées par (tronçon, jour de la semaine, heure) — sert à dire « le mardi à 8h c'est X » (P2).  |
| **FHWA**             | *Federal Highway Administration* (USA) — agence dont les 3 indicateurs (TTI, PTI, BTI) sont la norme mondiale. |
| **TTI / PTI / BTI**  | Travel Time Index / Planning Time Index / Buffer Time Index — voir le tableau en section 5 (P3).               |
| **Temps de référence** | Temps « idéal » à comparer au temps réel : Google sans trafic (priorité) ou 50 km/h théorique (repli) (P3). |
| **WebSocket**        | Connexion permanente entre serveur et navigateur, par où le serveur peut **pousser** des messages (P3).        |
| **Polling**          | Inverse du WebSocket : le client demande régulièrement « du nouveau ? ». Plus lourd et plus lent.              |
| **Swagger / OpenAPI**| Page web auto-générée qui documente l'API et permet de tester chaque route depuis le navigateur (`/docs`).     |

---

## 10 · Problèmes fréquents et solutions

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

## 11 · La suite du projet

Sept phases au total (voir [CLAUDE.md § 4](CLAUDE.md#4-feuille-de-route--7-phases)).

| Phase | Objectif                                              | État               |
|:-----:|-------------------------------------------------------|--------------------|
| **P1**| **Fondations** (infrastructure, modèle de données)    | ✅ **terminée**    |
| **P2**| **Robot de collecte + agrégation nocturne + exports** | ✅ **terminée**    |
| **P3**| **Indicateurs FHWA + API restructurée + WebSocket**   | ✅ **terminée**    |
| P4    | Tableau de bord avec carte Leaflet et graphiques      | À démarrer         |
| P5    | Validation hebdomadaire par relevés GPS terrain       | À venir            |
| P6    | Prédiction du temps optimal d'acheminement            | À venir            |
| P7    | Tests, déploiement, support de présentation           | À venir            |

À la fin de P7, l'application sera prête pour la démo au jury du hackathon.
