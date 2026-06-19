"use client";

/**
 * Courbe « évolution du temps de traversée » — trois séries superposées :
 *  - Temps avec trafic (orange/rouge selon classe)
 *  - Temps sans trafic (vert)
 *  - Référence 50 km/h (bleu ciel, ligne tirets) — couleur RÉSERVÉE
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

const COULEUR_TRAFIC = "#E74C3C"; // statut.congestionne
const COULEUR_FLUIDE = "#2ECC71"; // statut.fluide
const COULEUR_REFERENCE = "#4CC9F0"; // paa.sky — réservé

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

// Convertit secondes en minutes (arrondi à 1 décimale) pour l'affichage Y
function sToMin(s: number | null): number | null {
  return s === null ? null : Math.round((s / 60) * 10) / 10;
}

export function CourbeJournee({ serie }: { serie: SerieTemporelle | null }) {
  const { t } = useI18n();

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

  const refMin = (serie.temps_reference_s ?? 0) / 60;

  const data = points.map((p) => ({
    heure: formaterHeureCourte(p.instant_local),
    trafic: sToMin(p.moyenne_s),
    p95: sToMin(p.p95_s),
    nb: p.nb_mesures,
  }));

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
                  trafic: t("indicateurs.courbeTrafic"),
                  p95: t("indicateurs.pti"),
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
              dataKey="trafic"
              name={t("indicateurs.courbeTrafic")}
              stroke={COULEUR_TRAFIC}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="p95"
              name={t("indicateurs.pti")}
              stroke={COULEUR_FLUIDE}
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
        <LegendItem color={COULEUR_TRAFIC} label={t("indicateurs.courbeTrafic")} />
        <LegendItem color={COULEUR_FLUIDE} label={t("indicateurs.pti")} />
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
