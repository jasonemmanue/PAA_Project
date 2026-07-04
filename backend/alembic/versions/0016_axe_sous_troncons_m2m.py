"""Migration 0016 — Multi-parent : table de jonction axe_sous_troncons.

Permet à un même sous-tronçon codifié (ex. un pont commun) d'appartenir à
PLUSIEURS axes parents sans être dupliqué. Évite la redondance : un
sous-tronçon partagé (pont, carrefour) apparaît sous chaque axe qui l'utilise
sans double collecte Google.

Changes :
  1. Crée la table axe_sous_troncons(axe_id, sous_troncon_id, ordre).
  2. Backfill : pour chaque ligne existante de sous_troncons, insère une
     ligne dans axe_sous_troncons avec axe_id = troncon_id (parent principal).
  3. La colonne sous_troncons.troncon_id reste — elle représente désormais
     le "parent principal" (pour routing URL et rétro-compat). Toute la
     logique métier lit depuis la table de jonction pour supporter le
     multi-parent.

Revision: 0016
Revises: 0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "axe_sous_troncons",
        sa.Column(
            "axe_id",
            sa.Integer,
            sa.ForeignKey("troncons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sous_troncon_id",
            sa.Integer,
            sa.ForeignKey("sous_troncons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Ordre du sous-tronçon dans le parcours de CE parent (peut différer
        # d'un parent à l'autre — le même pont peut être 3e sur l'axe 1 et
        # 1er sur l'axe 4).
        sa.Column("ordre", sa.Integer, nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint(
            "axe_id", "sous_troncon_id",
            name="pk_axe_sous_troncons",
        ),
    )

    # Index pour accélérer la lecture "tous les sous-tronçons d'un axe"
    op.create_index(
        "ix_axe_sous_troncons_axe",
        "axe_sous_troncons",
        ["axe_id", "ordre"],
    )

    # Backfill : rattache chaque sous-tronçon existant à son axe historique
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO axe_sous_troncons (axe_id, sous_troncon_id, ordre) "
        "SELECT troncon_id, id, ordre FROM sous_troncons "
        "ON CONFLICT (axe_id, sous_troncon_id) DO NOTHING"
    ))


def downgrade() -> None:
    op.drop_index("ix_axe_sous_troncons_axe", table_name="axe_sous_troncons")
    op.drop_table("axe_sous_troncons")
