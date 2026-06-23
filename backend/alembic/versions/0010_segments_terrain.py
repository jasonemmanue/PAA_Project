"""Table segments_terrain — sous-sections GPX terrain par trajet libre.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-23

Chaque enregistrement correspond à UN segment entre deux landmarks
intermédiaires (ex. "CARENA→GMA", "Sim Ivoire→Carrefour Seamen's").
Ces segments s'accumulent au fil des sessions terrain pour améliorer
progressivement la précision des temps de traversée estimés.

Contrairement à `releves_terrain` (qui stocke un trajet COMPLET
depuis l'extrémité officielle d'un tronçon), `segments_terrain` accepte
des enregistrements PARTIELS : l'opérateur peut enregistrer n'importe
quelle sous-portion du tracé officiel. Le module d'assemblage somme
ensuite les durées pour reconstituer le temps total par tronçon.

Logique de précision progressive (cf. CLAUDE.md § 4.9) :
  - 1 session   → estimation directe (ou miroir aller/retour)
  - N sessions  → moyenne des N estimations → convergence progressive
  - Couverture  → % de la distance totale couverte par les segments
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "segments_terrain",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Libellé descriptif du segment (ex. "CARENA-GMA", "Sim Ivoire-Carrefour Seamen's")
        sa.Column("nom_segment", sa.String(200), nullable=False),

        # Tronçon parent optionnel — permet d'agréger les segments par axe officiel
        sa.Column(
            "troncon_id", sa.Integer(),
            sa.ForeignKey("troncons.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Direction de circulation : 'aller' (vers Palm Beach) ou 'retour' (depuis Palm Beach)
        sa.Column("direction", sa.String(10), nullable=True),

        # Coordonnées GPS du premier et dernier point enregistré
        sa.Column("lat_debut", sa.Float(), nullable=False),
        sa.Column("lon_debut", sa.Float(), nullable=False),
        sa.Column("lat_fin", sa.Float(), nullable=False),
        sa.Column("lon_fin", sa.Float(), nullable=False),

        # Durée mesurée en secondes (depuis les horodatages GPS)
        sa.Column("duree_s", sa.Integer(), nullable=False),

        # Distance cumulée des points de la trace (Haversine), en mètres
        sa.Column("distance_m", sa.Float(), nullable=True),

        # Horodatages UTC du début et de la fin du segment
        sa.Column("horodatage_debut", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horodatage_fin", sa.DateTime(timezone=True), nullable=False),

        # Date de la session terrain (pour grouper plusieurs segments d'une même sortie)
        sa.Column("date_session", sa.Date(), nullable=False),

        # Identifiant de session — permet de regrouper les segments
        # enregistrés lors du même parcours (ex. "20260622_A" pour la session
        # aller du 22 juin 2026). Format libre défini par l'opérateur.
        sa.Column("session_id", sa.String(50), nullable=True),

        # True = GPX téléphone réel (compte pour la calibration)
        # False = GPX synthétique généré par generer_gpx_synthetiques.py (exclu)
        sa.Column(
            "source_reelle", sa.Boolean(), nullable=False,
            server_default="true",
        ),

        # Contenu binaire du fichier GPX — source de vérité, survit aux redéploiements
        sa.Column("contenu_gpx", sa.LargeBinary(), nullable=True),

        # Nom du fichier original (pour les logs et le téléchargement)
        sa.Column("nom_fichier_gpx", sa.String(500), nullable=True),

        # Timestamp de création
        sa.Column(
            "cree_le", sa.DateTime(timezone=True),
            server_default="now()", nullable=False,
        ),
    )

    # Index pour les requêtes d'agrégation par tronçon + date
    op.create_index(
        "ix_segments_terrain_troncon_date",
        "segments_terrain",
        ["troncon_id", "date_session"],
    )
    # Index pour grouper par session
    op.create_index(
        "ix_segments_terrain_session",
        "segments_terrain",
        ["session_id"],
    )
    # Index pour la chronologie
    op.create_index(
        "ix_segments_terrain_horodatage",
        "segments_terrain",
        ["horodatage_debut"],
    )


def downgrade() -> None:
    op.drop_index("ix_segments_terrain_horodatage", table_name="segments_terrain")
    op.drop_index("ix_segments_terrain_session", table_name="segments_terrain")
    op.drop_index("ix_segments_terrain_troncon_date", table_name="segments_terrain")
    op.drop_table("segments_terrain")
