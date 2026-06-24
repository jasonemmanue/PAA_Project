"""Migration 0012 — Colonne fiabilite_source sur la table incidents (P8.5).

Ajoute un score de fiabilité (0..1) initialisé selon la source de scraping.

Revision: 0012
Revises: 0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("fiabilite_source", sa.Float, nullable=True),
    )
    # Initialisation des lignes existantes selon la source
    op.execute("""
        UPDATE incidents
        SET fiabilite_source = CASE source_nom
            WHEN 'fraternite_matin' THEN 0.9
            WHEN 'abidjan_net'      THEN 0.8
            WHEN 'koaci'            THEN 0.75
            WHEN 'linfodrome'       THEN 0.7
            WHEN 'soir_info'        THEN 0.7
            ELSE 0.5
        END
    """)


def downgrade() -> None:
    op.drop_column("incidents", "fiabilite_source")
