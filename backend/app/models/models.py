"""Modèles SQLAlchemy pour les 4 tables du projet PAA-Traverse.

Correspondance avec CLAUDE.md § 3 (Modèle de données) :
  - Troncon         → table `troncons`
  - Mesure          → table `mesures`
  - ProfilHoraire   → table `profils_horaires`
  - RelевеTerrain   → table `releves_terrain`

Conventions :
  - Toutes les durées sont en secondes (entier).
  - Les distances sont en mètres (entier).
  - Les horodatages sont stockés en UTC (timezone=True).
  - La suppression d'un tronçon est logique (actif=False), jamais physique.
  - Aucune valeur n'est inventée : les colonnes peuvent être NULL si la mesure est absente.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from app.db.session import Base


# ---------------------------------------------------------------------------
# Énumération des sources de mesure
# ---------------------------------------------------------------------------


class SourceMesure(str, enum.Enum):
    """Sources acceptées pour une mesure de temps de parcours.

    `tomtom` est conservé dans l'enum PostgreSQL (valeur inerte) mais aucun
    code ne le produit : TomTom a été retiré du projet faute de couverture à
    Abidjan (cf. CLAUDE.md § 2.5). La retirer demanderait une migration
    Postgres risquée pour zéro bénéfice fonctionnel.
    """
    google = "google"
    tomtom = "tomtom"                       # désactivée — conservée par compat. schéma
    terrain = "terrain"
    interne = "interne"
    historique_paa_2025 = "historique_paa_2025"  # données campagne terrain fév 2025


# ---------------------------------------------------------------------------
# Table : troncons
# ---------------------------------------------------------------------------


class Troncon(Base):
    """Un tronçon représente un sens de circulation sur un axe officiel.

    Chaque axe physique produit deux lignes (aller + retour) car les temps
    de parcours peuvent différer significativement selon le sens.
    Suppression toujours logique : actif=False préserve l'historique.
    """

    __tablename__ = "troncons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)

    # Coordonnées des extrémités (NULL jusqu'à la résolution OSRM)
    lat_origine: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon_origine: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat_destination: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon_destination: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Tracé encodé retourné par OSRM (NULL jusqu'à la résolution OSRM)
    polyline: Mapped[str | None] = mapped_column(Text, nullable=True)

    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    vitesse_ref_kmh: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    couleur: Mapped[str] = mapped_column(String(7), nullable=False, default="#1976D2")

    # Suppression logique : False = tronçon archivé, historique préservé
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relations
    mesures: Mapped[list["Mesure"]] = relationship(
        "Mesure", back_populates="troncon", cascade="all, delete-orphan"
    )
    profils_horaires: Mapped[list["ProfilHoraire"]] = relationship(
        "ProfilHoraire", back_populates="troncon", cascade="all, delete-orphan"
    )
    releves_terrain: Mapped[list["ReleveTerrain"]] = relationship(
        "ReleveTerrain", back_populates="troncon", cascade="all, delete-orphan"
    )
    sous_troncons: Mapped[list["SousTroncon"]] = relationship(
        "SousTroncon", back_populates="troncon",
        cascade="all, delete-orphan",
        order_by="SousTroncon.ordre",
    )

    def temps_reference_s(self) -> float:
        """Temps de parcours théorique à vitesse de référence, en secondes."""
        return (self.distance_m / 1000.0) / self.vitesse_ref_kmh * 3600.0

    def __repr__(self) -> str:
        return f"<Troncon id={self.id} nom={self.nom!r} actif={self.actif}>"


# ---------------------------------------------------------------------------
# Table : mesures
# ---------------------------------------------------------------------------


class Mesure(Base):
    """Un échantillon de temps de parcours observé à un instant donné.

    Si toutes les sources échouent, aucune ligne n'est insérée (trou de mesure).
    On n'invente ni n'interpole jamais de valeur.
    """

    __tablename__ = "mesures"

    # Index composite prioritaire pour les requêtes analytiques
    __table_args__ = (
        Index("ix_mesures_troncon_horodatage", "troncon_id", "horodatage"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    troncon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="RESTRICT"), nullable=False
    )
    # Stocké en UTC ; le fuseau Africa/Abidjan est appliqué à l'affichage
    horodatage: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Conservés pour les agrégats min/moyen/max par jour/semaine/mois
    # (Tableaux 3-15 du rapport DEESP, cf. CLAUDE.md § 4.5.4). NULL si la
    # source n'a pas renvoyé de valeur exploitable (trou de mesure).
    duree_trafic_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duree_sans_trafic_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # postgresql.ENUM avec create_type=False : le type est géré exclusivement
    # par les migrations Alembic, jamais par SQLAlchemy au démarrage du backend.
    source: Mapped[SourceMesure] = mapped_column(
        postgresql.ENUM(SourceMesure, name="source_mesure", create_type=False),
        nullable=False,
    )

    vitesse_moyenne_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Critère DEESP couleur (cf. rapport oct. 2025 § METHODOLOGIE et
    # CLAUDE.md § 4.5.2). Pourcentages de la longueur du tronçon par couleur
    # Google Maps : vert / orange / rouge. NULL si Google n'a pas renvoyé
    # `speedReadingIntervals` pour ce cycle (zone non couverte par les
    # données trafic — aucune valeur n'est inventée).
    pourcentage_rouge: Mapped[float | None] = mapped_column(Float, nullable=True)
    pourcentage_orange: Mapped[float | None] = mapped_column(Float, nullable=True)
    pourcentage_vert: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Verdict DEESP : True si rouge>0 OU orange ≥ 50 %, False sinon. NULL si
    # les pourcentages couleur sont absents.
    est_congestionne: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Flag posé par le job d'agrégation (méthode IQR) — la mesure reste
    # conservée en base, mais le frontend peut l'écarter de ses graphes.
    aberrante: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relation
    troncon: Mapped["Troncon"] = relationship("Troncon", back_populates="mesures")

    def __repr__(self) -> str:
        return (
            f"<Mesure id={self.id} troncon_id={self.troncon_id} "
            f"source={self.source.value} horodatage={self.horodatage}>"
        )


# ---------------------------------------------------------------------------
# Table : profils_horaires
# ---------------------------------------------------------------------------


class ProfilHoraire(Base):
    """Statistiques agrégées par (tronçon, jour_semaine, heure).

    Recalculée chaque nuit par un job APScheduler (P2).
    Alimente le prédicteur interne (P6).
    Clé primaire composite : (troncon_id, jour_semaine, heure).
    """

    __tablename__ = "profils_horaires"

    __table_args__ = (
        # Unicité garantie par la clé primaire composite ci-dessous ;
        # l'index composite explicite accélère les jointures analytiques.
        Index(
            "ix_profils_horaires_troncon_jour_heure_fenetre",
            "troncon_id", "jour_semaine", "heure", "fenetre_jours",
            unique=True,
        ),
    )

    # Clé primaire composite — fenetre_jours élargit la PK pour permettre
    # de stocker en parallèle les agrégats sur 30, 60 et 90 jours.
    troncon_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("troncons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # 0 = lundi … 6 = dimanche (convention Python datetime.weekday())
    jour_semaine: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # 0–23
    heure: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # Largeur de la fenêtre glissante d'agrégation, en jours : 30, 60 ou 90.
    fenetre_jours: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    # Statistiques en secondes
    moyenne: Mapped[float | None] = mapped_column(Float, nullable=True)
    mediane: Mapped[float | None] = mapped_column(Float, nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    nb_mesures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relation
    troncon: Mapped["Troncon"] = relationship(
        "Troncon", back_populates="profils_horaires"
    )

    def __repr__(self) -> str:
        return (
            f"<ProfilHoraire troncon_id={self.troncon_id} "
            f"jour={self.jour_semaine} heure={self.heure} "
            f"fenetre={self.fenetre_jours}j>"
        )


# ---------------------------------------------------------------------------
# Table : releves_terrain
# ---------------------------------------------------------------------------


class ReleveTerrain(Base):
    """Trace d'un relevé terrain hebdomadaire (fichier GPX + durée mesurée).

    Sert à valider la dérive éventuelle des sources API (P5).
    """

    __tablename__ = "releves_terrain"

    __table_args__ = (
        Index(
            "ix_releves_terrain_troncon_horodatage",
            "troncon_id", "horodatage_passage",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    troncon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="RESTRICT"), nullable=False
    )
    date_session: Mapped[date] = mapped_column(Date, nullable=False)

    # Instant médian (UTC) du passage sur le tronçon — sert à apparier finement
    # avec la mesure Google la plus proche dans le temps (cf. P5).
    horodatage_passage: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Chemin relatif ou URL vers le fichier GPX (stocké dans un volume dédié).
    # Conserve le nom de fichier pour les logs et le téléchargement.
    fichier_gpx: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Contenu binaire du `.gpx` — source de vérité, survit aux redéploiements
    # Railway (où le disque est éphémère par défaut). Cf. migration 0005.
    contenu_gpx: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Durée effectivement mesurée sur le terrain, en secondes
    duree_mesuree_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Durée API utilisée comme référence pour le calcul de l'écart
    duree_api_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # (durée_terrain – durée_API) / durée_API — NULL si pas encore calculé
    ecart_relatif: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Confiance OSRM du map-matching (0..1) — NULL si OSRM indisponible
    confiance_matching: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Flag indiquant qu'il s'agit d'un VRAI relevé terrain (téléphone GPS
    # parcourant réellement le tronçon) et non d'un GPX synthétique généré
    # par `app/generer_gpx_synthetiques.py`. Quand False, le facteur de
    # calibration calculé sur ce relevé n'est PAS appliqué par le prédicteur
    # (cf. P6.2 amendement 1, CLAUDE.md § 4.5).
    source_reelle: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relation
    troncon: Mapped["Troncon"] = relationship(
        "Troncon", back_populates="releves_terrain"
    )

    def __repr__(self) -> str:
        return (
            f"<ReleveTerrain id={self.id} troncon_id={self.troncon_id} "
            f"date={self.date_session} ecart={self.ecart_relatif}>"
        )


# ---------------------------------------------------------------------------
# Table : evolution_indicateur
# ---------------------------------------------------------------------------


class EvolutionIndicateur(Base):
    """Statistiques comparatives pluriannuelles par axe, sens, période et type de jour.

    Alimentée par l'import de la feuille 'SYNTHESE COMPAREE' du fichier
    FEVRIER_2026.xlsx. Permet de visualiser l'évolution des temps de traversée
    entre les campagnes (oct_2025, fev_2026, etc.).

    Durées stockées en secondes (float) pour cohérence avec `mesures`.
    """

    __tablename__ = "evolution_indicateur"

    __table_args__ = (
        UniqueConstraint("axe", "sens", "periode", "type_jour",
                         name="uq_evolution_axe_sens_periode_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Libellé de l'axe (ex. "CARENA → Pharmacie Palm Beach")
    axe: Mapped[str] = mapped_column(String(200), nullable=False)
    # "Aller" ou "Retour"
    sens: Mapped[str] = mapped_column(String(10), nullable=False)
    # Code de la campagne, ex. "oct_2025", "fev_2026"
    periode: Mapped[str] = mapped_column(String(20), nullable=False)
    # "Jours ouvrables" ou "Week-ends"
    type_jour: Mapped[str] = mapped_column(String(30), nullable=False)

    # Statistiques en secondes (NULL si donnée absente dans la source)
    temps_min_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    temps_moyen_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    temps_max_s: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EvolutionIndicateur axe={self.axe!r} sens={self.sens!r} "
            f"periode={self.periode!r} type_jour={self.type_jour!r}>"
        )


# ---------------------------------------------------------------------------
# Table : alertes  (P6.2 — prédicteur DEESP)
# ---------------------------------------------------------------------------


class Alerte(Base):
    """Alerte de congestion anormale — une mesure dépassant le P95 historique.

    Émise par le prédicteur DEESP quand `duree_trafic_s` d'une mesure courante
    dépasse le P95 historique du créneau correspondant (jour-semaine × heure).
    Sert le résultat n°5 de l'article 4 du cahier des charges (« Système
    d'alerte temps réel ») ainsi que la 5e recommandation du rapport DEESP.
    """

    __tablename__ = "alertes"

    __table_args__ = (
        Index("ix_alertes_troncon_horodatage", "troncon_id", "horodatage_utc"),
        Index("ix_alertes_lu", "lu"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    troncon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="CASCADE"), nullable=False
    )
    horodatage_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valeur_mesuree_s: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_attendu_s: Mapped[float] = mapped_column(Float, nullable=False)
    # "jour_ouvrable" ou "week_end" (cf. CLAUDE.md § 4.5.5)
    type_jour: Mapped[str] = mapped_column(String(20), nullable=False)
    lu: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    creee_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Alerte id={self.id} troncon_id={self.troncon_id} "
            f"valeur={self.valeur_mesuree_s}s p95={self.p95_attendu_s}s>"
        )


# ---------------------------------------------------------------------------
# Table : sous_troncons  (P6.4 — granularité fine DEESP)
# ---------------------------------------------------------------------------


class SousTroncon(Base):
    """Portion codifiée d'un axe principal (T1A, T1B, T1C, T2A...).

    Permet l'analyse fine des zones de congestion au niveau de portions de
    chaque axe — convention DEESP (cf. CLAUDE.md § 4.5 et Tableau 16 du
    rapport oct. 2025).

    Contrainte : code unique par tronçon parent. Suppression toujours
    logique (actif=False).
    """

    __tablename__ = "sous_troncons"

    __table_args__ = (
        UniqueConstraint(
            "troncon_id", "code", name="uq_sous_troncons_parent_code",
        ),
        Index(
            "ix_sous_troncons_parent_ordre",
            "troncon_id", "ordre",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    troncon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="CASCADE"), nullable=False,
    )
    # Code DEESP — ex. "T1A", "T2B", "T3C"
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    nom_court: Mapped[str] = mapped_column(String(120), nullable=False)
    # Ordre séquentiel sur le tronçon parent
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    # Bornes du sous-tronçon
    lat_debut: Mapped[float] = mapped_column(Float, nullable=False)
    lon_debut: Mapped[float] = mapped_column(Float, nullable=False)
    lat_fin: Mapped[float] = mapped_column(Float, nullable=False)
    lon_fin: Mapped[float] = mapped_column(Float, nullable=False)
    # Géométrie + distance
    polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    # Suppression logique
    actif: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False,
    )

    # Relation
    troncon: Mapped["Troncon"] = relationship(
        "Troncon", back_populates="sous_troncons",
    )

    def temps_reference_s(self) -> float:
        """Temps théorique 50 km/h pour ce sous-tronçon."""
        return (self.distance_m / 1000.0) / 50.0 * 3600.0

    def __repr__(self) -> str:
        return (
            f"<SousTroncon id={self.id} troncon_id={self.troncon_id} "
            f"code={self.code!r} ordre={self.ordre}>"
        )
