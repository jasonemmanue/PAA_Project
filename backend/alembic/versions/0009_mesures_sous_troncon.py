"""Mesures par sous-tronçon — colonne sous_troncon_id sur `mesures`.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-24

Permet au scheduler de collecter Google Routes au niveau **sous-tronçon**
(codification DEESP T1A, T1B, T1C…) en plus du niveau tronçon parent.

  - sous_troncon_id : FK nullable vers sous_troncons.id, ondelete CASCADE.
  - Index composite (sous_troncon_id, horodatage) pour accélérer les
    requêtes d'agrégation par créneau.

Règle métier :
  - Si un tronçon parent a au moins 1 sous-tronçon actif, le scheduler
    mesure UNIQUEMENT les sous-tronçons (et `mesures.troncon_id` reste
    renseigné par cohérence, mais `sous_troncon_id` est posé).
  - Sinon le scheduler mesure le tronçon parent comme avant
    (`sous_troncon_id` = NULL).

Pas de contrainte SQL forçant l'exclusivité — la logique est dans
`backend/app/collecte/scheduler.py`.
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mesures",
        sa.Column("sous_troncon_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mesures_sous_troncon",
        "mesures", "sous_troncons",
        ["sous_troncon_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_mesures_sous_troncon_horodatage",
        "mesures",
        ["sous_troncon_id", "horodatage"],
    )


def downgrade() -> None:
    op.drop_index("ix_mesures_sous_troncon_horodatage", table_name="mesures")
    op.drop_constraint("fk_mesures_sous_troncon", "mesures", type_="foreignkey")
    op.drop_column("mesures", "sous_troncon_id")
