"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Card } from "@/components/ui/Card";
import { useAuth } from "@/contexts/AuthContext";
import type { Troncon } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
const FENETRE_JOURS = 7;

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

function couleurCellule(duree_s: number, ref_s: number): string {
  if (ref_s <= 0) return "";
  const ratio = duree_s / ref_s;
  if (ratio <= 1.0)
    return "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200";
  if (ratio <= 1.3)
    return "bg-lime-100 dark:bg-lime-900/30 text-lime-800 dark:text-lime-200";
  if (ratio <= 1.5)
    return "bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200";
  return "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200";
}

interface Props {
  campagne: string;
  debutRange: string;
  finRange: string;
  tronconId: number | null;
  troncons: Troncon[];
  onTronconChange: (id: number) => void;
}

export function MatriceTemps({
  campagne,
  debutRange,
  finRange,
  tronconId,
  troncons,
  onTronconChange,
}: Props) {
  const { peutEcrire } = useAuth();
  const [data, setData] = useState<MatriceTempsData | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fenetre, setFenetre] = useState(0);
  const [importEnCours, setImportEnCours] = useState(false);
  const [msgImport, setMsgImport] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const charger = useCallback(async () => {
    if (tronconId === null) return;
    setChargement(true);
    setErreur(null);
    setFenetre(0);
    try {
      const params = new URLSearchParams({
        campagne,
        troncon_id: String(tronconId),
        debut: debutRange,
        fin: finRange,
      });
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
  }, [campagne, debutRange, finRange, tronconId]);

  useEffect(() => {
    charger();
  }, [charger]);

  // Fenêtre glissante de 7 jours
  const datesVisibles = data
    ? data.dates.slice(fenetre * FENETRE_JOURS, (fenetre + 1) * FENETRE_JOURS)
    : [];
  const maxFenetre = data
    ? Math.max(0, Math.ceil(data.dates.length / FENETRE_JOURS) - 1)
    : 0;
  const ref_s = data?.temps_ref_s ?? 0;

  async function importerExcel(e: React.ChangeEvent<HTMLInputElement>) {
    const fichier = e.target.files?.[0];
    if (!fichier) return;
    setImportEnCours(true);
    setMsgImport(null);
    try {
      const formData = new FormData();
      formData.append("fichier", fichier);
      const rep = await fetch(`${API_BASE}/rapport/import-mesures-excel`, {
        method: "POST",
        body: formData,
      });
      const json = await rep.json();
      if (!rep.ok) throw new Error(json?.detail ?? `HTTP ${rep.status}`);
      setMsgImport(
        `✓ ${json.nb_inserees} mesure(s) importée(s), ${json.nb_doublons} doublon(s) ignoré(s).`,
      );
      charger();
    } catch (err) {
      setMsgImport(`Erreur : ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setImportEnCours(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <Card
      titre="Temps de traversée — créneaux horaires × dates"
      description={
        `Plage DEESP 07h–19h. Durée réelle observée (toutes sources : google, terrain, historique). ` +
        `Couleurs : 🟢 ≤ ref 50 km/h  🟡 +30 %  🟠 +50 %  🔴 > +50 %.`
      }
    >
      {/* Barre d'outils */}
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
            {data.nb_mesures} mesure(s) — {data.dates.length} jour(s)
            {ref_s > 0 && ` — Référence 50 km/h : ${formatMnSs(ref_s)}`}
          </span>
        )}

        {/* Bouton d'import Excel — mode écriture uniquement */}
        {peutEcrire && (
          <>
            <label
              className={`inline-flex items-center gap-2 cursor-pointer rounded-md
                          border border-paa-blue-300 px-3 py-1.5 text-fluid-xs
                          text-paa-blue-700 dark:text-paa-blue-300
                          hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors
                          ${importEnCours ? "opacity-60 pointer-events-none" : ""}`}
            >
              {importEnCours ? "Import en cours…" : "📥 Importer Excel"}
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                className="hidden"
                onChange={importerExcel}
                disabled={importEnCours}
              />
            </label>
            {msgImport && (
              <span
                className={`text-fluid-xs ${
                  msgImport.startsWith("Erreur") ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400"
                }`}
              >
                {msgImport}
              </span>
            )}
          </>
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
          {/* Navigation 7 jours */}
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
                        className="sticky left-0 z-10 bg-white dark:bg-paa-navy-950 font-mono
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
                        const cls = couleurCellule(cell.duree_s, ref_s);
                        return (
                          <td
                            key={d}
                            title={`${formatMnSs(cell.duree_s)} min (source : ${cell.source})`}
                            className={`px-1 py-1.5 text-center border-r border-gray-100
                                        dark:border-paa-navy-800 font-mono text-[11px]
                                        ${we ? "opacity-80" : ""}
                                        ${cls}`}
                          >
                            {formatMnSs(cell.duree_s)}
                          </td>
                        );
                      })}
                      {/* Moyenne sur la fenêtre visible */}
                      <td
                        className={`px-2 py-1.5 text-center font-mono font-semibold text-[11px]
                                    border-l app-border
                                    ${moy != null ? couleurCellule(moy, ref_s) : "app-text-muted"}`}
                      >
                        {moy != null ? formatMnSs(moy) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {peutEcrire && (
            <p className="mt-2 text-[10px] app-text-muted">
              Format Excel attendu :{" "}
              <code className="bg-gray-100 dark:bg-paa-navy-800 px-1 rounded">
                date, heure, troncon_id, duree_mn
              </code>
              {" "}— une ligne par mesure. Insère avec{" "}
              <code className="bg-gray-100 dark:bg-paa-navy-800 px-1 rounded">
                source=historique_paa_2025
              </code>
              .
            </p>
          )}
        </>
      )}

      {!chargement && data && data.tranches.length === 0 && (
        <p className="text-fluid-sm app-text-muted">
          Aucune mesure dans la plage DEESP (07h–19h) pour ce tronçon sur la période
          sélectionnée.
          {peutEcrire && (
            <> Importez un fichier Excel pour alimenter cette vue.</>
          )}
        </p>
      )}
    </Card>
  );
}
