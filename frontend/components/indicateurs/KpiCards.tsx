"use client";

/**
 * Grille de KPI alignée sur la méthodologie DEESP (cf. rapport
 * « Évaluation du temps de traversée octobre 2025 » + CLAUDE.md § 4.5.4) :
 *
 *   Ligne 1 — Temps min / moyen / max (Tableaux 3-15 du rapport)
 *             + nombre de mesures collectées.
 *
 *   Ligne 2 — Verdict couleur DEESP :
 *               • Taux de congestion (part de mesures congestionnées
 *                 selon la couleur Google Maps)
 *               • Pourcentage rouge moyen (TRAFFIC_JAM)
 *               • Pourcentage orange moyen (SLOW)
 *
 * Plus de TTI / PTI / BTI : la qualification de congestion vient
 * exclusivement des couleurs Google Maps comme dans le rapport DEESP.
 */

import { Card } from "@/components/ui/Card";
import { StatutBadge } from "@/components/ui/StatutBadge";
import { formaterDuree } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { SnapshotIndicateurs } from "@/lib/types";

export function KpiCards({ snapshot }: { snapshot: SnapshotIndicateurs | null }) {
  const { t, locale } = useI18n();

  const moyenne = formaterDuree(snapshot?.moyenne_s);
  const min = formaterDuree(snapshot?.min_s);
  const max = formaterDuree(snapshot?.max_s);
  const nb = snapshot?.nb_mesures ?? 0;
  const vitesse =
    snapshot?.vitesse_moyenne_kmh != null
      ? `${snapshot.vitesse_moyenne_kmh.toFixed(1)} km/h`
      : "—";

  const taux =
    snapshot?.taux_congestion !== null && snapshot?.taux_congestion !== undefined
      ? `${Math.round(snapshot.taux_congestion * 100)} %`
      : "—";
  const pctRouge =
    snapshot?.pourcentage_rouge_moyen !== null && snapshot?.pourcentage_rouge_moyen !== undefined
      ? `${snapshot.pourcentage_rouge_moyen.toFixed(1)} %`
      : "—";
  const pctOrange =
    snapshot?.pourcentage_orange_moyen !== null && snapshot?.pourcentage_orange_moyen !== undefined
      ? `${snapshot.pourcentage_orange_moyen.toFixed(1)} %`
      : "—";

  const labelTaux = locale === "fr" ? "Taux de congestion" : "Congestion rate";
  const tooltipTaux =
    locale === "fr"
      ? "Part de mesures où Google Maps a affiché du rouge ou de l'orange sur ≥ 50 % du tronçon (critère DEESP)."
      : "Share of measurements where Google Maps shows red or orange on ≥ 50 % of the segment (DEESP rule).";

  const labelRouge = locale === "fr" ? "% rouge moyen" : "Avg. red %";
  const tooltipRouge =
    locale === "fr"
      ? "Part moyenne du tracé en rouge (TRAFFIC_JAM) sur la période — embouteillage sévère."
      : "Average share of route in red (TRAFFIC_JAM) over the period — severe jam.";

  const labelOrange = locale === "fr" ? "% orange moyen" : "Avg. orange %";
  const tooltipOrange =
    locale === "fr"
      ? "Part moyenne du tracé en orange (SLOW). Au-delà de 50 % le rapport DEESP qualifie le tronçon de congestionné."
      : "Average share of route in orange (SLOW). Beyond 50 % the DEESP report calls the segment congested.";

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Ligne 1 — temps min / moyen / max + nb mesures */}
      <div className="grid gap-fluid-4 grid-cols-2 lg:grid-cols-5">
        <KpiCompteur label={t("indicateurs.kpiMoyenne")} valeur={moyenne} />
        <KpiCompteur label={t("indicateurs.kpiMin")} valeur={min} />
        <KpiCompteur label={t("indicateurs.kpiMax")} valeur={max} />
        <KpiCompteur label={t("indicateurs.kpiVitesseMoyenne")} valeur={vitesse} />
        <KpiCompteur
          label={t("indicateurs.kpiNbMesures")}
          valeur={nb.toLocaleString("fr-FR")}
        />
      </div>

      {/* Ligne 2 — verdict couleur DEESP */}
      <div className="grid gap-fluid-4 md:grid-cols-3">
        <Card titre={labelTaux} description={tooltipTaux}>
          <div className="mt-2 flex items-baseline justify-between gap-2">
            <p className="text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
              {taux}
            </p>
            {snapshot && <StatutBadge classe={snapshot.classe_congestion} />}
          </div>
        </Card>
        <Card titre={labelRouge} description={tooltipRouge}>
          <p className="mt-2 text-fluid-3xl font-bold" style={{ color: "#E74C3C" }}>
            {pctRouge}
          </p>
        </Card>
        <Card titre={labelOrange} description={tooltipOrange}>
          <p className="mt-2 text-fluid-3xl font-bold" style={{ color: "#F39C12" }}>
            {pctOrange}
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
