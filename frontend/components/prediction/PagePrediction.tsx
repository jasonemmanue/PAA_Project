"use client";

/**
 * Page Prédiction (P6.2) — prédicteur DEESP + cascade gracieuse.
 *
 * Affiche pour un (tronçon, date, heure) cibles :
 *   - 3 KPI cards Min / Moyen / Max en minutes (format DEESP)
 *   - badge de source (google_routes / predicteur_profils_60j / vitesse_ref_50kmh)
 *   - badge de type-jour (jour_ouvrable / week_end)
 *   - phrase d'interprétation auto-générée
 *   - barre de confiance (0..1)
 *   - encart calibration si appliquée, avertissement si désactivée
 *   - encart MAE du prédicteur (qualité) en bas de page
 */

import { useCallback, useEffect, useState } from "react";

import { OngletHeureOptimale } from "@/components/prediction/OngletHeureOptimale";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  PredictionResponse,
  QualiteResponse,
  SourcePrediction,
  Troncon,
} from "@/lib/types";

type Onglet = "prediction" | "heure_optimale";

function defautDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function defautHeure(): number {
  return new Date().getHours();
}

const COULEUR_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "#2ECC71",
  predicteur_profils_60j: "#3498DB",
  vitesse_ref_50kmh: "#95A5A6",
};

const LIBELLE_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "Mesure Google temps réel",
  predicteur_profils_60j: "Prédicteur DEESP (profils 60 j)",
  vitesse_ref_50kmh: "Référence 50 km/h",
};

export function PagePrediction() {
  const { t } = useI18n();
  const [onglet, setOnglet] = useState<Onglet>("prediction");
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [tronconId, setTronconId] = useState<number | null>(null);
  const [dateCible, setDateCible] = useState<string>(defautDate());
  const [heure, setHeure] = useState<number>(defautHeure());
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [qualite, setQualite] = useState<QualiteResponse | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // 1) Charger la liste des tronçons + qualité du prédicteur
  useEffect(() => {
    let annule = false;
    Promise.all([api.troncons(), api.qualitePrediction(7)])
      .then(([liste, q]) => {
        if (annule) return;
        const tr = Array.isArray(liste) ? liste : [];
        setTroncons(tr);
        setTronconId(tr[0]?.id ?? null);
        setQualite(q);
      })
      .catch((e) =>
        !annule && setErreur(e instanceof Error ? e.message : String(e)),
      );
    return () => {
      annule = true;
    };
  }, []);

  const lancerPrediction = useCallback(async () => {
    if (tronconId === null) return;
    setChargement(true);
    setErreur(null);
    try {
      const p = await api.predire(tronconId, dateCible, heure);
      setPrediction(p);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, [tronconId, dateCible, heure]);

  // Auto-prédiction au chargement initial dès qu'on a un tronçon
  useEffect(() => {
    if (tronconId !== null && prediction === null) {
      void lancerPrediction();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tronconId]);

  const phraseInterpretation = construirePhrase(prediction);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre="Prédicteur DEESP — quand passer ?"
        sousTitre="Estimation min / moyen / max en minutes basée sur les profils horaires, avec cascade Google → prédicteur → référence 50 km/h."
      />

      {/* Onglets */}
      <div className="inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface self-start">
        <button
          type="button"
          onClick={() => setOnglet("prediction")}
          aria-pressed={onglet === "prediction"}
          className={
            "px-4 py-2 text-fluid-sm font-medium rounded transition-colors " +
            (onglet === "prediction"
              ? "bg-paa-navy-700 text-white"
              : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700")
          }
        >
          📈 Prédiction par créneau
        </button>
        <button
          type="button"
          onClick={() => setOnglet("heure_optimale")}
          aria-pressed={onglet === "heure_optimale"}
          className={
            "px-4 py-2 text-fluid-sm font-medium rounded transition-colors " +
            (onglet === "heure_optimale"
              ? "bg-paa-navy-700 text-white"
              : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700")
          }
        >
          🏆 Heure optimale de départ
        </button>
      </div>

      {/* Onglet Heure optimale */}
      {onglet === "heure_optimale" && <OngletHeureOptimale />}

      {/* Onglet Prédiction par créneau — reste tel quel */}
      {onglet === "prediction" && (
        <>

      {/* Sélecteurs */}
      <Card>
        <div className="grid gap-3 md:grid-cols-4 md:items-end">
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Tronçon
            <select
              value={tronconId ?? ""}
              onChange={(e) => setTronconId(Number(e.target.value))}
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            >
              {troncons.map((tr) => (
                <option key={tr.id} value={tr.id}>
                  {tr.nom}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Date
            <input
              type="date"
              value={dateCible}
              onChange={(e) => setDateCible(e.target.value)}
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>

          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Heure : <span className="font-mono text-paa-blue-500">{String(heure).padStart(2, "0")}:00</span>
            <input
              type="range"
              min={0}
              max={23}
              value={heure}
              onChange={(e) => setHeure(Number(e.target.value))}
              className="accent-paa-navy-700"
            />
          </label>

          <button
            type="button"
            onClick={lancerPrediction}
            disabled={tronconId === null || chargement}
            className="btn-primary disabled:opacity-50"
          >
            {chargement ? "Calcul…" : "Prédire"}
          </button>
        </div>
      </Card>

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          Erreur : {erreur}
        </div>
      )}

      {/* Résultat de prédiction */}
      {prediction && (
        <>
          {/* Badge source + type-jour */}
          <div className="flex flex-wrap gap-2">
            <BadgeSource source={prediction.source} />
            <BadgeTypeJour type={prediction.type_jour} />
            <BadgeConfiance valeur={prediction.confiance} />
          </div>

          {/* 3 KPI Min / Moyen / Max */}
          <div className="grid gap-fluid-4 md:grid-cols-3">
            <KpiPrediction label="Temps minimum attendu" mn={prediction.prediction.min_mn} couleur="#2ECC71" />
            <KpiPrediction label="Temps moyen attendu" mn={prediction.prediction.moyen_mn} couleur="#3498DB" couleurDominante />
            <KpiPrediction label="Temps maximum attendu" mn={prediction.prediction.max_mn} couleur="#E74C3C" />
          </div>

          {/* Phrase d'interprétation */}
          {phraseInterpretation && (
            <Card titre="Notre interprétation">
              <p className="text-fluid-base text-paa-navy-900 dark:text-paa-blue-100 leading-relaxed">
                {phraseInterpretation}
              </p>
            </Card>
          )}

          {/* Calibration + avertissement */}
          <Card titre="Calibration terrain" description="Multiplicateur appliqué à la prédiction depuis les relevés GPX réels. Désactivé tant que tous les relevés sont synthétiques.">
            <div className="flex flex-wrap items-baseline gap-4">
              <div>
                <div className="text-fluid-xs app-text-muted">Facteur</div>
                <div className="text-fluid-2xl font-bold">
                  {prediction.calibration_appliquee === 0
                    ? "×1,00 (neutre)"
                    : `×${(1 + prediction.calibration_appliquee).toFixed(3)}`}
                </div>
              </div>
              {prediction.avertissement && (
                <p className="flex-1 min-w-[200px] rounded-md bg-statut-dense/10 border border-statut-dense/40 px-3 py-2 text-fluid-sm text-statut-dense">
                  ⚠ {prediction.avertissement}
                </p>
              )}
            </div>
          </Card>
        </>
      )}

      {/* Qualité (MAE) en bas de page */}
      {qualite && (
        <Card
          titre="Qualité du prédicteur"
          description="Mean Absolute Error (MAE) des 7 derniers jours, mesures Google réelles vs prédiction par profils."
        >
          <div className="grid gap-fluid-4 sm:grid-cols-2">
            <MaeCard
              label="Jours ouvrables (lun–ven)"
              mae={qualite.mae_minutes.jour_ouvrable}
              nbObs={qualite.nb_observations.jour_ouvrable}
            />
            <MaeCard
              label="Week-ends (sam–dim)"
              mae={qualite.mae_minutes.week_end}
              nbObs={qualite.nb_observations.week_end}
            />
          </div>
        </Card>
      )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sous-composants
// ---------------------------------------------------------------------------

function KpiPrediction({
  label,
  mn,
  couleur,
  couleurDominante = false,
}: {
  label: string;
  mn: number | null;
  couleur: string;
  couleurDominante?: boolean;
}) {
  return (
    <div
      className="paa-card p-fluid-4"
      style={
        couleurDominante
          ? { borderLeft: `4px solid ${couleur}` }
          : undefined
      }
    >
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div
        className="mt-1 text-fluid-3xl font-bold"
        style={{ color: couleur }}
      >
        {mn === null ? "—" : `${mn} min`}
      </div>
    </div>
  );
}

function BadgeSource({ source }: { source: SourcePrediction }) {
  const c = COULEUR_SOURCE[source];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}
    >
      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
      {LIBELLE_SOURCE[source]}
    </span>
  );
}

function BadgeTypeJour({ type }: { type: "jour_ouvrable" | "week_end" }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-paa-blue-100 px-3 py-1 text-fluid-xs font-medium text-paa-navy-700 dark:bg-paa-navy-700 dark:text-paa-blue-100">
      📅 {type === "jour_ouvrable" ? "Jour ouvrable" : "Week-end"}
    </span>
  );
}

function BadgeConfiance({ valeur }: { valeur: number }) {
  const pct = Math.round(valeur * 100);
  const c = valeur >= 0.7 ? "#2ECC71" : valeur >= 0.4 ? "#F39C12" : "#95A5A6";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}
    >
      Confiance {pct}%
    </span>
  );
}

function MaeCard({ label, mae, nbObs }: { label: string; mae: number | null; nbObs: number }) {
  return (
    <div className="rounded-md border app-border p-3 app-surface">
      <div className="text-fluid-xs app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-2xl font-bold text-paa-navy-900 dark:text-paa-blue-100">
        {mae === null ? "—" : `± ${mae} min`}
      </div>
      <div className="mt-1 text-fluid-xs app-text-muted">
        Calculé sur {nbObs.toLocaleString("fr-FR")} observation{nbObs > 1 ? "s" : ""}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Génération de la phrase d'interprétation
// ---------------------------------------------------------------------------

function construirePhrase(p: PredictionResponse | null): string | null {
  if (!p) return null;
  const { min_mn, moyen_mn, max_mn } = p.prediction;
  if (moyen_mn === null) return null;

  const dateObj = new Date(p.instant_local);
  const joursFr = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
  const moisFr = ["jan.", "fév.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const libelleJour = joursFr[dateObj.getUTCDay()];
  const libelleDate = `${dateObj.getUTCDate()} ${moisFr[dateObj.getUTCMonth()]}`;
  const libelleHeure = `${String(dateObj.getUTCHours()).padStart(2, "0")}h00`;

  const fourchette =
    min_mn !== null && max_mn !== null && min_mn !== max_mn
      ? ` (entre ${min_mn} et ${max_mn} minutes selon les conditions)`
      : "";

  return `Pour un trajet ${libelleJour} ${libelleDate} à ${libelleHeure}, comptez en moyenne ${moyen_mn} minute${moyen_mn > 1 ? "s" : ""}${fourchette}.`;
}
