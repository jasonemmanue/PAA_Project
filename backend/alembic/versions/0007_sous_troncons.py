"""P6.4 — Table sous_troncons (codifiés T1A, T1B, T1C, T2A...).

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-21

Méthodologie DEESP (cf. CLAUDE.md § 4.5) :

Le rapport DEESP attribue des codes (T1A, T1B, T1C, T2A...) à des portions
des 3 axes principaux. Cela permet une analyse fine des zones de
congestion (Tableau 16). Cette migration ajoute la table dédiée.

  - `troncons` continue de représenter les 6 axes principaux (CARENA → Palm
    Beach, etc.)
  - `sous_troncons` représente des portions ordonnées de ces axes, chacune
    avec son propre code (unique par parent)

La suppression reste TOUJOURS logique (`actif=false`) pour préserver
l'historique.
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sous_troncons",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "troncon_id", sa.Integer,
            sa.ForeignKey("troncons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Code unique par parent : "T1A", "T1B", etc.
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("nom_court", sa.String(120), nullable=False),
        # Ordre séquentiel sur l'axe parent (1=premier sous-tronçon, etc.)
        sa.Column("ordre", sa.Integer, nullable=False),
        # Coordonnées de début et fin
        sa.Column("lat_debut", sa.Float, nullable=False),
        sa.Column("lon_debut", sa.Float, nullable=False),
        sa.Column("lat_fin", sa.Float, nullable=False),
        sa.Column("lon_fin", sa.Float, nullable=False),
        # Géométrie + distance (calculées à la création)
        sa.Column("polyline", sa.Text, nullable=True),
        sa.Column("distance_m", sa.Integer, nullable=False),
        # Suppression logique
        sa.Column(
            "actif", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "cree_le", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    # Code unique par parent
    op.create_unique_constraint(
        "uq_sous_troncons_parent_code",
        "sous_troncons", ["troncon_id", "code"],
    )
    # Index pour les requêtes par parent + ordre
    op.create_index(
        "ix_sous_troncons_parent_ordre",
        "sous_troncons", ["troncon_id", "ordre"],
    )


def downgrade() -> None:
    op.drop_index("ix_sous_troncons_parent_ordre", table_name="sous_troncons")
    op.drop_constraint("uq_sous_troncons_parent_code", "sous_troncons")
    op.drop_table("sous_troncons")
