"""Schéma initial FLUIDIS — 4 tables + enum source_mesure + index.

Révision    : 0001
Dépend de   : (aucune — migration racine)
Date        : 2026-06-18

Tables créées :
  - troncons
  - mesures          (+ index sur troncon_id, horodatage)
  - profils_horaires (+ index unique sur troncon_id, jour_semaine, heure)
  - releves_terrain
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ----------------------------------------------------------------------
# Type ENUM partagé.
# create_type=False est CRUCIAL : sans ça, SQLAlchemy retenterait un
# CREATE TYPE lors de la création de la table `mesures` (via l'événement
# _on_table_create), ce qui ferait échouer toute la migration.
# Le type est créé une seule fois, explicitement, via op.execute().
# ----------------------------------------------------------------------
source_mesure_enum = postgresql.ENUM(
    "google", "tomtom", "terrain", "interne",
    name="source_mesure",
    create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Création explicite du type ENUM (SQL brut, sans ambiguïté)
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE source_mesure AS ENUM ('google', 'tomtom', 'terrain', 'interne')"
    )

    # ------------------------------------------------------------------
    # Table : troncons
    # ------------------------------------------------------------------
    op.create_table(
        "troncons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nom", sa.String(200), nullable=False),
        # Coordonnées des extrémités — NULL jusqu'à la résolution OSRM
        sa.Column("lat_origine", sa.Float(), nullable=True),
        sa.Column("lon_origine", sa.Float(), nullable=True),
        sa.Column("lat_destination", sa.Float(), nullable=True),
        sa.Column("lon_destination", sa.Float(), nullable=True),
        # Polyline encodée — NULL jusqu'à la résolution OSRM
        sa.Column("polyline", sa.Text(), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("vitesse_ref_kmh", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("couleur", sa.String(7), nullable=False, server_default="#1976D2"),
        # Suppression logique uniquement
        sa.Column("actif", sa.Boolean(), nullable=False, server_default="true"),
    )

    # ------------------------------------------------------------------
    # Table : mesures
    # ------------------------------------------------------------------
    op.create_table(
        "mesures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "troncon_id",
            sa.Integer(),
            sa.ForeignKey("troncons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Stocké en UTC
        sa.Column("horodatage", sa.DateTime(timezone=True), nullable=False),
        # NULL si la source concernée n'a pas renvoyé de valeur exploitable
        sa.Column("duree_trafic_s", sa.Integer(), nullable=True),
        sa.Column("duree_sans_trafic_s", sa.Integer(), nullable=True),
        # Type déjà créé par op.execute() plus haut — l'objet ENUM partagé
        # a create_type=False, donc aucune tentative de recréation.
        sa.Column("source", source_mesure_enum, nullable=False),
        sa.Column("vitesse_moyenne_kmh", sa.Float(), nullable=True),
    )
    # Index principal pour les requêtes analytiques et le tableau de bord
    op.create_index(
        "ix_mesures_troncon_horodatage",
        "mesures",
        ["troncon_id", "horodatage"],
    )

    # ------------------------------------------------------------------
    # Table : profils_horaires
    # Clé primaire composite (troncon_id, jour_semaine, heure)
    # ------------------------------------------------------------------
    op.create_table(
        "profils_horaires",
        sa.Column(
            "troncon_id",
            sa.Integer(),
            sa.ForeignKey("troncons.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        # 0 = lundi … 6 = dimanche
        sa.Column("jour_semaine", sa.SmallInteger(), nullable=False, primary_key=True),
        # 0–23
        sa.Column("heure", sa.SmallInteger(), nullable=False, primary_key=True),
        # Statistiques agrégées en secondes
        sa.Column("moyenne", sa.Float(), nullable=True),
        sa.Column("mediane", sa.Float(), nullable=True),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("p95", sa.Float(), nullable=True),
        sa.Column("nb_mesures", sa.Integer(), nullable=False, server_default="0"),
    )
    # Index unique sur la clé de recherche analytique (redondant avec PK mais
    # nommé explicitement pour les requêtes Alembic --autogenerate futures)
    op.create_index(
        "ix_profils_horaires_troncon_jour_heure",
        "profils_horaires",
        ["troncon_id", "jour_semaine", "heure"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Table : releves_terrain
    # ------------------------------------------------------------------
    op.create_table(
        "releves_terrain",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "troncon_id",
            sa.Integer(),
            sa.ForeignKey("troncons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("date_session", sa.Date(), nullable=False),
        sa.Column("fichier_gpx", sa.String(500), nullable=True),
        sa.Column("duree_mesuree_s", sa.Integer(), nullable=True),
        sa.Column("ecart_relatif", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("releves_terrain")
    op.drop_index("ix_profils_horaires_troncon_jour_heure", table_name="profils_horaires")
    op.drop_table("profils_horaires")
    op.drop_index("ix_mesures_troncon_horodatage", table_name="mesures")
    op.drop_table("mesures")
    op.drop_table("troncons")
    # Suppression du type ENUM en SQL brut (symétrique du upgrade)
    op.execute("DROP TYPE IF EXISTS source_mesure")
