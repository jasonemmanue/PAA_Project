"use client";

/**
 * Légende des couleurs de congestion + sources de mesure (matérialise
 * la cascade de dégradation gracieuse du backend).
 *
 * Volontairement compacte pour s'afficher en surimpression de la carte
 * sans gêner la lecture sur petit écran.
 */

import { useI18n } from "@/lib/i18n";

// Légende DEESP : 2 classes seulement + indéterminé. Le rapport « Évaluation
// du temps de traversée octobre 2025 » ne distingue pas de classe "dense"
// intermédiaire — congestionné = rouge OU orange long ; tout le reste est
// fluide.
const CLASSES: Array<{
  cle: string;
  couleur: string;
}> = [
  { cle: "carte.legendFluide", couleur: "#2ECC71" },
  { cle: "carte.legendCongestionne", couleur: "#E74C3C" },
  { cle: "carte.legendIndetermine", couleur: "#95A5A6" },
];

export function LegendeCarte() {
  const { t } = useI18n();

  return (
    <div
      className="pointer-events-auto absolute bottom-3 left-3 z-[1000] max-w-[260px]
                 rounded-md app-surface border app-border px-3 py-2 shadow-paa-md
                 text-fluid-xs"
      aria-label={t("carte.legendTitle")}
    >
      <div className="mb-1 text-fluid-sm font-semibold text-paa-navy-900 dark:text-paa-blue-100">
        {t("carte.legendTitle")}
      </div>
      <ul className="space-y-1">
        {CLASSES.map(({ cle, couleur }) => (
          <li key={cle} className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-5 shrink-0 rounded-sm"
              style={{ backgroundColor: couleur }}
              aria-hidden
            />
            <span className="text-paa-navy-900 dark:text-paa-blue-100">
              {t(cle)}
            </span>
          </li>
        ))}
        <li className="flex items-center gap-2 border-t pt-1 mt-1 app-border">
          <span
            className="inline-block h-3 w-5 shrink-0 rounded-sm"
            style={{ backgroundColor: "#4CC9F0" }}
            aria-hidden
          />
          <span className="text-paa-navy-900 dark:text-paa-blue-100">
            {t("carte.referenceLine")}
          </span>
        </li>
      </ul>
    </div>
  );
}
