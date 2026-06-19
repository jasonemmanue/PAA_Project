"use client";

/**
 * Grille de 4 + 3 cartes KPI :
 *   - Ligne 1 : Temps moyen / min / max / nb mesures (compteurs sobres)
 *   - Ligne 2 : TTI / PTI / BTI (indicateurs FHWA, plus mis en valeur)
 * Affichage du badge de congestion correspondant à la classe calculée
 * sur la période choisie.
 */

import { Card } from "@/components/ui/Card";
import { StatutBadge } from "@/components/ui/StatutBadge";
import { formaterDuree } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { SnapshotIndicateurs } from "@/lib/types";

export function KpiCards({ snapshot }: { snapshot: SnapshotIndicateurs | null }) {
  const { t } = useI18n();

  const moyenne = formaterDuree(snapshot?.moyenne_s);
  const min = formaterDuree(snapshot?.min_s);
  const max = formaterDuree(snapshot?.max_s);
  const nb = snapshot?.nb_mesures ?? 0;

  const tti = snapshot?.tti !== null && snapshot?.tti !== undefined ? snapshot.tti.toFixed(2) : "—";
  const pti = snapshot?.pti !== null && snapshot?.pti !== undefined ? snapshot.pti.toFixed(2) : "—";
  const bti =
    snapshot?.bti !== null && snapshot?.bti !== undefined
      ? `+${Math.round(snapshot.bti * 100)} %`
      : "—";

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Ligne 1 : compteurs sobres */}
      <div className="grid gap-fluid-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCompteur label={t("indicateurs.kpiMoyenne")} valeur={moyenne} />
        <KpiCompteur label={t("indicateurs.kpiMin")} valeur={min} />
        <KpiCompteur label={t("indicateurs.kpiMax")} valeur={max} />
        <KpiCompteur
          label={t("indicateurs.kpiNbMesures")}
          valeur={nb.toLocaleString("fr-FR")}
        />
      </div>

      {/* Ligne 2 : TTI / PTI / BTI mis en avant + badge de classe */}
      <div className="grid gap-fluid-4 md:grid-cols-3">
        <Card titre={t("indicateurs.tti")} description={t("indicateurs.ttiTooltip")}>
          <div className="mt-2 flex items-baseline justify-between gap-2">
            <p className="text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
              {tti}
            </p>
            {snapshot && <StatutBadge classe={snapshot.classe_congestion} />}
          </div>
        </Card>
        <Card titre={t("indicateurs.pti")} description={t("indicateurs.ptiTooltip")}>
          <p className="mt-2 text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
            {pti}
          </p>
        </Card>
        <Card titre={t("indicateurs.bti")} description={t("indicateurs.btiTooltip")}>
          <p className="mt-2 text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
            {bti}
          </p>
        </Card>
      </div>
    </div>
  );
}

function KpiCompteur({ label, valeur }: { label: string; valeur: string }) {
  return (
    <div className="paa-card p-fluid-4">
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-2xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
        {valeur}
      </div>
    </div>
  );
}
