"""Migration 0014 — Table `sources_incidents` pour les sources de scraping configurables.

Permet à l'opérateur d'ajouter, désactiver ou supprimer des sources RSS / HTML
sans modifier le code source.

Colonnes :
  - id           : PK
  - nom          : identifiant court unique (ex. 'fraternite_matin')
  - libelle      : nom humain affiché (ex. 'Fraternité Matin')
  - url          : URL du flux RSS ou de la page HTML
  - type         : 'rss' ou 'html' (HTML non encore implémenté, prévu P8.2++)
  - actif        : bool — désactiver sans supprimer
  - fiabilite    : float (0..1) — score initial appliqué aux incidents collectés
  - ajoute_le    : datetime tz, audit

Seed initial : les 3 sources RSS historiques (fraternite_matin, abidjan_net, koaci)
sont insérées si absentes.

Revision: 0014
Revises: 0013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources_incidents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("nom", sa.String(80), nullable=False, unique=True),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("type", sa.String(10), nullable=False, server_default="rss"),
        sa.Column("actif", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("fiabilite", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("ajoute_le", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    # Seed des 3 sources historiques (idempotent grâce à ON CONFLICT)
    op.execute("""
        INSERT INTO sources_incidents (nom, libelle, url, type, actif, fiabilite)
        VALUES
          ('fraternite_matin', 'Fraternité Matin', 'https://www.fraternitematin.ci/feed/', 'rss', true, 0.90),
          ('abidjan_net',      'Abidjan.net',      'https://news.abidjan.net/rss.php',     'rss', true, 0.80),
          ('koaci',            'Koaci',            'https://koaci.com/rss.xml',            'rss', true, 0.75)
        ON CONFLICT (nom) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("sources_incidents")
