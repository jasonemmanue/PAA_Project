"use client";

/**
 * Courbe « évolution du temps de traversée » — trois séries superposées :
 *  - Temps moyen avec trafic (rouge)
 *  - Temps maximal (orange, en tirets)
 *  - Référence 50 km/h (bleu ciel, ligne tirets)
 *
 * Aligné DEESP : pas de TTI/PTI, on affiche directement les temps en
 * minutes (Tableaux 3-15 du rapport oct. 2025).
 *
 * Données alimentées par /indicateurs/troncons/{id}/serie (granularité hour).
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";
import type { PointSerie, SerieTemporelle } from "@/lib/types";

const COULEUR_MIN = "#16a34a";       // temps minimal observé
const COULEUR_MOYENNE = "#E74C3C";   // temps moyen avec trafic
const COULEUR_MAX = "#F39C12";       // temps maximal observé
const COULEUR_REFERENCE = "#4CC9F0"; // référence 50 km/h

function formaterHeureCourte(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Africa/Abidjan",
    });
  } catch {
    return iso;
  }
}

function sToMin(s: number | null | undefined): number | null {
  return s === null || s === undefined ? null : Math.round((s / 60) * 10) / 10;
}

export function CourbeJournee({ serie }: { serie: SerieTemporelle | null }) {
  const { t, locale } = useI18n();

  const points: PointSerie[] = Array.isArray(serie?.points) ? serie!.points : [];

  if (!serie || points.length === 0) {
    return (
      <Card
        titre={t("indicateurs.courbeTitle")}
        description={t("indicateurs.courbeSubtitle")}
      >
        <div className="flex h-[260px] items-center justify-center text-fluid-sm app-text-muted">
          {t("common.noData")}
        </div>
      </Card>
    );
  }

  const refMin = (serie.temps_reference_50kmh_s ?? 0) / 60;

  const data = points.map((p) => ({
    heure: formaterHeureCourte(p.instant_local),
    min: sToMin(p.min_s),
    moyenne: sToMin(p.moyenne_s),
    max: sToMin(p.max_s),
    nb: p.nb_mesures,
  }));

  const labelMin = locale === "fr" ? "Temps minimal (min)" : "Minimum time (min)";
  const labelMoyenne =
    locale === "fr" ? "Temps moyen (min)" : "Average time (min)";
  const labelMax = locale === "fr" ? "Temps maximal (min)" : "Maximum time (min)";

  return (
    <Card
      titre={t("indicateurs.courbeTitle")}
      description={t("indicateurs.courbeSubtitle")}
    >
      <div className="h-[280px] w-full md:h-[340px] lg:h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 5, right: 8, left: -10, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(125,125,125,0.18)" />
            <XAxis
              dataKey="heure"
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
              minTickGap={32}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{
                value: "min",
                angle: -90,
                position: "insideLeft",
                offset: 14,
                style: { fontSize: 11, fill: "currentColor" },
              }}
            />
            <Tooltip
              contentStyle={{
                background: "rgba(11, 37, 69, 0.96)",
                border: "none",
                borderRadius: 6,
                fontSize: 12,
                color: "white",
              }}
              formatter={(value: unknown, key: string) => {
                const labels: Record<string, string> = {
                  min: labelMin,
                  moyenne: labelMoyenne,
                  max: labelMax,
                };
                return [`${value} min`, labels[key] ?? key];
              }}
            />
            {/* Ligne référence 50 km/h — bleu ciel, tirets */}
            <ReferenceLine
              y={Math.round(refMin * 10) / 10}
              stroke={COULEUR_REFERENCE}
              strokeWidth={2}
              strokeDasharray="6 4"
              label={{
                value: t("indicateurs.courbeReference"),
                position: "insideTopRight",
                fill: COULEUR_REFERENCE,
                fontSize: 11,
              }}
            />
            <Line
              type="monotone"
              dataKey="min"
              name={labelMin}
              stroke={COULEUR_MIN}
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="moyenne"
              name={labelMoyenne}
              stroke={COULEUR_MOYENNE}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="max"
              name={labelMax}
              stroke={COULEUR_MAX}
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Légende textuelle sous le graphique */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-fluid-xs app-text-muted">
        <LegendItem color={COULEUR_MIN} label={labelMin} dashed />
        <LegendItem color={COULEUR_MOYENNE} label={labelMoyenne} />
        <LegendItem color={COULEUR_MAX} label={labelMax} dashed />
        <LegendItem color={COULEUR_REFERENCE} label={t("indicateurs.courbeReference")} dashed />
      </div>
    </Card>
  );
}

function LegendItem({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-0.5 w-5 rounded"
        style={{
          backgroundColor: dashed ? "transparent" : color,
          borderTop: dashed ? `2px dashed ${color}` : "none",
        }}
        aria-hidden
      />
      {label}
    </span>
  );
}
