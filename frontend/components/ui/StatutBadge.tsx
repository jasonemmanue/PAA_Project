"use client";

/**
 * Badge coloré indiquant un niveau de congestion DEESP (fluide /
 * congestionné / indéterminé) — couleurs identiques à celles utilisées
 * par la carte. Plus de classe « dense » : le rapport DEESP ne la
 * distingue pas (cf. CLAUDE.md § 4.5.2).
 */

import clsx from "clsx";

import type { ClasseCongestion } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const CLASSES: Record<ClasseCongestion, string> = {
  fluide: "bg-statut-fluide text-white",
  congestionne: "bg-statut-congestionne text-white",
  indetermine: "bg-statut-indetermine text-white",
};

const KEYS: Record<ClasseCongestion, string> = {
  fluide: "carte.legendFluide",
  congestionne: "carte.legendCongestionne",
  indetermine: "carte.legendIndetermine",
};

export function StatutBadge({ classe }: { classe: ClasseCongestion }) {
  const { t } = useI18n();
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-fluid-xs font-medium",
        CLASSES[classe],
      )}
    >
      {t(KEYS[classe])}
    </span>
  );
}
