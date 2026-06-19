"""Évolution P6.1 — table evolution_indicateur + valeur enum historique_paa_2025.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajout de la valeur d'enum (idempotent grâce à IF NOT EXISTS)
    #    ALTER TYPE ... ADD VALUE ne peut pas être annulé dans une transaction,
    #    mais IF NOT EXISTS le rend sûr à rejouer.
    op.execute("ALTER TYPE source_mesure ADD VALUE IF NOT EXISTS 'historique_paa_2025'")

    # 2. Création de la table evolution_indicateur
    op.create_table(
        "evolution_indicateur",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("axe", sa.String(200), nullable=False),
        sa.Column("sens", sa.String(10), nullable=False),
        sa.Column("periode", sa.String(20), nullable=False),
        sa.Column("type_jour", sa.String(30), nullable=False),
        sa.Column("temps_min_s", sa.Float, nullable=True),
        sa.Column("temps_moyen_s", sa.Float, nullable=True),
        sa.Column("temps_max_s", sa.Float, nullable=True),
    )
    op.create_unique_constraint(
        "uq_evolution_axe_sens_periode_type",
        "evolution_indicateur",
        ["axe", "sens", "periode", "type_jour"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_evolution_axe_sens_periode_type", "evolution_indicateur")
    op.drop_table("evolution_indicateur")
    # Note : PostgreSQL ne supporte pas DROP VALUE sur un enum —
    # la valeur historique_paa_2025 reste dans le type source_mesure.
