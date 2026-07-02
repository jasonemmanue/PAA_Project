"use client";

import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import type { Troncon } from "@/lib/types";

const FENETRE_JOURS = 7;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

interface CellData {
  est_congestionne: boolean | null;
  pct_rouge: number | null;
  pct_orange: number | null;
}

interface Tranche {
  heure: number;
  tranche: string;
  par_date: Record<string, CellData | null>;
}

interface MatriceData {
  troncon_id: number;
  troncon_nom: string;
  nb_mesures: number;
  dates: string[];
  tranches: Tranche[];
}

const JOURS_COURT = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

function jourCourt(dateStr: string): string {
  return JOURS_COURT[new Date(dateStr + "T12:00:00").getDay()];
}

function estWeekend(dateStr: string): boolean {
  const j = new Date(dateStr + "T12:00:00").getDay();
  return j === 0 || j === 6;
}

function Cellule({ cell }: { cell: CellData | null | undefined }) {
  if (cell === null || cell === undefined) {
    return <span className="text-gray-300 dark:text-gray-600 select-none">—</span>;
  }
  if (cell.est_congestionne === true) {
    const titre = cell.pct_rouge != null ? `Rouge ${cell.pct_rouge}%${cell.pct_orange != null ? ` / Orange ${cell.pct_orange}%` : ""}` : "Congestionné";
    return (
      <span
        title={titre}
        className="inline-block w-5 h-5 rounded-sm bg-red-500 dark:bg-red-600"
      />
    );
  }
  if (cell.est_congestionne === false) {
    return (
      <span
        title="Fluide"
        className="inline-block w-5 h-5 rounded-sm bg-green-500 dark:bg-green-600"
      />
    );
  }
  // null = indéterminé (pas de speedReadingIntervals Google)
  return (
    <span
      title="Indéterminé (pas de données couleur Google)"
      className="inline-block w-5 h-5 rounded-sm bg-gray-300 dark:bg-gray-600"
    />
  );
}

interface Props {
  campagne: string;
  debutRange: string;
  finRange: string;
  tronconId: number | null;
  troncons: Troncon[];
  onTronconChange: (id: number) => void;
  heureDebut?: number;
  heureFin?: number;
}

export function MatriceCongestion({
  campagne,
  debutRange,
  finRange,
  tronconId,
  troncons,
  onTronconChange,
  heureDebut = 0,
  heureFin = 24,
}: Props) {
  const [data, setData] = useState<MatriceData | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fenetre, setFenetre] = useState(0);

  const charger = useCallback(async () => {
    if (tronconId === null) return;
    setChargement(true);
    setErreur(null);
    try {
      const params = new URLSearchParams({
        campagne,
        troncon_id: String(tronconId),
        debut: debutRange,
        fin: finRange,
      });
      if (heureDebut !== 0) params.set("heure_debut", String(heureDebut));
      if (heureFin !== 24) params.set("heure_fin", String(heureFin));
      const rep = await fetch(`${API_BASE}/rapport/matrice-congestion?${params.toString()}`);
      if (!rep.ok) {
        const txt = await rep.text().catch(() => "");
        throw new Error(`HTTP ${rep.status} — ${txt || rep.statusText}`);
      }
      setData(await rep.json());
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, [campagne, debutRange, finRange, tronconId, heureDebut, heureFin]);

  useEffect(() => {
    setFenetre(0); // reset au changement de période
    charger();
  }, [charger]);

  const tronconNom = data?.troncon_nom ?? troncons.find((t) => t.id === tronconId)?.nom ?? "";

  // Fenêtre glissante de 7 jours sur les dates disponibles
  const datesVisibles = data
    ? data.dates.slice(fenetre * FENETRE_JOURS, (fenetre + 1) * FENETRE_JOURS)
    : [];
  const maxFenetre = data ? Math.max(0, Math.ceil(data.dates.length / FENETRE_JOURS) - 1) : 0;

  return (
    <Card
      titre="Analyse détaillée des congestions — créneaux horaires × dates"
      description={`Plage ${heureDebut === 0 && heureFin === 24 ? "24h/24" : `${String(heureDebut).padStart(2, "0")}h–${String(heureFin).padStart(2, "0")}h`}. 🟥 Congestionné  🟩 Fluide  ◻ Indéterminé (pas de données couleur)  — Sans mesure. Les week-ends sont sur fond grisé.`}
    >
      {/* Sélecteur de tronçon */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-fluid-sm font-medium app-text-muted whitespace-nowrap">
          Tronçon analysé :
        </label>
        <select
          value={tronconId ?? ""}
          onChange={(e) => onTronconChange(Number(e.target.value))}
          className="rounded-md border app-border app-surface px-3 py-1.5 text-fluid-sm
                     text-paa-navy-900 dark:text-paa-blue-100 focus:outline-none
                     focus:ring-2 focus:ring-paa-blue-400 min-w-[260px]"
        >
          {troncons.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nom}
            </option>
          ))}
        </select>
        {data && !chargement && (
          <span className="text-fluid-xs app-text-muted">
            {data.nb_mesures} mesure(s) — {data.dates.length} jour(s) avec données
          </span>
        )}
      </div>

      {erreur && (
        <div className="mb-3 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-fluid-xs text-red-700 dark:bg-red-950/40 dark:border-red-800 dark:text-red-300">
          Erreur : {erreur}
        </div>
      )}

      {chargement && (
        <div className="text-fluid-xs app-text-muted animate-pulse">Chargement de la matrice…</div>
      )}

      {!chargement && data && data.tranches.length > 0 && (
        <>
          {/* Navigation 7 jours — affiché uniquement si la période dépasse 7 jours */}
          {data.dates.length > FENETRE_JOURS && (
            <div className="mb-3 flex items-center gap-2 text-fluid-xs">
              <button
                type="button"
                disabled={fenetre === 0}
                onClick={() => setFenetre((f) => f - 1)}
                className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                           hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
              >
                ← 7 jours précédents
              </button>
              <span className="app-text-muted">
                Semaine {fenetre + 1} / {maxFenetre + 1}
              </span>
              <button
                type="button"
                disabled={fenetre >= maxFenetre}
                onClick={() => setFenetre((f) => f + 1)}
                className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                           hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
              >
                7 jours suivants →
              </button>
            </div>
          )}

        <div className="overflow-x-auto">
          <table className="text-fluid-xs border-collapse">
            <thead>
              <tr>
                {/* En-tête colonne créneau */}
                <th
                  className="sticky left-0 z-10 bg-paa-navy-700 text-white px-3 py-2
                             text-left whitespace-nowrap min-w-[90px] font-medium text-[11px]
                             border border-paa-navy-600 uppercase tracking-wide"
                >
                  CRÉNEAU
                </th>
                {datesVisibles.map((d) => {
                  const we = estWeekend(d);
                  return (
                    <th
                      key={d}
                      className={`bg-paa-navy-700 text-white px-2 py-1 text-center
                                  whitespace-nowrap min-w-[48px] font-normal
                                  border border-paa-navy-600
                                  ${we ? "opacity-60" : ""}`}
                    >
                      <div className="font-semibold text-[11px]">
                        {d.slice(8, 10)}/{d.slice(5, 7)}
                      </div>
                      <div className="text-[9px] font-normal opacity-80">{jourCourt(d)}</div>
                    </th>
                  );
                })}
                {/* Colonne compteur congestions */}
                <th
                  className="bg-paa-navy-700 text-white px-2 py-2 text-center
                             whitespace-nowrap min-w-[48px] font-medium text-[11px]
                             border border-paa-navy-600 uppercase tracking-wide"
                >
                  Total 🟥
                </th>
              </tr>
            </thead>
            <tbody>
              {data.tranches.map((tr) => {
                // Compte uniquement sur les dates visibles dans la fenêtre courante
                const nbCong = datesVisibles.filter(
                  (d) => tr.par_date[d]?.est_congestionne === true,
                ).length;
                // Total sur TOUTES les dates (pour le badge ≥4× représentatif)
                const nbCongTotal = Object.values(tr.par_date).filter(
                  (c) => c?.est_congestionne === true,
                ).length;
                const rowHighlight = nbCong >= 4 ? "bg-red-50 dark:bg-red-950/20" : "";
                return (
                  <tr
                    key={tr.heure}
                    className={`border-t app-border ${rowHighlight}`}
                  >
                    {/* Créneau — collant à gauche */}
                    <td
                      className="sticky left-0 z-10 bg-white dark:bg-paa-navy-950 font-mono
                                 px-3 py-1.5 whitespace-nowrap border-r app-border
                                 text-paa-navy-900 dark:text-paa-blue-100 text-[11px]"
                    >
                      {tr.tranche}
                      {nbCongTotal >= 4 && (
                        <span
                          title="≥ 4 occurrences congestionnées sur l'ensemble de la période (règle DEESP)"
                          className="ml-2 inline-block rounded bg-red-100 dark:bg-red-900/40
                                     px-1 text-[9px] text-red-700 dark:text-red-300 font-semibold"
                        >
                          ≥4×
                        </span>
                      )}
                    </td>
                    {/* Cellules pour les dates de la fenêtre courante */}
                    {datesVisibles.map((d) => {
                      const we = estWeekend(d);
                      return (
                        <td
                          key={d}
                          className={`px-2 py-1.5 text-center border-r border-gray-100
                                      dark:border-paa-navy-800
                                      ${we ? "bg-gray-50 dark:bg-paa-navy-900/40" : ""}`}
                        >
                          <Cellule cell={tr.par_date[d]} />
                        </td>
                      );
                    })}
                    {/* Total congestions sur la fenêtre visible */}
                    <td
                      className={`px-2 py-1.5 text-center font-semibold
                                  ${nbCong >= 4 ? "text-red-600 dark:text-red-400" : "app-text-muted"}`}
                    >
                      {nbCong > 0 ? nbCong : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <p className="mt-2 text-[10px] app-text-muted">
            {tronconNom} — {debutRange} → {finRange}
            {data.dates.length > FENETRE_JOURS && ` — Fenêtre ${fenetre + 1}/${maxFenetre + 1} (${datesVisibles[0]} → ${datesVisibles[datesVisibles.length - 1]})`}
            {" "}— Surligné en rouge si le créneau cumule ≥ 4 congestions sur la fenêtre (règle DEESP).
          </p>
        </div>
        </>
      )}

      {!chargement && data && data.tranches.length === 0 && (
        <p className="text-fluid-sm app-text-muted">
          Aucune mesure dans la plage {heureDebut === 0 && heureFin === 24 ? "24h/24" : `${String(heureDebut).padStart(2, "0")}h–${String(heureFin).padStart(2, "0")}h`} pour ce tronçon sur la période sélectionnée.
        </p>
      )}
    </Card>
  );
}
