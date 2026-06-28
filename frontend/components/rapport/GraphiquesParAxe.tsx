"use client";

/**
 * Reproduit les 12 graphiques du rapport DEESP — exclusivement des BarChart
 * Recharts avec :
 *   - Axe X = jour de l'observation
 *   - Axe Y = temps en minutes entières
 *   - 1 barre par observation journalière
 *
 * Les LineChart ne sont PAS utilisés ici (au contraire de la page Indicateurs)
 * conformément au format attendu par le rapport.
 */

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { RapportGraphique, Troncon } from "@/lib/types";

const COULEUR_BAR_MIN = "#2ECC71";
const COULEUR_BAR_MAX = "#E74C3C";

interface Props {
  troncons: Troncon[];
  campagne: string;
  agregat: "min" | "max";
  titre: string;
}

export function GraphiquesParAxe({ troncons, campagne, agregat, titre }: Props) {
  return (
    <Card titre={titre} description="Axe Y en minutes — 1 barre = 1 observation journalière.">
      <div className="grid gap-fluid-4 lg:grid-cols-2">
        {troncons.map((t) => (
          <GraphiqueTroncon
            key={t.id}
            troncon={t}
            campagne={campagne}
            agregat={agregat}
          />
        ))}
      </div>
    </Card>
  );
}

function GraphiqueTroncon({
  troncon,
  campagne,
  agregat,
}: {
  troncon: Troncon;
  campagne: string;
  agregat: "min" | "max";
}) {
  const [data, setData] = useState<RapportGraphique | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let annule = false;
    setData(null);
    setErreur(null);
    api
      .rapportGraphique(troncon.id, campagne, agregat)
      .then((r) => {
        if (!annule) setData(r);
      })
      .catch((e) => {
        if (!annule) setErreur(e instanceof Error ? e.message : String(e));
      });
    return () => {
      annule = true;
    };
  }, [troncon.id, campagne, agregat]);

  const couleur = agregat === "min" ? COULEUR_BAR_MIN : COULEUR_BAR_MAX;
  const points = data?.points ?? [];
  const labelGraphique = `Graphique ${troncon.id} — ${troncon.nom} — Temps ${
    agregat === "min" ? "minimal" : "maximal"
  } observé (en Min)`;

  return (
    <div className="paa-card p-3">
      <h3 className="mb-1 text-fluid-xs font-semibold text-paa-navy-700 dark:text-paa-blue-100">
        {labelGraphique}
      </h3>
      {erreur && (
        <p className="text-fluid-xs text-statut-congestionne">{erreur}</p>
      )}
      {!erreur && (
        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="libelle_jour"
                tick={{ fontSize: 10 }}
                interval={0}
              />
              <YAxis tick={{ fontSize: 10 }} unit=" mn" />
              <Tooltip
                formatter={(v: unknown) => [`${v} mn`, "Temps"]}
                labelFormatter={(_, payload) => {
                  const p = payload?.[0]?.payload as { date?: string } | undefined;
                  return p?.date ?? "";
                }}
              />
              <Bar dataKey="temps_mn" fill={couleur}>
                {points.map((p, idx) => (
                  <Cell key={idx} fill={couleur} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {points.length === 0 && !erreur && data && (
        <p className="mt-2 text-fluid-xs app-text-muted">
          Aucune mesure sur cette campagne.
        </p>
      )}
    </div>
  );
}
