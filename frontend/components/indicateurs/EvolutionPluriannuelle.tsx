"use client";

/**
 * Évolution pluriannuelle de l'indicateur « temps de traversée » — réponse
 * directe au résultat n°4 de l'article 4 du cahier des charges.
 *
 * Source : table `evolution_indicateur` (alimentée par l'import P6.1).
 * Affiche pour chaque période (oct_2025, fev_2026, …) les temps min / moyen / max
 * agrégés sur tous les axes présents dans la table, séparés en jours
 * ouvrables / week-ends.
 *
 * Note importante (CLAUDE.md § 4.6) : les tronçons créés via
 * /administration/troncons ne disposent pas de données pluriannuelles tant
 * qu'aucune campagne historique ne les couvre — ils restent donc absents de
 * ce graphique, qui repose exclusivement sur les imports P6.1. Le reste du
 * pipeline (collecte, indicateurs, prédicteur, rapport DEESP) les inclut
 * normalement.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { LigneEvolution } from "@/lib/types";

type TypeJour = "Jours ouvrables" | "Week-ends";

export function EvolutionPluriannuelle() {
  const { t } = useI18n();
  const [lignes, setLignes] = useState<LigneEvolution[]>([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [typeJour, setTypeJour] = useState<TypeJour>("Jours ouvrables");

  useEffect(() => {
    let annule = false;
    api
      .evolution()
      .then((res) => {
        if (annule) return;
        setLignes(Array.isArray(res?.lignes) ? res.lignes : []);
      })
      .catch((e) => !annule && setErreur(e instanceof Error ? e.message : String(e)))
      .finally(() => !annule && setChargement(false));
    return () => {
      annule = true;
    };
  }, []);

  const lignesFiltrees = lignes.filter((l) => l.type_jour === typeJour);

  // Agrégation : moyenne sur tous les axes × sens présents dans la table par période
  const parPeriode = new Map<
    string,
    { sommeMin: number; sommeMoyen: number; sommeMax: number; n: number }
  >();
  for (const l of lignesFiltrees) {
    const cle = l.periode;
    const entry = parPeriode.get(cle) ?? {
      sommeMin: 0,
      sommeMoyen: 0,
      sommeMax: 0,
      n: 0,
    };
    if (l.temps_min_s !== null) entry.sommeMin += l.temps_min_s;
    if (l.temps_moyen_s !== null) entry.sommeMoyen += l.temps_moyen_s;
    if (l.temps_max_s !== null) entry.sommeMax += l.temps_max_s;
    entry.n += 1;
    parPeriode.set(cle, entry);
  }
  // Tri chronologique : "oct_2025" → 202510, "fev_2026" → 202602, etc.
  const MOIS_NUM: Record<string, number> = {
    jan: 1, fev: 2, mar: 3, avr: 4, mai: 5, jun: 6,
    jul: 7, aou: 8, sep: 9, oct: 10, nov: 11, dec: 12,
  };
  function periodeVersDate(p: string): number {
    const m = p.match(/^([a-z]+)_(\d{4})$/);
    if (!m) return 0;
    return parseInt(m[2]) * 100 + (MOIS_NUM[m[1]] ?? 0);
  }

  const data = Array.from(parPeriode.entries())
    .sort(([a], [b]) => periodeVersDate(a) - periodeVersDate(b))
    .map(([periode, v]) => ({
      periode: formaterPeriode(periode),
      min: v.n > 0 ? Math.round(v.sommeMin / v.n / 60) : 0,
      moyen: v.n > 0 ? Math.round(v.sommeMoyen / v.n / 60) : 0,
      max: v.n > 0 ? Math.round(v.sommeMax / v.n / 60) : 0,
    }));

  return (
    <Card
      titre={t("indicateurs.evolutionTitle")}
      description={t("indicateurs.evolutionSubtitle")}
    >
      {/* Toggle Jours ouvrables / Week-ends */}
      <div
        role="group"
        className="mb-3 inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface"
      >
        {(["Jours ouvrables", "Week-ends"] as const).map((tj) => {
          const actif = typeJour === tj;
          const label = tj === "Jours ouvrables"
            ? t("indicateurs.joursOuvrables")
            : t("indicateurs.weekEnds");
          return (
            <button
              key={tj}
              type="button"
              onClick={() => setTypeJour(tj)}
              aria-pressed={actif}
              className={`px-3 py-1.5 text-fluid-xs font-medium rounded transition-colors min-h-[36px] ${
                actif
                  ? "bg-paa-navy-700 text-white"
                  : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {chargement && (
        <div className="flex h-[220px] items-center justify-center text-fluid-sm app-text-muted">
          {t("common.loading")}
        </div>
      )}
      {erreur && (
        <div className="text-fluid-sm text-statut-congestionne">
          {t("common.error")} : {erreur}
        </div>
      )}
      {!chargement && !erreur && data.length === 0 && (
        <div className="flex h-[220px] items-center justify-center text-fluid-sm app-text-muted">
          {t("common.noData")}
        </div>
      )}
      {!chargement && !erreur && data.length > 0 && (
        <div className="h-[260px] w-full md:h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(125,125,125,0.18)" />
              <XAxis dataKey="periode" tick={{ fontSize: 12 }} />
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
                    min: t("indicateurs.evolutionMin"),
                    moyen: t("indicateurs.evolutionMoyen"),
                    max: t("indicateurs.evolutionMax"),
                  };
                  return [`${value} min`, labels[key] ?? key];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                formatter={(v: string) => {
                  const labels: Record<string, string> = {
                    min: t("indicateurs.evolutionMin"),
                    moyen: t("indicateurs.evolutionMoyen"),
                    max: t("indicateurs.evolutionMax"),
                  };
                  return labels[v] ?? v;
                }}
              />
              <Bar dataKey="min" fill="#2ECC71" radius={[4, 4, 0, 0]} />
              <Bar dataKey="moyen" fill="#F39C12" radius={[4, 4, 0, 0]} />
              <Bar dataKey="max" fill="#E74C3C" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function formaterPeriode(p: string): string {
  // "oct_2025" → "Oct 2025", "fev_2026" → "Fév 2026"
  const mois: Record<string, string> = {
    jan: "Jan",
    fev: "Fév",
    mar: "Mar",
    avr: "Avr",
    mai: "Mai",
    jun: "Juin",
    jul: "Juil",
    aou: "Août",
    sep: "Sep",
    oct: "Oct",
    nov: "Nov",
    dec: "Déc",
  };
  const m = p.match(/^(\w+)_(\d{4})$/);
  if (m) return `${mois[m[1]] ?? m[1]} ${m[2]}`;
  return p;
}
