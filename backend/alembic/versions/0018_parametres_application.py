"""Migration 0018 — Table parametres_application (réglages modifiables à chaud).

Stocke les réglages d'exploitation que l'opérateur change depuis l'interface
sans redéploiement. Premier usage : la plage horaire de collecte Google
(`plage_collecte`), hors de laquelle aucune requête n'est émise. Tant que la
clé n'existe pas, le backend retombe sur COLLECT_START_HOUR / COLLECT_END_HOUR.

Revision: 0018
Revises: 0017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parametres_application",
        sa.Column("cle", sa.String(64), primary_key=True),
        sa.Column(
            "valeur",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "maj_le",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("parametres_application")
