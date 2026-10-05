"use client";

/**
 * Libellé court et pastille de sens d'un axe — partagés par le panneau de
 * l'Accueil et la fiche de sélection de la carte.
 */

import clsx from "clsx";

import { useI18n } from "@/lib/i18n";
import type { EtatTronconCarte } from "@/lib/types";

/** Libellé court « Origine → Destination » sans les précisions de commune. */
export function nomCourtAxe(tr: EtatTronconCarte): string {
  const nettoyer = (s: string) => s.replace(/\s*\([^)]*\)/g, "").trim();
  if (tr.origine_libelle && tr.destination_libelle) {
    return `${nettoyer(tr.origine_libelle)} → ${nettoyer(tr.destination_libelle)}`;
  }
  return nettoyer(tr.nom);
}

/** Pastille « Aller » / « Retour » d'un axe — rien si le sens est inconnu. */
export function BadgeSensAxe({ sens }: { sens: EtatTronconCarte["sens_axe"] }) {
  const { t } = useI18n();
  if (!sens) return null;
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center gap-0.5 rounded px-1.5 py-0.5 text-[0.6rem] font-bold uppercase tracking-wide",
        sens === "aller"
          ? "bg-paa-blue-100 text-paa-navy-700 dark:bg-paa-navy-700 dark:text-paa-blue-100"
          : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
      )}
    >
      {sens === "aller" ? "➜" : "⟲"} {t(sens === "aller" ? "carte.axes.aller" : "carte.axes.retour")}
    </span>
  );
}
