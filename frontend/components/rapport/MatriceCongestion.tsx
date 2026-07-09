"use client";

import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import type { Troncon } from "@/lib/types";

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

// Retourne le lundi (YYYY-MM-DD) de la semaine ISO contenant cette date.
// Semaine ISO : lundi = 1er jour, dimanche = dernier jour.
function lundiSemaineIso(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const jour = d.getDay(); // 0=dim, 1=lun…6=sam
  const diff = jour === 0 ? 6 : jour - 1; // jours depuis lundi
  const lundi = new Date(d.getTime() - diff * 86400000);
  return lundi.toISOString().slice(0, 10);
}

interface SemaineIso {
  lundiKey: string; // YYYY-MM-DD du lundi
  dates: string[];  // dates de la semaine présentes dans les données
}

function grouperParSemaineIso(dates: string[]): SemaineIso[] {
  const map = new Map<string, string[]>();
  for (const d of dates) {
    const key = lundiSemaineIso(d);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(d);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([lundiKey, dates]) => ({ lundiKey, dates }));
}

// Maximum de congestions dans une seule semaine calendaire ISO (lun–dim).
// Aligné exactement sur la règle SEMAINE du backend (troncons_congestionnes).
function maxCongestionsSemaineIso(parDate: Record<string, CellData | null>): number {
  const nbParSemaine = new Map<string, number>();
  for (const [dateStr, cell] of Object.entries(parDate)) {
    if (cell?.est_congestionne !== true) continue;
    const key = lundiSemaineIso(dateStr);
    nbParSemaine.set(key, (nbParSemaine.get(key) ?? 0) + 1);
  }
  return nbParSemaine.size > 0 ? Math.max(...nbParSemaine.values()) : 0;
}

function labelSemaine(lundiKey: string): string {
  const d = new Date(lundiKey + "T12:00:00");
  const dim = new Date(d.getTime() + 6 * 86400000);
  const fmt = (dt: Date) =>
    `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}`;
  return `Sem. ${fmt(d)} – ${fmt(dim)}`;
}

// Retourne le lundi de la semaine ISO courante.
function lundiSemaineActuelle(): string {
  return lundiSemaineIso(new Date().toISOString().slice(0, 10));
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
  sousTronconId?: number | null;
  troncons: Troncon[];
  onTronconChange: (id: number, sousId: number | null) => void;
  heureDebut?: number;
  heureFin?: number;
}

export function MatriceCongestion({
  campagne,
  debutRange,
  finRange,
  tronconId,
  sousTronconId = null,
  troncons,
  onTronconChange,
  heureDebut = 0,
  heureFin = 24,
}: Props) {
  const [data, setData] = useState<MatriceData | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fenetre, setFenetre] = useState(0);

  // Auto-sélection du premier sous-tronçon au chargement initial des tronçons
  useEffect(() => {
    if (sousTronconId !== null) return;
    const sous = troncons.flatMap((t) => t.sous_troncons ?? []);
    if (sous.length === 0) return;
    const first = sous[0];
    const parent = troncons.find((a) => (a.sous_troncons ?? []).some((s) => s.id === first.id));
    if (parent) onTronconChange(parent.id, first.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [troncons.length]);

  const charger = useCallback(async () => {
    if (tronconId === null) return;
    const tousSous = troncons.flatMap((t) => t.sous_troncons ?? []);
    if (tousSous.length > 0 && sousTronconId === null) return;
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
      if (sousTronconId !== null) params.set("sous_troncon_id", String(sousTronconId));
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
  }, [campagne, debutRange, finRange, tronconId, sousTronconId, heureDebut, heureFin]);

  useEffect(() => {
    charger();
  }, [charger]);

  // Positionne la fenêtre sur la semaine courante dès que les données arrivent
  useEffect(() => {
    if (!data || data.dates.length === 0) return;
    const semaines = grouperParSemaineIso(data.dates);
    const lundiActuel = lundiSemaineActuelle();
    const idx = semaines.findIndex((s) => s.lundiKey === lundiActuel);
    setFenetre(idx >= 0 ? idx : semaines.length - 1);
  }, [data]);

  const tronconNom = data?.troncon_nom ?? troncons.find((t) => t.id === tronconId)?.nom ?? "";

  // Regroupement par semaine ISO calendaire
  const semaines: SemaineIso[] = data ? grouperParSemaineIso(data.dates) : [];
  const maxFenetre = Math.max(0, semaines.length - 1);
  const datesVisibles = semaines[fenetre]?.dates ?? [];
  const labelFen = semaines[fenetre] ? labelSemaine(semaines[fenetre].lundiKey) : "";

  return (
    <Card
      titre="Analyse détaillée des congestions — créneaux horaires × dates"
      description={`Plage ${heureDebut === 0 && heureFin === 24 ? "24h/24" : `${String(heureDebut).padStart(2, "0")}h–${String(heureFin).padStart(2, "0")}h`}. 🟥 Congestionné  🟩 Fluide  ◻ Indéterminé  — Sans mesure. Week-ends sur fond grisé. Badge ≥4× = règle SEMAINE ISO déclenchée.`}
    >
      {/* Sélecteur de tronçon */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-fluid-sm font-medium app-text-muted whitespace-nowrap">
          Tronçon codifié :
        </label>
        <select
          value={sousTronconId !== null ? `sous-${sousTronconId}` : ""}
          onChange={(e) => {
            const v = e.target.value;
            if (v.startsWith("sous-")) {
              const sid = Number(v.slice(5));
              const parent = troncons.find((a) =>
                (a.sous_troncons ?? []).some((s) => s.id === sid),
              );
              if (parent) onTronconChange(parent.id, sid);
            }
          }}
          className="rounded-md border app-border app-surface px-3 py-1.5 text-fluid-sm
                     text-paa-navy-900 dark:text-paa-blue-100 focus:outline-none
                     focus:ring-2 focus:ring-paa-blue-400 min-w-[260px]"
        >
          <option value="" disabled>
            Sélectionnez un tronçon codifié…
          </option>
          {troncons.flatMap((a) =>
            (a.sous_troncons ?? []).map((s) => (
              <option key={`sous-${s.id}`} value={`sous-${s.id}`}>
                [{s.code}] {s.nom_court} — {a.nom}
              </option>
            )),
          )}
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
          {/* Navigation par semaine ISO — toujours affiché s'il y a plusieurs semaines */}
          <div className="mb-3 flex items-center gap-2 text-fluid-xs">
            <button
              type="button"
              disabled={fenetre === 0}
              onClick={() => setFenetre((f) => f - 1)}
              className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                         hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
            >
              ← Semaine précédente
            </button>
            <span className="app-text-muted font-medium">
              {labelFen} ({fenetre + 1}/{semaines.length})
            </span>
            <button
              type="button"
              disabled={fenetre >= maxFenetre}
              onClick={() => setFenetre((f) => f + 1)}
              className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                         hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
            >
              Semaine suivante →
            </button>
          </div>

        <div className="overflow-x-auto">
          <table className="text-fluid-xs border-collapse">
            <thead>
              <tr>
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
                // Compte sur les dates visibles de la fenêtre
                const nbCong = datesVisibles.filter(
                  (d) => tr.par_date[d]?.est_congestionne === true,
                ).length;
                // Badge ≥4× : max dans une semaine ISO calendaire — aligné avec le backend
                const nbCongSemaineMax = maxCongestionsSemaineIso(tr.par_date);
                const rowHighlight = nbCong >= 4 ? "bg-red-50 dark:bg-red-950/20" : "";
                return (
                  <tr
                    key={tr.heure}
                    className={`border-t app-border ${rowHighlight}`}
                  >
                    <td
                      className="sticky left-0 z-10 bg-white dark:bg-slate-900 font-mono
                                 px-3 py-1.5 whitespace-nowrap border-r app-border
                                 text-paa-navy-900 dark:text-paa-blue-100 text-[11px]"
                    >
                      {tr.tranche}
                      {nbCongSemaineMax >= 4 && (
                        <span
                          title={`≥ 4 occurrences congestionnées dans la même semaine ISO (lun–dim) — règle DEESP semaine, Tableau 16`}
                          className="ml-2 inline-block rounded bg-red-100 dark:bg-red-900/40
                                     px-1 text-[9px] text-red-700 dark:text-red-300 font-semibold"
                        >
                          ≥4×
                        </span>
                      )}
                    </td>
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
            {datesVisibles.length > 0 && ` — ${labelFen}`}
            {" "}— Surligné en rouge si ≥ 4 congestions dans la fenêtre (règle DEESP).
            Badge ≥4× = règle SEMAINE ISO déclenchée sur l'ensemble de la période.
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
