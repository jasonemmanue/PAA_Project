"""Évolution P2 — agrégation : fenêtres glissantes + flag IQR sur mesures.

Révision    : 0002
Dépend de   : 0001
Date        : 2026-06-18

Changements :
  - mesures              : ajout `aberrante BOOLEAN NOT NULL DEFAULT FALSE`
                           (flag posé par le job d'agrégation via IQR).
  - profils_horaires     : ajout `fenetre_jours SMALLINT NOT NULL` dans la PK
                           (3 lignes possibles par tronçon/jour/heure pour les
                           fenêtres glissantes 30/60/90 j).

⚠️  Modifier une PK existante en PostgreSQL impose de :
  1. supprimer l'index unique redondant ;
  2. supprimer la contrainte PK ;
  3. ajouter la colonne fenetre_jours avec un DEFAULT temporaire pour les
     éventuelles lignes existantes (vide en l'occurrence — sécurité) ;
  4. recréer la PK élargie ;
  5. recréer l'index unique étendu.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. mesures.aberrante — flag IQR posé par l'agrégation nocturne.
    # ------------------------------------------------------------------
    op.add_column(
        "mesures",
        sa.Column(
            "aberrante",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Index partiel : on n'analyse les aberrantes que ponctuellement
    op.create_index(
        "ix_mesures_aberrante",
        "mesures",
        ["aberrante"],
        postgresql_where=sa.text("aberrante = true"),
    )

    # ------------------------------------------------------------------
    # 2. profils_horaires : élargissement de la PK à fenetre_jours.
    # ------------------------------------------------------------------
    # Suppression de l'index unique redondant (créé en 0001)
    op.drop_index(
        "ix_profils_horaires_troncon_jour_heure",
        table_name="profils_horaires",
    )

    # Suppression de la contrainte PK existante. Le nom auto-généré PostgreSQL
    # pour une PK est `<table>_pkey` — on l'écrit explicitement.
    op.drop_constraint("profils_horaires_pkey", "profils_horaires", type_="primary")

    # Ajout de la colonne (DEFAULT 30 le temps de la migration, retiré ensuite)
    op.add_column(
        "profils_horaires",
        sa.Column(
            "fenetre_jours",
            sa.SmallInteger(),
            nullable=False,
            server_default="30",
        ),
    )
    # On retire le DEFAULT pour forcer une valeur explicite côté code applicatif
    op.alter_column("profils_horaires", "fenetre_jours", server_default=None)

    # Recréation de la PK élargie
    op.create_primary_key(
        "profils_horaires_pkey",
        "profils_horaires",
        ["troncon_id", "jour_semaine", "heure", "fenetre_jours"],
    )

    # Recréation de l'index unique nommé (utile pour --autogenerate futurs
    # et pour les requêtes analytiques par fenêtre)
    op.create_index(
        "ix_profils_horaires_troncon_jour_heure_fenetre",
        "profils_horaires",
        ["troncon_id", "jour_semaine", "heure", "fenetre_jours"],
        unique=True,
    )


def downgrade() -> None:
    # Inverse strict du upgrade — utile pour rejouer une migration en dev.
    op.drop_index(
        "ix_profils_horaires_troncon_jour_heure_fenetre",
        table_name="profils_horaires",
    )
    op.drop_constraint("profils_horaires_pkey", "profils_horaires", type_="primary")
    op.drop_column("profils_horaires", "fenetre_jours")
    op.create_primary_key(
        "profils_horaires_pkey",
        "profils_horaires",
        ["troncon_id", "jour_semaine", "heure"],
    )
    op.create_index(
        "ix_profils_horaires_troncon_jour_heure",
        "profils_horaires",
        ["troncon_id", "jour_semaine", "heure"],
        unique=True,
    )

    op.drop_index("ix_mesures_aberrante", table_name="mesures")
    op.drop_column("mesures", "aberrante")
