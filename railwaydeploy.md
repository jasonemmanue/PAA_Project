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
