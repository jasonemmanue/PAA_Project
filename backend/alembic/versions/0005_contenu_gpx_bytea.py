"""P5 — ajout colonne `contenu_gpx` BYTEA dans releves_terrain.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-21

Pourquoi : sur Railway, le système de fichiers du conteneur est **éphémère**
par défaut. Toute redéploiement (push code) vide le disque, donc les `.gpx`
stockés dans `/app/data/gpx/` disparaissent — alors que la table
`releves_terrain` conserve leur chemin → l'endpoint `/terrain/releves/{id}/gpx`
renvoie 404 sur tous les anciens uploads.

Solution : stocker le contenu binaire du `.gpx` directement dans la DB,
colonne `contenu_gpx`. Quelques Mo pour 6-12 fichiers, négligeable, mais
survit à tous les redéploiements.

`fichier_gpx` conserve son rôle (nom de fichier + chemin disque pour le dev
local), mais le serving HTTP passe en priorité par `contenu_gpx`.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "releves_terrain",
        sa.Column("contenu_gpx", sa.LargeBinary, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("releves_terrain", "contenu_gpx")
