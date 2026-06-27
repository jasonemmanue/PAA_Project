# PAA-Traverse — Guide de déploiement Railway

> Ce fichier documente toutes les leçons apprises lors du déploiement initial
> (P1→P6.1) et sert de référence pour tous les déploiements futurs.
> À lire AVANT chaque `railway up`.

---

## Rapport du déploiement initial (2026-06-18/19)

### Architecture déployée

| Composant | Service Railway | URL / Statut |
|-----------|----------------|--------------|
| Backend FastAPI | `backend` (Dockerfile) | `https://backend-production-6cbf.up.railway.app` ✅ |
| PostgreSQL | Plugin Railway | Interne Railway ✅ |
| Redis | Plugin Railway | Interne Railway ✅ |
| OSRM | Non déployé | Optionnel (voir § OSRM) |
| Frontend | À déployer en P4/P7 | Vercel ou Railway |

### État au 2026-06-19

```
✅ Backend en ligne — healthcheck /health → {"status":"ok"}
✅ Scheduler actif — 6 tronçons, 216 req/jour Google, 7h-19h Abidjan
✅ Migrations 0001 et 0002 appliquées
✅ 6 tronçons seedés (python -m app.seed_troncons)
✅ Code P1+P2+P3+P6.1 déployé
⏳ Migration 0003 à appliquer (evolution_indicateur + enum historique_paa_2025)
⏳ Import Excel à faire après migration 0003
⏳ OSRM non configuré (optionnel pour la collecte Google)
```

### Problèmes rencontrés et solutions

| # | Symptôme | Cause | Solution appliquée |
|---|----------|-------|-------------------|
| 1 | `ModuleNotFoundError: psycopg2` dans alembic | `alembic/env.py` retournait l'URL brute sans driver | `_normaliser_url()` appelée dans `_get_url()` de `env.py` |
| 2 | Alembic bloqué 7 min, healthcheck échoue | `pg_advisory_lock` non libéré entre déploiements | `alembic upgrade head` retiré du `startCommand` — à lancer manuellement |
| 3 | `${PORT}` non résolu, uvicorn ne démarre pas | `startCommand` exécuté sans shell | Enveloppé dans `sh -c '...'` |
| 4 | `RuntimeError: no running event loop` au démarrage | `AsyncIOScheduler.start()` appelé via `asyncio.to_thread()` | Appel direct dans le lifespan async (non threadé) |
| 5 | `OSRM_BASE_URL` requise bloquait le démarrage | `Field(...)` sans défaut dans config.py | Rendu optionnel `str \| None = Field(default=None)` |
| 6 | Migration 0003 absente du conteneur | Fichiers non-commités ignorés par `railway up` | `git add -A` AVANT `railway up` (voir § Règle critique) |
| 7 | `railway run python -m app.seed_troncons` échoue en local | `railway run` exécute en local sans les dépendances Python | Utiliser la **Console Railway** (onglet Console du service) |
| 8 | Healthcheck failure + log `Form data requires "python-multipart"` | FastAPI exige `python-multipart` dès qu'un endpoint utilise `UploadFile` / `Form` | Ajouter `python-multipart>=0.0.9` dans `backend/requirements.txt` |
| 9 | `railway run alembic ...` → `failed to resolve host postgres.railway.internal` | DNS interne Railway invisible depuis localhost | Lancer alembic depuis la **Console Railway** OU committer + redéployer pour que le `alembic upgrade head` soit appliqué dans le conteneur |

---

## Règle critique — railway up et git

> **`railway up` n'envoie que les fichiers trackés par git.**
> Il utilise `git ls-files` pour créer l'archive envoyée aux serveurs Railway.
> Un fichier non ajouté à git (`??` dans `git status`) sera ABSENT du conteneur.

**Avant chaque `railway up` :**
```powershell
git add -A          # ou git add <fichiers spécifiques>
git status          # vérifier qu'il n'y a plus de ?? pour les fichiers à déployer
railway up --service backend --detach
```

---

## Procédure de déploiement standard

### Déploiement normal (code existant modifié)

```powershell
# 1. Stager tous les fichiers modifiés
git add -A

# 2. (Optionnel mais recommandé) Committer
git commit -m "description du changement"

# 3. Déployer
railway up --service backend --detach

# 4. Suivre les logs
railway logs --service backend
```

**Healthcheck attendu (dans Deploy Logs) :**
```
Starting Container
INFO:     Started server process [N]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT
INFO:     100.64.x.x - "GET /health HTTP/1.1" 200 OK
```

---

### Déploiement avec nouvelle migration Alembic

> ⚠️ Ne JAMAIS mettre `alembic upgrade head` dans le `startCommand` :
> cela provoque un `pg_advisory_lock` persistant qui bloque le démarrage.

```powershell
# 1. Créer la migration localement
# (depuis backend/ avec l'env Docker actif)
# alembic revision --autogenerate -m "description"
# → modifier le fichier généré si besoin

# 2. Stager + déployer (inclut le nouveau fichier de migration)
git add -A
git commit -m "migration XXXX: description"
railway up --service backend --detach

# 3. Attendre que le déploiement soit vert (Online)
# Puis ouvrir la Console Railway → onglet Console

# 4. Appliquer la migration dans la Console Railway
alembic current      # vérifier la révision actuelle
alembic heads        # vérifier que la nouvelle migration est visible
alembic upgrade head # appliquer

# 5. Vérifier
alembic current      # doit montrer la nouvelle révision (head)
```

---

### Premier déploiement sur un nouveau projet Railway

```powershell
# Pré-requis : CLI installée, authentifié
railway login

# Lier le projet
railway link

# Configurer les variables (une fois)
railway variables set DATABASE_URL='${{Postgres.DATABASE_URL}}' --service backend
railway variables set REDIS_URL='${{Redis.REDIS_URL}}' --service backend
railway variables set GOOGLE_ROUTES_API_KEY='AIza...' --service backend
railway variables set API_SECRET_KEY='<40 caractères aléatoires>' --service backend
railway variables set ALLOWED_ORIGINS='https://VOTRE-FRONT.up.railway.app' --service backend
railway variables set TZ=Africa/Abidjan --service backend
railway variables set COLLECT_INTERVAL_MINUTES=20 --service backend
railway variables set COLLECT_START_HOUR=7 --service backend
railway variables set COLLECT_END_HOUR=19 --service backend
# OSRM optionnel — ne pas mettre si non disponible
# railway variables set OSRM_BASE_URL='https://...' --service backend

# Déployer
git add -A
railway up --service backend --detach

# Appliquer les migrations (Console Railway)
alembic upgrade head

# Seeder les tronçons (Console Railway)
python -m app.seed_troncons

# (Optionnel) Compléter les coordonnées via OSRM si disponible
# python -m app.complete_troncons
```

---

### Import des données Excel historiques (P6.1 — one-shot)

À faire UNE SEULE FOIS après la migration 0003.

```
1. Ouvrir https://backend-production-6cbf.up.railway.app/docs
2. Section "import données historiques"
3. POST /import/base-nettoyee → uploader Base_Nettoyee_PAA_Fev2025-1.xlsx
   → résultat attendu : nb_inseres=2016, agregation_recalculee=true
4. POST /import/evolution → uploader FEVRIER_2026.xlsx
   → résultat attendu : nb_inseres=72 (6 axes × 2 périodes × 2 type_jour)
```

Ou depuis la Console Railway :
```bash
python -m app.import_base_nettoyee /chemin/vers/Base_Nettoyee_PAA_Fev2025-1.xlsx
python -m app.import_evolution /chemin/vers/FEVRIER_2026.xlsx
```

---

## Configuration railway.toml (backend/)

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
# IMPORTANT : pas de "alembic upgrade head &&" ici — voir § migration
startCommand = "sh -c 'uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=*'"
healthcheckPath = "/health"
healthcheckTimeout = 300
numReplicas = 1
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**Points clés :**
- `sh -c '...'` est obligatoire pour que `$PORT` soit interprété par le shell
- `numReplicas = 1` obligatoire car APScheduler vit en mémoire (duplication = double collecte)
- `healthcheckTimeout = 300` donne 5 min au démarrage (suffisant pour la connexion DB)

---

## Endpoints de vérification post-déploiement

```bash
# Depuis n'importe où
curl https://backend-production-6cbf.up.railway.app/health
# → {"status":"ok"}

curl https://backend-production-6cbf.up.railway.app/collecte/status
# → {"actif":true,"prochaine_execution":"...","nb_troncons_actifs":6,...}

curl https://backend-production-6cbf.up.railway.app/carte/etat
# → état des 6 tronçons avec TTI et classe de congestion

# Swagger interactif
# https://backend-production-6cbf.up.railway.app/docs
```

---

## OSRM — options si nécessaire

OSRM n'est PAS requis pour la collecte Google. Il sert uniquement à
`complete_troncons.py` (polylines) et `/diag/osrm/{id}`.

**Option A — ngrok temporaire (démo uniquement) :**
```powershell
# OSRM tourne localement sur :5000
ngrok http 5000
# Injecter l'URL ngrok (change à chaque redémarrage)
railway variables set OSRM_BASE_URL='https://xxxx.ngrok-free.app' --service backend
```

**Option B — Oracle Cloud Free Tier (permanent) :**
Voir CLAUDE.md § 8.3 pour la procédure complète.

---

## Flux de données — comment la base grossit automatiquement

```
Railway (actif 24h/24, sans intervention)
─────────────────────────────────────────

  Chaque jour (7h00 → 19h00, Africa/Abidjan) :
  ┌─ 7h00 ──► Cycle collecte #1 : 6 appels Google → 6 lignes dans mesures
  ├─ 7h20 ──► Cycle collecte #2 : +6 lignes
  ├─ ...
  └─ 18h40 ──► Cycle collecte #36 : +6 lignes
               ─────────────────────────────
               Total : 216 mesures/jour

  Chaque nuit à 23h00 (Africa/Abidjan) :
  └─► Agrégation : recalcul de profils_horaires
      (moyenne, médiane, P95 par tronçon × jour_semaine × heure)

Progression :
  Jour 1   → ~216 mesures temps réel
  Jour 7   → ~1 512 mesures → profils fiables → prédicteur opérationnel
  Hackathon → données réelles + 2016 mesures Fév 2025 = base solide
```

**Sources dans la table mesures :**
- `source='google'` — robot temps réel (ne jamais filtrer)
- `source='historique_paa_2025'` — campagne terrain Fév 2025 (2016 lignes)
- Ne JAMAIS mélanger les deux sources dans les calculs TTI temps réel

---

## Checklist déploiement rapide

Avant chaque `railway up` :
- [ ] `git add -A` — fichiers non-trackés exclus du build
- [ ] Pas de secrets dans le code (vérifier `.env` dans `.gitignore`)
- [ ] Si nouvelle migration : elle sera dans le conteneur, l'appliquer via Console après déploiement
- [ ] `OSRM_BASE_URL` : ne pas mettre si OSRM non disponible (champ optionnel)
- [ ] `numReplicas = 1` dans railway.toml (APScheduler single-process)

Après chaque `railway up` :
- [ ] `curl .../health` → `{"status":"ok"}`
- [ ] `curl .../collecte/status` → `"actif":true`
- [ ] Si migration : Console → `alembic upgrade head`

---

## Déploiement du Frontend Next.js sur Railway (P7.2)

> Section ajoutée le **2026-06-27** — guide pas-à-pas pour déployer le frontend
> en application web accessible publiquement via Railway.

### Pré-requis

- Le backend Railway est déjà en ligne sur `https://backend-production-6cbf.up.railway.app`
- Le fichier `frontend/railway.toml` est commité (ajouté le 2026-06-27)
- La CLI Railway est installée et authentifiée (`railway login`)

### Architecture cible

```
Internet
   │
   ├── frontend.up.railway.app → Service "frontend" Railway (Next.js)
   │                                   │
   │                                   └── NEXT_PUBLIC_API_BASE_URL
   │                                         │
   └── backend-production-6cbf.up.railway.app → Service "backend" Railway (FastAPI)
```

### Étape 1 — Créer le service frontend dans Railway

**Via le tableau de bord Railway (recommandé) :**

1. Aller sur [railway.com](https://railway.com) → ouvrir le projet `empowering-embrace`
2. Cliquer **New Service** → **GitHub Repo**
3. Sélectionner le dépôt `PAA_Project`
4. **Root Directory** → taper `frontend` (important : le frontend est dans un sous-dossier)
5. Nommer le service `frontend`
6. Ne pas encore déployer — aller d'abord à l'étape 2 (variables)

**Via la CLI :**
```powershell
# Créer le service depuis le sous-dossier frontend
railway service create --name frontend
```

### Étape 2 — Configurer les variables d'environnement

> ⚠️ **Critique** : `NEXT_PUBLIC_*` sont des variables de **build-time** dans Next.js.
> Elles sont incorporées dans le JavaScript pendant `next build`.
> Elles DOIVENT être définies AVANT le premier déploiement.

Dans Railway → service `frontend` → onglet **Variables** → ajouter :

| Variable | Valeur |
|----------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://backend-production-6cbf.up.railway.app` |
| `NEXT_PUBLIC_DEFAULT_LANG` | `fr` |
| `NEXT_PUBLIC_TILE_URL` | `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` |
| `NEXT_PUBLIC_TILE_ATTRIBUTION` | `&copy; OpenStreetMap contributors` |
| `NODE_ENV` | `production` |

**Via la CLI (remplacer `--service frontend` par le nom exact) :**
```powershell
railway variables set NEXT_PUBLIC_API_BASE_URL="https://backend-production-6cbf.up.railway.app" --service frontend
railway variables set NEXT_PUBLIC_DEFAULT_LANG="fr" --service frontend
railway variables set NEXT_PUBLIC_TILE_URL="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" --service frontend
railway variables set NEXT_PUBLIC_TILE_ATTRIBUTION="&copy; OpenStreetMap contributors" --service frontend
railway variables set NODE_ENV="production" --service frontend
```

### Étape 3 — Configurer le domaine public

1. Dans Railway → service `frontend` → onglet **Settings** → section **Networking**
2. Cliquer **Generate Domain** → Railway attribue une URL `https://frontend-production-xxxx.up.railway.app`
3. **Copier cette URL** — elle sera nécessaire pour mettre à jour `ALLOWED_ORIGINS` côté backend

### Étape 4 — Autoriser le CORS côté backend

Le backend filtre les origines autorisées via `ALLOWED_ORIGINS`.
Une fois l'URL frontend connue, l'ajouter :

```powershell
# Remplacer https://frontend-production-xxxx.up.railway.app par l'URL réelle
railway variables set ALLOWED_ORIGINS="https://frontend-production-xxxx.up.railway.app,http://localhost:3000" --service backend
```

Redéployer le backend pour que la variable soit prise en compte :
```powershell
railway up --service backend --detach
```

### Étape 5 — Déclencher le premier déploiement frontend

**Via le tableau de bord :**
- Dans le service `frontend` → cliquer **Deploy** (ou attendre le déclenchement auto si lié à la branche `main`)

**Via la CLI :**
```powershell
railway up --service frontend --detach
```

Railway va automatiquement :
1. Détecter Next.js via Nixpacks
2. Installer les dépendances (`npm install`)
3. Builder (`npm run build`)
4. Démarrer (`npx next start -p $PORT`)

### Étape 6 — Vérification post-déploiement

```powershell
# Attendre que le déploiement soit "Online"
railway logs --service frontend

# Vérifier la page d'accueil
curl -I https://frontend-production-xxxx.up.railway.app/
# → HTTP/2 200

# Vérifier le splash screen + carte
# Ouvrir dans le navigateur — le splash HACKATONIA doit apparaître
```

### Étape 7 — Déploiements suivants

Pour tout changement du frontend :
```powershell
git add frontend/
git commit -m "feat: description du changement"
git push origin main
# Railway redéploie automatiquement via webhook GitHub
```

> Railway surveille la branche `main`. Chaque push déclenche un rebuild automatique
> du service frontend. Aucune commande `railway up` manuelle n'est nécessaire après
> la configuration initiale.

---

### Configuration `frontend/railway.toml` (référence)

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "npx next start -p $PORT"
healthcheckPath = "/"
healthcheckTimeout = 120
numReplicas = 1
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**Points clés :**
- `builder = "NIXPACKS"` : Railway détecte automatiquement Next.js, installe Node.js
- `startCommand = "npx next start -p $PORT"` : Railway injecte `$PORT` (différent de 3000)
- Sans ce `startCommand`, Next.js démarrerait sur le port 3000 et Railway ne pourrait pas router le trafic
- `numReplicas = 1` : un seul process (WebSocket + état en mémoire)
- Pas de `next.config.js` `output: 'standalone'` nécessaire avec Nixpacks

---

### Problèmes fréquents du frontend Railway

| # | Symptôme | Cause | Solution |
|---|----------|-------|----------|
| 1 | La carte n'affiche pas les données | `NEXT_PUBLIC_API_BASE_URL` incorrect ou manquant | Vérifier la variable dans Railway → **rebuild** obligatoire |
| 2 | Erreurs CORS dans la console | `ALLOWED_ORIGINS` backend ne contient pas l'URL frontend | Ajouter l'URL et redéployer le backend |
| 3 | Build échoue (`sharp` module) | Binaire natif incompatible | Railway compile `sharp` en natif — normal, attendre la fin du build |
| 4 | Timeout healthcheck | Next.js met >2 min à démarrer sur un plan hobby | Augmenter `healthcheckTimeout = 180` dans `railway.toml` |
| 5 | `NEXT_PUBLIC_API_BASE_URL` = `undefined` en prod | Variable ajoutée APRÈS le premier build | Re-déployer pour déclencher un nouveau build avec la variable |
| 6 | Page blanche au chargement | Hydratation SSR échouée | Vérifier les logs console navigateur — souvent une variable d'env manquante |

---

### Mise à jour ALLOWED_ORIGINS après déploiement frontend (récapitulatif)

```powershell
# 1. Récupérer l'URL publique du frontend
railway domain --service frontend
# → https://frontend-production-xxxx.up.railway.app

# 2. Mettre à jour ALLOWED_ORIGINS côté backend
railway variables set ALLOWED_ORIGINS="https://frontend-production-xxxx.up.railway.app,http://localhost:3000" --service backend

# 3. Redéployer le backend
railway up --service backend --detach
```


---

## Déploiement OSRM permanent sur Render

> Durée : ~30 min (compte Render + 1er démarrage pour l'indexation).
> Coût : plan **Standard** à **25 $/mois** (2 Go RAM indispensables pour OSRM)
> + **Persistent Disk 5 Go à 1,25 $/mois** = ~**26,25 $/mois** total.
> Le plan Starter (512 Mo) est insuffisant — l'indexation plante par OOM.

### Étape 1 — Créer un compte Render

Aller sur <https://render.com> → **Get Started for Free** → s'inscrire
(email ou GitHub). Ajouter une carte bancaire (pas de débit immédiat
pour les services Standard tant qu'on ne dépasse pas le plan).

### Étape 2 — Créer le service OSRM

1. Dashboard Render → **New → Web Service**
2. Choisir **"Deploy an existing image or a public Git repo"** →
   connecter le dépôt GitHub `jasonemmanue/PAA_Project`
3. Paramètres :
   - **Name** : `paa-osrm`
   - **Region** : `Frankfurt (EU Central)` — meilleure latence vers Abidjan
   - **Branch** : `main`
   - **Runtime** : `Docker`
   - **Dockerfile Path** : `./osrm-render/Dockerfile`
   - **Docker Context** : `./osrm-render`
   - **Instance Type** : `Standard` (2 Go RAM, 1 CPU) — **obligatoire**
4. Cliquer **Advanced** → **Add Disk** :
   - **Name** : `osrm-data`
   - **Mount Path** : `/data`
   - **Size** : `5 GB`
5. **Create Web Service**

### Étape 3 — Attendre le premier démarrage (10-20 min)

Au premier lancement, le script `entrypoint.sh` :
1. Télécharge `ivory-coast-latest.osm.pbf` depuis Geofabrik (~50 Mo)
2. Exécute `osrm-extract` + `osrm-partition` + `osrm-customize` (~10-15 min)
3. Lance `osrm-routed` sur le port 5000

Vous pouvez suivre les logs en temps réel dans l'onglet **Logs** du service.
Le service devient **Healthy** quand `osrm-routed` répond sur `/route/v1/...`.

Dès le 2ème démarrage, les fichiers indexés sont sur le Persistent Disk → 
démarrage en **< 10 secondes** sans re-téléchargement.

### Étape 4 — Récupérer l'URL publique

Une fois **Healthy** (pastille verte), l'URL publique est visible en haut
du dashboard Render, ex. :

```
https://paa-osrm.onrender.com
```

Tester avec curl :
```bash
curl "https://paa-osrm.onrender.com/route/v1/driving/-4.028563,5.328119;-3.98196,5.258705?overview=full" | head -c 200
# Réponse attendue : {"code":"Ok","routes":[{"geometry":"...
```

### Étape 5 — Connecter Railway au nouvel OSRM

```bash
railway variables set OSRM_BASE_URL=https://paa-osrm.onrender.com --service backend
```

Railway redémarre automatiquement le service après le `variables set`.

### Étape 6 — Regénérer les polylines (Console Railway)

```bash
python -m app.complete_troncons
# → [OK] T1 CARENA → Palm Beach : 939 chars
# → [OK] T2 Palm Beach → CARENA : 1081 chars
# ...
```

Hard refresh (`Ctrl+Shift+R`) sur la carte → les tracés suivent les vraies routes.

### Étape 7 — Workflow pour chaque nouveau tronçon ou sous-tronçon

1. Créer le tronçon/sous-tronçon via la page Administration
2. Sur la **Console Railway** du service backend :
   ```bash
   python -m app.complete_troncons
   ```
3. Hard refresh la carte → nouveau tracé routier visible

> OSRM reste en ligne en permanence sur Render — plus besoin de tunnel
> Cloudflare ni de machine locale allumée. L'URL Railway pointe vers
> Render de façon stable.

### Note sur le plan Render

| Plan | RAM | CPU | Prix/mois | Compatible OSRM |
|------|-----|-----|-----------|-----------------|
| Free | 512 Mo | 0.1 | 0 $ | ❌ OOM lors de l'indexation |
| Starter | 512 Mo | 0.5 | 7 $ | ❌ OOM lors de l'indexation |
| Standard | 2 Go | 1 | 25 $ | ✅ Recommandé |
| Pro | 4 Go | 2 | 85 $ | ✅ Confort (pas nécessaire) |

> Si le coût est un frein pour la démo, utiliser le tunnel Cloudflare ponctuel
> (procédure dans CLAUDE.md § 8.5.1) pour générer les polylines, puis couper.
> Les polylines persistées en base Railway restent affichées même sans OSRM.
