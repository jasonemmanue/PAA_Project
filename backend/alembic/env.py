"""Configuration de l'environnement Alembic pour PAA-Traverse.

Ce module est exécuté par Alembic lors de chaque commande de migration.
Il charge l'URL de la base depuis DATABASE_URL (variable d'environnement)
et expose les métadonnées des modèles pour l'autogénération de migrations.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ajout du dossier backend/ au PYTHONPATH pour que `app.*` soit importable
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Import de la Base déclarative et des modèles (obligatoire pour --autogenerate)
# ---------------------------------------------------------------------------
from app.db.session import Base  # noqa: E402
import app.models.models  # noqa: E402, F401 — enregistre les modèles dans Base.metadata

# ---------------------------------------------------------------------------
# Configuration Alembic standard
# ---------------------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Retourne l'URL de connexion depuis l'environnement.

    Priorité : variable d'environnement DATABASE_URL > valeur de alembic.ini.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    raise RuntimeError(
        "DATABASE_URL introuvable. "
        "Définir la variable dans backend/.env ou dans alembic.ini."
    )


def run_migrations_offline() -> None:
    """Mode hors-ligne : génère le SQL sans se connecter à la base."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode en ligne : se connecte à la base et applique les migrations."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
