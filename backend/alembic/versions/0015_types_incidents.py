"""Migration 0015 — Types d'incidents configurables.

Changes :
  1. Convertit incidents.type_incident de l'ENUM PostgreSQL vers VARCHAR(50)
     pour permettre des types personnalisés sans migration supplémentaire.
  2. Crée la table types_incidents : CRUD des catégories d'incidents.
  3. Seed des 4 types de base + 'autre' (idempotent via ON CONFLICT).

Revision: 0015
Revises: 0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# Types de base à insérer au seed
_TYPES_BASE = [
    (
        "accident",
        "Accident",
        r"accident|collision|accrochage|carambolage|renvers|percut|choc frontal|derapage",
    ),
    (
        "route_barree",
        "Route barrée",
        r"route barr|voie coup|bloqu|ferm|manifestation|barricade|mouvement d.humeur",
    ),
    (
        "travaux",
        "Travaux",
        r"travaux|chantier|refection|caniveau|bitumage|goudronnage",
    ),
    (
        "embouteillage",
        "Embouteillage",
        r"embouteillage|bouchon|ralentissement|congestion|trafic dense|circulation difficile",
    ),
    (
        "autre",
        "Autre",
        r"(?!)",  # Regex qui ne matche jamais — 'autre' est le fallback par défaut
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Convertir type_incident de ENUM vers VARCHAR
    conn.execute(sa.text(
        "ALTER TABLE incidents "
        "ALTER COLUMN type_incident TYPE VARCHAR(50) "
        "USING type_incident::text"
    ))
    conn.execute(sa.text("DROP TYPE IF EXISTS typeincident"))

    # 2. Créer la table types_incidents
    op.create_table(
        "types_incidents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("regex", sa.Text, nullable=False),
        sa.Column("actif", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "cree_le",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # 3. Seed des types de base (idempotent)
    for slug, libelle, regex in _TYPES_BASE:
        conn.execute(
            sa.text(
                "INSERT INTO types_incidents (slug, libelle, regex, actif) "
                "VALUES (:slug, :libelle, :regex, true) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "libelle": libelle, "regex": regex},
        )


def downgrade() -> None:
    op.drop_table("types_incidents")
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE TYPE typeincident AS ENUM "
        "('accident', 'embouteillage', 'route_barree', 'travaux', 'autre')"
    ))
    conn.execute(sa.text(
        "ALTER TABLE incidents "
        "ALTER COLUMN type_incident TYPE typeincident "
        "USING type_incident::typeincident"
    ))
