"""P5 — releves_terrain : ajout horodatage_passage + duree_api_s + confiance_matching.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-20

Pour pouvoir apparier finement chaque segment terrain avec la mesure API la plus
proche dans le temps, on stocke un horodatage précis (UTC) du passage sur le
tronçon. `date_session` reste pour le filtrage par jour calendaire ; les
nouvelles colonnes affinent l'analyse :

  - `horodatage_passage`  → instant médian du segment terrain sur ce tronçon
  - `duree_api_s`         → durée API utilisée comme référence pour ε
  - `confiance_matching`  → confiance OSRM du map-matching (0..1)
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "releves_terrain",
        sa.Column("horodatage_passage", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "releves_terrain",
        sa.Column("duree_api_s", sa.Integer, nullable=True),
    )
    op.add_column(
        "releves_terrain",
        sa.Column("confiance_matching", sa.Float, nullable=True),
    )
    op.create_index(
        "ix_releves_terrain_troncon_horodatage",
        "releves_terrain",
        ["troncon_id", "horodatage_passage"],
    )


def downgrade() -> None:
    op.drop_index("ix_releves_terrain_troncon_horodatage", table_name="releves_terrain")
    op.drop_column("releves_terrain", "confiance_matching")
    op.drop_column("releves_terrain", "duree_api_s")
    op.drop_column("releves_terrain", "horodatage_passage")
