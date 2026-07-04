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
/** Sélection typée par le composant : axe seul, ou sous-tronçon + son axe parent. */
export type SelectionTroncon =
  | { type: "axe"; tronconId: number }
  | { type: "sous"; tronconId: number; sousTronconId: number };

/** Encode la sélection en une clé unique pour l'option <select>. */
export function encoderSelection(s: SelectionTroncon | null): string {
  if (!s) return "";
  return s.type === "axe" ? `axe-${s.tronconId}` : `sous-${s.sousTronconId}`;
}

export function SelecteurTroncon({
  troncons,
  selection,
  onChange,
}: {
  troncons: Troncon[];
  selection: SelectionTroncon | null;
  onChange: (s: SelectionTroncon) => void;
}) {
  const { t } = useI18n();
  const liste = Array.isArray(troncons) ? troncons : [];
  const estAxe = (tr: Troncon) => tr.est_axe ?? (tr.id <= 6);
  const axes   = liste.filter(estAxe);
  const orphelins = liste.filter((tr) => !estAxe(tr));

  const surSelect = (cle: string) => {
    if (cle.startsWith("axe-")) {
      const id = Number(cle.slice(4));
      if (Number.isFinite(id)) onChange({ type: "axe", tronconId: id });
      return;
    }
    if (cle.startsWith("sous-")) {
      const sid = Number(cle.slice(5));
      const parent = axes.find((a) =>
        (a.sous_troncons ?? []).some((s) => s.id === sid),
      );
      if (parent && Number.isFinite(sid)) {
        onChange({ type: "sous", tronconId: parent.id, sousTronconId: sid });
      }
    }
  };

  return (
    <label className="flex flex-col gap-1">
      <span className="text-fluid-xs font-medium app-text-muted">
        {t("indicateurs.selectTroncon")}
      </span>
      <select
        value={encoderSelection(selection)}
        onChange={(e) => surSelect(e.target.value)}
        className="rounded-md border app-border app-surface px-3 py-2 text-fluid-sm
                   text-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   dark:text-paa-blue-100 min-h-[44px]"
      >
        {axes.length > 0 && (
          <optgroup label="── Axes ──">
            {axes.map((tr) => (
              <option key={`axe-${tr.id}`} value={`axe-${tr.id}`}>{tr.nom}</option>
            ))}
          </optgroup>
        )}
        {axes.some((a) => (a.sous_troncons?.length ?? 0) > 0) && (
          <optgroup label="── Tronçons par axes ──">
            {axes.flatMap((a) =>
              (a.sous_troncons ?? []).map((s) => (
                <option key={`sous-${s.id}`} value={`sous-${s.id}`}>
                  {a.nom} : {s.nom_court} ({s.code})
                </option>
              )),
            )}
          </optgroup>
        )}
        {orphelins.length > 0 && (
          <optgroup label="── Tronçons ──">
            {orphelins.map((tr) => (
              <option key={`orph-${tr.id}`} value={`axe-${tr.id}`}>{tr.nom}</option>
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
