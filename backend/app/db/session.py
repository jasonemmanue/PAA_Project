"""Initialisation du moteur SQLAlchemy et de la fabrique de sessions.

On utilise le driver synchrone psycopg v3 (psycopg[binary]) en P1.
L'accès asynchrone sera ajouté en P2 lorsque les endpoints de collecte en seront besoin.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles du projet."""
    pass


def _normaliser_url(url: str) -> str:
    """Convertit toute URL Postgres en forme `postgresql+psycopg://...` (psycopg v3).

    Les hébergeurs managés (Railway, Heroku, Render, …) exposent généralement
    `DATABASE_URL` sous l'une de ces formes :
      - `postgres://user:pwd@host:port/db`        → format historique
      - `postgresql://user:pwd@host:port/db`      → équivalent moderne
    SQLAlchemy + psycopg v3 attend `postgresql+psycopg://...`. On insère donc
    le driver explicite si manquant — opération idempotente côté local
    (notre `.env` contient déjà la forme complète).
    """
    if url.startswith("postgres://"):
        # Forme legacy → on remet le schéma moderne
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        # Préfixe schéma sans driver → on injecte `+psycopg`
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _get_database_url() -> str:
    """Retourne l'URL de connexion depuis les variables d'environnement.

    On lit directement os.environ plutôt que pydantic-settings pour que ce module
    puisse être importé par Alembic sans charger toute la pile FastAPI.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "La variable d'environnement DATABASE_URL n'est pas définie. "
            "Vérifier que backend/.env est bien chargé."
        )
    return _normaliser_url(url)


engine = create_engine(
    _get_database_url(),
    echo=False,           # Passer à True en développement pour voir le SQL généré
    pool_pre_ping=True,   # Invalide les connexions périmées avant usage
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """Générateur de session utilisé comme dépendance FastAPI (Depends)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
