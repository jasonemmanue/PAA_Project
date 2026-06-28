"""Migration 0013 — Distinction axes / tronçons.

Ajoute la colonne `est_axe` à la table `troncons` :
  - True  → axe officiel (3 axes × 2 sens = 6 lignes IDs 1-6 initiales)
  - False → tronçon supplémentaire ajouté via la page Administration

Cette distinction est cosmétique (UI + chatbot) — le pipeline de collecte
et d'analyse traite toutes les entrées actives de façon identique. Elle
permet à l'opérateur de réserver le terme « axe » aux 3 axes DEESP du
cahier des charges.

Initialisation :
  - IDs ≤ 6 → est_axe = True
  - IDs > 6 → est_axe = False (cas des deux entrées supplémentaires
    ajoutées en démo le 2026-06-28)

Revision: 0013
Revises: 0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colonne nullable d'abord pour permettre la migration sans valeur
    op.add_column(
        "troncons",
        sa.Column("est_axe", sa.Boolean(), nullable=True),
    )
    # Initialisation : axes officiels = ids ≤ 6
    op.execute("UPDATE troncons SET est_axe = TRUE  WHERE id <= 6")
    op.execute("UPDATE troncons SET est_axe = FALSE WHERE id >  6")
    # Désormais NOT NULL avec default True (futurs INSERT sans précision
    # → axe officiel)
    op.alter_column("troncons", "est_axe", nullable=False, server_default=sa.text("true"))


def downgrade() -> None:
    op.drop_column("troncons", "est_axe")
