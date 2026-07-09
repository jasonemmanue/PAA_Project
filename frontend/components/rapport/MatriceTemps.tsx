"use client";

import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { Troncon } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

interface CellTemps {
  duree_s: number;
  source: string;
}

interface Tranche {
  heure: number;
  tranche: string;
  par_date: Record<string, CellTemps | null>;
}

interface MatriceTempsData {
  troncon_id: number;
  troncon_nom: string;
  nb_mesures: number;
  dates: string[];
  tranches: Tranche[];
  temps_ref_s: number;
  distance_m: number;
  vitesse_ref_kmh: number;
}

const JOURS_COURT = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

function jourCourt(dateStr: string): string {
  return JOURS_COURT[new Date(dateStr + "T12:00:00").getDay()];
}

function estWeekend(dateStr: string): boolean {
  const j = new Date(dateStr + "T12:00:00").getDay();
  return j === 0 || j === 6;
}

function formatMnSs(duree_s: number): string {
  const mn = Math.floor(duree_s / 60);
  const ss = Math.round(duree_s % 60);
  return `${mn}:${String(ss).padStart(2, "0")}`;
}

// Retourne le lundi (YYYY-MM-DD) de la semaine ISO contenant cette date.
function lundiSemaineIso(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const jour = d.getDay();
  const diff = jour === 0 ? 6 : jour - 1;
  const lundi = new Date(d.getTime() - diff * 86400000);
  return lundi.toISOString().slice(0, 10);
}

interface SemaineIso {
  lundiKey: string;
  dates: string[];
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

function labelSemaine(lundiKey: string): string {
  const d = new Date(lundiKey + "T12:00:00");
  const dim = new Date(d.getTime() + 6 * 86400000);
  const fmt = (dt: Date) =>
    `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}`;
  return `Sem. ${fmt(d)} – ${fmt(dim)}`;
}

function lundiSemaineActuelle(): string {
  return lundiSemaineIso(new Date().toISOString().slice(0, 10));
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

export function MatriceTemps({
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
  const [data, setData] = useState<MatriceTempsData | null>(null);
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
      if (sousTronconId !== null) params.set("sous_troncon_id", String(sousTronconId));
      const rep = await fetch(`${API_BASE}/rapport/matrice-temps?${params.toString()}`);
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

  // Regroupement par semaine ISO calendaire
  const semaines: SemaineIso[] = data ? grouperParSemaineIso(data.dates) : [];
  const maxFenetre = Math.max(0, semaines.length - 1);
  const datesVisibles = semaines[fenetre]?.dates ?? [];
  const labelFen = semaines[fenetre] ? labelSemaine(semaines[fenetre].lundiKey) : "";
  const ref_s = data?.temps_ref_s ?? 0;

  return (
    <Card
      titre="Temps de traversée — créneaux horaires × dates"
    >
      {/* Barre d'outils */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-fluid-sm font-medium app-text-muted whitespace-nowrap">
          Axe / Tronçons par axes :
        </label>
        <select
          value={
            tronconId === null
              ? ""
              : sousTronconId !== null
                ? `sous-${sousTronconId}`
                : `axe-${tronconId}`
          }
          onChange={(e) => {
            const v = e.target.value;
            if (v.startsWith("axe-")) {
              onTronconChange(Number(v.slice(4)), null);
            } else if (v.startsWith("sous-")) {
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
          <optgroup label="── Axes ──">
            {troncons.map((t) => (
              <option key={`axe-${t.id}`} value={`axe-${t.id}`}>
                {t.nom}
              </option>
            ))}
          </optgroup>
          {troncons.some((t) => (t.sous_troncons?.length ?? 0) > 0) && (
            <optgroup label="── Tronçons par axes ──">
              {troncons.flatMap((a) =>
                (a.sous_troncons ?? []).map((s) => (
                  <option key={`sous-${s.id}`} value={`sous-${s.id}`}>
                    {a.nom} : {s.nom_court} ({s.code})
                  </option>
                )),
              )}
            </optgroup>
          )}
        </select>

        {data && !chargement && (
          <span className="text-fluid-xs app-text-muted">
            {data.nb_mesures} mesure(s) — {data.dates.length} jour(s)
            {ref_s > 0 && ` — Référence 50 km/h : ${formatMnSs(ref_s)}`}
          </span>
        )}

        {tronconId !== null && (
          <a
            href={api.urlExportMesures({ troncon_id: tronconId, debut: debutRange, fin: finRange, format: "xlsx" })}
            download={`matrice_temps_troncon${tronconId}_${debutRange}_${finRange}.xlsx`}
            className="inline-flex items-center gap-2 rounded-md border border-paa-blue-300
                       px-3 py-1.5 text-fluid-xs text-paa-blue-700 dark:text-paa-blue-300
                       hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
          >
            📊 Exporter Excel
          </a>
        )}
      </div>

      {erreur && (
        <div className="mb-3 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-fluid-xs
                        text-red-700 dark:bg-red-950/40 dark:border-red-800 dark:text-red-300">
          Erreur : {erreur}
        </div>
      )}

      {chargement && (
        <div className="text-fluid-xs app-text-muted animate-pulse">
          Chargement de la matrice…
        </div>
      )}

      {!chargement && data && data.tranches.length > 0 && (
        <>
          {/* Navigation par semaine ISO — toujours affiché */}
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
                                    whitespace-nowrap min-w-[64px] font-normal
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
                               whitespace-nowrap min-w-[64px] font-medium text-[11px]
                               border border-paa-navy-600 uppercase tracking-wide"
                  >
                    Moy.
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.tranches.map((tr) => {
                  const durees = datesVisibles
                    .map((d) => tr.par_date[d]?.duree_s)
                    .filter((d): d is number => d != null);
                  const moy =
                    durees.length > 0
                      ? Math.round(durees.reduce((a, b) => a + b, 0) / durees.length)
                      : null;
                  return (
                    <tr key={tr.heure} className="border-t app-border">
                      <td
                        className="sticky left-0 z-10 bg-white dark:bg-slate-900 font-mono
                                   px-3 py-1.5 whitespace-nowrap border-r app-border
                                   text-paa-navy-900 dark:text-paa-blue-100 text-[11px]"
                      >
                        {tr.tranche}
                      </td>
                      {datesVisibles.map((d) => {
                        const cell = tr.par_date[d];
                        const we = estWeekend(d);
                        if (!cell || cell.duree_s == null) {
                          return (
                            <td
                              key={d}
                              className={`px-2 py-1.5 text-center border-r border-gray-100
                                          dark:border-paa-navy-800 text-gray-300 dark:text-gray-600
                                          ${we ? "bg-gray-50 dark:bg-paa-navy-900/40" : ""}`}
                            >
                              —
                            </td>
                          );
                        }
                        return (
                          <td
                            key={d}
                            title={`${formatMnSs(cell.duree_s)} min (source : ${cell.source})`}
                            className={`px-1 py-1.5 text-center border-r border-gray-100
                                        dark:border-paa-navy-800 font-mono text-[11px]
                                        text-gray-900 dark:text-gray-100
                                        ${we ? "opacity-80" : ""}`}
                          >
                            {formatMnSs(cell.duree_s)}
                          </td>
                        );
                      })}
                      <td
                        className={`px-2 py-1.5 text-center font-mono font-semibold text-[11px]
                                    border-l app-border
                                    ${moy != null ? "text-gray-900 dark:text-gray-100" : "app-text-muted"}`}
                      >
                        {moy != null ? formatMnSs(moy) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
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
