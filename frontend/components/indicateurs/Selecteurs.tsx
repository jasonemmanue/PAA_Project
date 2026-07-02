"use client";

/**
 * Sélecteurs réutilisables pour la page Indicateurs.
 * - SelecteurTroncon : liste déroulante de **tous les tronçons actifs**
 *   chargés dynamiquement depuis `/troncons` — y compris les tronçons
 *   ajoutés via la page Administration (cf. CLAUDE.md § 4.6).
 * - SelecteurPeriode : groupe de boutons radio 24h / 7j / 30j / 90j
 * - SelecteurJour    : groupe de boutons radio Lundi → Dimanche
 */

import clsx from "clsx";

import { useI18n } from "@/lib/i18n";
import type { JourSemaine, Troncon } from "@/lib/types";

// ---------------------------------------------------------------------------
// Sélecteur de tronçon
// ---------------------------------------------------------------------------
export function SelecteurTroncon({
  troncons,
  valeur,
  onChange,
}: {
  troncons: Troncon[];
  valeur: number | null;
  onChange: (id: number) => void;
}) {
  const { t } = useI18n();
  const liste = Array.isArray(troncons) ? troncons : [];
  const estAxe = (tr: Troncon) => tr.est_axe ?? (tr.id <= 6);
  const axes   = liste.filter(estAxe);
  const troncons_ = liste.filter((tr) => !estAxe(tr));
  return (
    <label className="flex flex-col gap-1">
      <span className="text-fluid-xs font-medium app-text-muted">
        {t("indicateurs.selectTroncon")}
      </span>
      <select
        value={valeur ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-md border app-border app-surface px-3 py-2 text-fluid-sm
                   text-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   dark:text-paa-blue-100 min-h-[44px]"
      >
        {axes.length > 0 && (
          <optgroup label="── Axes ──">
            {axes.map((tr) => (
              <option key={tr.id} value={tr.id}>{tr.nom}</option>
            ))}
          </optgroup>
        )}
        {troncons_.length > 0 && (
          <optgroup label="── Tronçons ──">
            {troncons_.map((tr) => (
              <option key={tr.id} value={tr.id}>{tr.nom}</option>
            ))}
          </optgroup>
        )}
      </select>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Sélecteur de période
// ---------------------------------------------------------------------------
export type Periode = "24h" | "7j" | "30j" | "90j" | "6mois" | "1an";
const PERIODES: Periode[] = ["24h", "7j", "30j", "90j", "6mois", "1an"];

export function SelecteurPeriode({
  valeur,
  onChange,
}: {
  valeur: Periode;
  onChange: (p: Periode) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-1">
      <span className="text-fluid-xs font-medium app-text-muted">
        {t("indicateurs.selectPeriode")}
      </span>
      <div
        role="group"
        aria-label={t("indicateurs.selectPeriode")}
        className="inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface"
      >
        {PERIODES.map((p) => {
          const actif = valeur === p;
          return (
            <button
              key={p}
              type="button"
              onClick={() => onChange(p)}
              aria-pressed={actif}
              className={clsx(
                "px-3 py-1.5 text-fluid-xs font-medium rounded transition-colors min-h-[36px]",
                actif
                  ? "bg-paa-navy-700 text-white"
                  : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700",
              )}
            >
              {t(
                p === "24h" ? "indicateurs.periode24h"
                : p === "7j" ? "indicateurs.periode7j"
                : p === "30j" ? "indicateurs.periode30j"
                : p === "90j" ? "indicateurs.periode90j"
                : p === "6mois" ? "indicateurs.periode6mois"
                : "indicateurs.periode1an",
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sélecteur de jour de semaine (pour le profil horaire)
// ---------------------------------------------------------------------------
const JOURS: JourSemaine[] = [
  "lundi",
  "mardi",
  "mercredi",
  "jeudi",
  "vendredi",
  "samedi",
  "dimanche",
];

export function SelecteurJour({
  valeur,
  onChange,
}: {
  valeur: JourSemaine;
  onChange: (j: JourSemaine) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-1">
      <span className="text-fluid-xs font-medium app-text-muted">
        {t("indicateurs.selectJour")}
      </span>
      <div
        role="group"
        className="inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface"
      >
        {JOURS.map((j) => {
          const actif = valeur === j;
          const labelKey = `indicateurs.jour${j.charAt(0).toUpperCase() + j.slice(1)}`;
          return (
            <button
              key={j}
              type="button"
              onClick={() => onChange(j)}
              aria-pressed={actif}
              className={clsx(
                "px-2.5 py-1.5 text-fluid-xs font-medium rounded transition-colors min-h-[36px]",
                actif
                  ? "bg-paa-navy-700 text-white"
                  : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700",
              )}
            >
              {t(labelKey)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
