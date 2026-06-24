"""Table incidents — incidents de circulation scrapés depuis la presse ivoirienne.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-24

Recense automatiquement les accidents, embouteillages, routes barrées et
travaux signalés dans la zone portuaire d'Abidjan en scrutant les flux RSS
et les sites de presse ivoirienne toutes les 30 minutes.

La déduplication repose sur `source_url` (clé unique) : le même article
republié par une même source ne crée pas de doublon.

Les colonnes `lat` / `lon` restent NULL tant que le géocodage Nominatim
n'a pas été déclenché. L'enrichissement NLP (lieu, type, sévérité) est
asynchrone — les champs correspondants sont également nullable.
"""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum TypeIncident
    type_incident_enum = sa.Enum(
        "accident", "embouteillage", "route_barree", "travaux", "autre",
        name="typeincident",
    )
    type_incident_enum.create(op.get_bind(), checkfirst=True)

    # Enum SeveriteIncident
    severite_enum = sa.Enum(
        "mineur", "moyen", "grave", "inconnu",
        name="severiteincident",
    )
    severite_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Titre et résumé extraits de l'article
        sa.Column("titre", sa.String(500), nullable=False),
        sa.Column("resume", sa.Text(), nullable=True),

        # URL canonique — clé de déduplication inter-collectes
        sa.Column("source_url", sa.String(2000), nullable=False),

        # Identifiant lisible de la source (fraternite_matin, abidjan_net…)
        sa.Column("source_nom", sa.String(50), nullable=False),

        # Date de publication telle que fournie par le flux RSS (UTC)
        sa.Column(
            "horodatage_publication",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        # Instant où le scraper a détecté l'article (UTC)
        sa.Column(
            "horodatage_collecte",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),

        # Géocodage Nominatim — NULL si le lieu n'a pas été géocodé ou
        # si le résultat est hors de la bbox portuaire
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),

        # Lieu tel qu'extrait du texte par le module NLP (CLAUDE.md § 10.3)
        sa.Column("lieu_extrait", sa.String(200), nullable=True),

        # Tronçon impacté détecté par proximité géographique (< 300 m)
        sa.Column(
            "troncon_id",
            sa.Integer(),
            sa.ForeignKey("troncons.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Classification type et sévérité par regex NLP
        sa.Column(
            "type_incident",
            sa.Enum(
                "accident", "embouteillage", "route_barree", "travaux", "autre",
                name="typeincident",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "severite",
            sa.Enum(
                "mineur", "moyen", "grave", "inconnu",
                name="severiteincident",
                create_type=False,
            ),
            nullable=True,
        ),

        # Validation manuelle optionnelle (False par défaut)
        sa.Column(
            "verifie",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # URL unique pour la déduplication
    op.create_unique_constraint(
        "uq_incidents_source_url",
        "incidents",
        ["source_url"],
    )

    # Tri chronologique
    op.create_index(
        "ix_incidents_horodatage",
        "incidents",
        ["horodatage_publication"],
        postgresql_ops={"horodatage_publication": "DESC"},
    )

    # Filtrage par tronçon impacté
    op.create_index(
        "ix_incidents_troncon",
        "incidents",
        ["troncon_id", "horodatage_publication"],
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_troncon", table_name="incidents")
    op.drop_index("ix_incidents_horodatage", table_name="incidents")
    op.drop_constraint("uq_incidents_source_url", "incidents", type_="unique")
    op.drop_table("incidents")

    op.execute("DROP TYPE IF EXISTS typeincident")
    op.execute("DROP TYPE IF EXISTS severiteincident")
