"use client";

/**
 * Panneau latéral listant les 6 tronçons, leur classe de congestion et leur
 * dernier temps mesuré. Sur mobile, le panneau passe sous la carte (grid
 * responsive géré par le parent). Cliquer une ligne déclenche le recentrage
 * animé de la carte sur ce tronçon.
 */

import clsx from "clsx";

import {
  couleurClasseCongestion,
  formaterDuree,
  formaterHeureAbidjan,
  libelleClasseCongestion,
  libelleSource,
} from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat } from "@/lib/types";

type Props = {
  etat: CarteEtat | null;
  selectionId: number | null;
  onSelectionner: (id: number) => void;
};

export function PanneauTroncons({ etat, selectionId, onSelectionner }: Props) {
  const { t, locale } = useI18n();

  if (!etat) {
    return (
      <div className="paa-card p-4 text-fluid-sm app-text-muted">
        {t("common.loading")}
      </div>
    );
  }

  return (
    <div className="paa-card overflow-hidden">
      <div className="border-b app-border bg-paa-blue-100 px-4 py-2 text-fluid-sm font-semibold
                      text-paa-navy-900 dark:bg-paa-navy-700 dark:text-paa-blue-100">
        {locale === "fr" ? `${etat.nb_troncons} tronçons surveillés` : `${etat.nb_troncons} segments monitored`}
      </div>
      <ul className="divide-y divide-[rgb(var(--app-border))]">
        {etat.troncons.map((tr) => {
          const couleur = couleurClasseCongestion(tr.classe_congestion);
          const dureeTrafic = formaterDuree(tr.derniere_mesure?.duree_trafic_s);
          const actif = selectionId === tr.id;

          return (
            <li key={tr.id}>
              <button
                type="button"
                onClick={() => onSelectionner(tr.id)}
                aria-pressed={actif}
                className={clsx(
                  "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors",
                  actif
                    ? "bg-paa-blue-50 dark:bg-paa-navy-700"
                    : "hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800",
                )}
              >
                <span
                  className="mt-1 inline-block h-3 w-3 shrink-0 rounded-full"
                  style={{ backgroundColor: couleur }}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <div className="text-fluid-sm font-medium text-paa-navy-900 dark:text-paa-blue-100 truncate">
                    {tr.nom}
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-fluid-xs app-text-muted">
                    <span
                      className="font-semibold"
                      style={{ color: couleur }}
                    >
                      {libelleClasseCongestion(tr.classe_congestion, locale)}
                    </span>
                    <span>
                      {locale === "fr" ? "Temps actuel " : "Current "}
                      <span className="font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                        {dureeTrafic}
                      </span>
                    </span>
                    <span>
                      {tr.tti !== null
                        ? `TTI ${tr.tti.toFixed(2)}`
                        : "TTI —"}
                    </span>
                  </div>
                  <div className="mt-1 text-fluid-xs app-text-muted truncate">
                    {libelleSource(tr.derniere_mesure?.source)} ·{" "}
                    {formaterHeureAbidjan(tr.derniere_mesure?.horodatage)}
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
