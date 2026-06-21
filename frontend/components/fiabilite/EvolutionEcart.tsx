"use client";

/**
 * Graphique d'évolution de l'écart relatif terrain / API par tronçon.
 *
 * Une ligne par tronçon (jusqu'à 6) — chaque point représente un relevé.
 * L'axe Y affiche l'écart en pourcentage (ε × 100).
 * Une ligne de référence à 0 % matérialise la cible idéale.
 */

import {
  CartesianGrid,
  Legend,
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
import type { ReleveTerrainHistorique, Troncon } from "@/lib/types";

// Palette par index — réutilise les nuances PAA hors bleu ciel. Réutilisée
// circulairement (`idx % PALETTE.length`) si le nombre de tronçons dépasse 6.
const PALETTE = [
  "#1565C8",
  "#64B5F6",
  "#C62828",
  "#EF9A9A",
  "#2E7D32",
  "#A5D6A7",
];

interface PointGraphe {
  date: string;
  [key: string]: number | string | null;
}

function formaterDateCourte(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      timeZone: "Africa/Abidjan",
    });
  } catch {
    return iso;
  }
}

export function EvolutionEcart({
  releves,
  troncons,
}: {
  releves: ReleveTerrainHistorique[];
  troncons: Troncon[];
}) {
  const { t } = useI18n();

  // Regroupe les relevés par horodatage de session (clé = date) et par tronçon.
  const tronconsParId = new Map(troncons.map((tr) => [tr.id, tr]));

  // Tri chronologique croissant pour le graphique
  const releveTries = [...releves].sort((a, b) => {
    const ka = a.horodatage_passage_utc ?? a.date_session;
    const kb = b.horodatage_passage_utc ?? b.date_session;
    return ka.localeCompare(kb);
  });

  // Une entrée par (date, troncon)
  const parDate: Map<string, PointGraphe> = new Map();
  for (const r of releveTries) {
    const cle = formaterDateCourte(r.horodatage_passage_utc ?? r.date_session);
    const entree = parDate.get(cle) ?? { date: cle };
    const troncon = tronconsParId.get(r.troncon_id);
    const nomCourt = troncon ? `T${r.troncon_id}` : `T${r.troncon_id}`;
    entree[nomCourt] = r.ecart_relatif === null ? null : r.ecart_relatif * 100;
    parDate.set(cle, entree);
  }
  const points = Array.from(parDate.values());

  // Liste des tronçons effectivement présents dans les données
  const idsPresents = Array.from(new Set(releveTries.map((r) => r.troncon_id))).sort(
    (a, b) => a - b,
  );

  if (points.length === 0) {
    return (
      <Card
        titre={t("fiabilite.evolutionTitle")}
        description={t("fiabilite.evolutionDescription")}
      >
        <div className="flex h-40 items-center justify-center text-fluid-sm app-text-muted">
          {t("fiabilite.aucunReleve")}
        </div>
      </Card>
    );
  }

  return (
    <Card
      titre={t("fiabilite.evolutionTitle")}
      description={t("fiabilite.evolutionDescription")}
    >
      <div className="h-72 w-full sm:h-80 lg:h-96">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{
                value: "ε (%)",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 11 },
              }}
              tickFormatter={(v) => `${v.toFixed(0)} %`}
            />
            <Tooltip
              formatter={(v, name) => {
                if (v === null || v === undefined) return ["—", name];
                if (typeof v === "number") return [`${v.toFixed(1)} %`, name];
                return [String(v), name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine
              y={0}
              stroke="#4CC9F0"
              strokeDasharray="4 4"
              label={{ value: "0 %", fontSize: 10, fill: "#4CC9F0" }}
            />
            {idsPresents.map((id, idx) => (
              <Line
                key={id}
                type="monotone"
                dataKey={`T${id}`}
                name={tronconsParId.get(id)?.nom ?? `Tronçon ${id}`}
                stroke={PALETTE[idx % PALETTE.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
