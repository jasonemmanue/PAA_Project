"""P6.2 — Table alertes + colonne source_reelle pour releves_terrain.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-21

Deux changements liés au prédicteur DEESP (cf. CLAUDE.md § 4.5) :

1. **Table `alertes`** — émise quand une mesure courante dépasse le P95
   historique du créneau correspondant (jour-semaine × heure). Trace
   exploitable pour un système d'alerte temps réel (recommandation §4.5.7
   point 5 du rapport DEESP).

2. **Colonne `releves_terrain.source_reelle`** — marqueur permettant au
   prédicteur de désactiver le facteur de calibration tant que les seuls
   relevés disponibles sont des GPX synthétiques (`generer_gpx_synthetiques`).
   Par défaut false ; les imports POST /terrain/import à partir de maintenant
   peuvent l'override à true via le formulaire (cf. P6.2 amendement 1).
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Table alertes
    op.create_table(
        "alertes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("troncon_id", sa.Integer,
                  sa.ForeignKey("troncons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("horodatage_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valeur_mesuree_s", sa.Integer, nullable=False),
        sa.Column("p95_attendu_s", sa.Float, nullable=False),
        sa.Column("type_jour", sa.String(20), nullable=False),  # jour_ouvrable / week_end
        sa.Column("lu", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("creee_le", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_alertes_troncon_horodatage",
        "alertes",
        ["troncon_id", "horodatage_utc"],
    )
    op.create_index("ix_alertes_lu", "alertes", ["lu"])

    # 2. Colonne source_reelle sur releves_terrain
    op.add_column(
        "releves_terrain",
        sa.Column(
            "source_reelle",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("releves_terrain", "source_reelle")
    op.drop_index("ix_alertes_lu", table_name="alertes")
    op.drop_index("ix_alertes_troncon_horodatage", table_name="alertes")
    op.drop_table("alertes")
