"""Critère couleur DEESP — colonnes de congestion par couleur sur `mesures`.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-22

Cette migration ajoute les colonnes permettant de reproduire fidèlement le
critère de congestion du rapport DEESP/DEEF (oct. 2025) — couleur Google
Maps : ROUGE → congestionné, ORANGE long (≥ 50 %) → congestionné, sinon
fluide.

Les colonnes ajoutées :

  - pourcentage_rouge   : part du tracé en TRAFFIC_JAM Google (0..100)
  - pourcentage_orange  : part du tracé en SLOW Google (0..100)
  - pourcentage_vert    : part du tracé en NORMAL Google (0..100)
  - est_congestionne    : booléen — règle DEESP appliquée

Toutes nullables : NULL = Google n'a pas renvoyé `speedReadingIntervals`
pour ce cycle (zone sans donnée trafic). On ne fabrique aucune valeur
(cf. CLAUDE.md § 5.3 — pas d'interpolation).

Les colonnes `duree_trafic_s` et `duree_sans_trafic_s` sont **conservées**
car elles alimentent les agrégats temps min/moyen/max par jour, semaine,
mois (Tableaux 3-15 du rapport DEESP) — cf. CLAUDE.md § 4.5.4.
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mesures",
        sa.Column("pourcentage_rouge", sa.Float(), nullable=True),
    )
    op.add_column(
        "mesures",
        sa.Column("pourcentage_orange", sa.Float(), nullable=True),
    )
    op.add_column(
        "mesures",
        sa.Column("pourcentage_vert", sa.Float(), nullable=True),
    )
    op.add_column(
        "mesures",
        sa.Column("est_congestionne", sa.Boolean(), nullable=True),
    )
    # Index pour accélérer les agrégats « combien de tronçons congestionnés
    # par tranche horaire » (Tableau 16 du rapport DEESP).
    op.create_index(
        "ix_mesures_est_congestionne",
        "mesures",
        ["troncon_id", "est_congestionne", "horodatage"],
    )


def downgrade() -> None:
    op.drop_index("ix_mesures_est_congestionne", table_name="mesures")
    op.drop_column("mesures", "est_congestionne")
    op.drop_column("mesures", "pourcentage_vert")
    op.drop_column("mesures", "pourcentage_orange")
    op.drop_column("mesures", "pourcentage_rouge")
