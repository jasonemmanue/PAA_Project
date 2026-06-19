# =========================================================================
# Procfile de secours — utilisé si Railway ignore railway.toml ou pour
# d'autres PaaS compatibles (Heroku, Render avec mode Procfile, etc.).
# -------------------------------------------------------------------------
# Note : ce Procfile suppose que Root Directory = "backend".
# Le port $PORT est injecté par la plateforme hôte au runtime.
# =========================================================================

# Job web — démarre Uvicorn après application des migrations Alembic.
web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=*

# Job release (Heroku-style) — exécuté avant chaque release.
# Railway n'utilise pas ce hook, mais il est repris par d'autres PaaS.
release: alembic upgrade head
