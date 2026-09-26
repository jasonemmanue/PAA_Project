"""Migration 0017 — Table rapport_parametres (données Excel du Rapport DEESP).

Le Rapport DEESP officiel (.docx) contient deux familles de contenus :

  1. Les données **produites par l'application** (temps de traversée collectés
     via Google Routes, tronçons congestionnés, graphiques) — recalculées à
     chaque génération depuis la table `mesures` sur la période choisie.

  2. Les données **hors application** : chiffres macro-économiques de
     l'introduction, constats terrain de la conclusion, campagne de référence
     du Tableau 19 comparatif, relevés manuels des annexes, signataires.
     Ces données sont saisies par l'opérateur dans un classeur Excel
     téléchargé depuis la page Rapport puis ré-importé.

Cette table persiste la famille 2, par campagne (AAAA-MM), sous forme d'un
document JSON. Un import sur une campagne déjà présente écrase l'entrée
(UPSERT sur la clé unique `campagne`).

Revision: 0017
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rapport_parametres",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        # Campagne au format 'AAAA-MM' (ex. '2026-02')
        sa.Column("campagne", sa.String(7), nullable=False),
        # Contenu du classeur Excel importé, normalisé en JSON
        sa.Column(
            "donnees",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Nom du fichier d'origine — tracé pour l'affichage côté UI
        sa.Column("nom_fichier", sa.String(255), nullable=True),
        sa.Column(
            "importe_le",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("campagne", name="uq_rapport_parametres_campagne"),
    )


def downgrade() -> None:
    op.drop_table("rapport_parametres")
