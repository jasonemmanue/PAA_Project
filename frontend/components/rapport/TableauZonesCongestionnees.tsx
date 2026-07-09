"use client";

import { Card } from "@/components/ui/Card";
import type { RapportZonesCongestionnees, EntreeCongestion } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

/**
 * Téléchargement direct du PDF généré côté backend (fpdf2).
 * Utilise une navigation directe (pas fetch) pour contourner les restrictions CORS
 * sur les requêtes cross-origin. Le serveur envoie Content-Disposition: attachment,
 * ce qui déclenche le téléchargement sans quitter la page.
 */
function telechargerPdf(campagne: string, debut?: string, fin?: string, heureDebut = 0, heureFin = 24): void {
  const params = new URLSearchParams({ campagne });
  if (debut) params.set("debut", debut);
  if (fin) params.set("fin", fin);
  if (heureDebut !== 0) params.set("heure_debut", String(heureDebut));
  if (heureFin !== 24) params.set("heure_fin", String(heureFin));
  const url = `${API_BASE}/rapport/zones-congestionnees/pdf?${params.toString()}`;
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function exporterCsv(entrees: EntreeCongestion[], nomFichier: string, typeLabel: string): void {
  const headers = [typeLabel, "AXE", "TRANCHE HORAIRE", "NB / SEMAINE", "RÈGLE DÉCLENCHÉE"];
  const lignes = entrees.map((e) => {
    const nom = e.sous_troncon_code
      ? `${e.sous_troncon_code} - ${e.sous_troncon_nom ?? ""}`
      : e.troncon_nom;
    const regles: string[] = [];
    if (e.regle_semaine) regles.push("Règle 1 — semaine (>=4 fois)");
    if (e.regle_jour_indicatif) regles.push("Règle 2 — jour indicatif (>=3 fois)");
    return [nom, e.troncon_nom, e.tranche, String(e.nb_total_semaine), regles.join(" | ")];
  });

  const csv = [headers, ...lignes].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nomFichier;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

export function TableauZonesCongestionnees({
  rapport,
  debutRange,
  finRange,
  heureDebut = 0,
  heureFin = 24,
}: {
  rapport: RapportZonesCongestionnees | null;
  debutRange?: string;
  finRange?: string;
  heureDebut?: number;
  heureFin?: number;
}) {
  // Seuls les tronçons codifiés (sous-tronçons) sont affichés — conformément
  // à la méthodologie DEESP : la congestion s'évalue au niveau tronçon.
  const entrees = (rapport?.entrees ?? []).filter((e) => e.sous_troncon_id !== null);

  return (
    <Card
      titre="Tableau 16 — Tronçons congestionnés (règles DEESP)"
      description={
        "Un tronçon est congestionné à un créneau horaire si l'une des deux règles DEESP est vérifiée — " +
        "Règle 1 (semaine) : ce créneau revient au moins 4 fois dans la même semaine calendaire ISO (lun–dim) ; " +
        "Règle 2 (jour indicatif) : ce même jour de la semaine (ex. lundi) est congestionné à cette tranche horaire au moins 3 fois dans le mois. " +
        "Critère de congestion d'une mesure : couleur Google Maps — rouge présent OU orange ≥ 50 % du tronçon."
      }
    >

      {/* ──── Tronçons codifiés congestionnés ──── */}
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>TRONÇON</Th>
              <Th>AXE</Th>
              <Th>TRANCHE HORAIRE</Th>
              <Th className="text-right">NB / SEMAINE</Th>
              <Th>RÈGLE DÉCLENCHÉE</Th>
            </tr>
          </thead>
          <tbody>
            {entrees.map((e) => (
              <LigneTroncon key={`${e.sous_troncon_id}-${e.troncon_id}-${e.heure}`} e={e} />
            ))}
            {entrees.length === 0 && (
              <tr>
                <Td colSpan={5}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Aucun tronçon codifié congestionné sur cette campagne."
                      : "Chargement…"}
                  </span>
                </Td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {entrees.length > 0 && (
        <div className="mt-2 flex justify-end gap-2">
          <BoutonExportCsv
            label="Exporter CSV"
            onClick={() =>
              exporterCsv(entrees, `congestion_troncons_${rapport?.campagne ?? "export"}.csv`, "TRONÇON")
            }
          />
        </div>
      )}

      {/* Bouton PDF global en bas — couvre axes + tronçons codifiés */}
      <div className="mt-4 border-t app-border pt-4">
        <BoutonExportPdf
          campagne={rapport?.campagne ?? ""}
          actif={!!rapport}
          debut={debutRange}
          fin={finRange}
          heureDebut={heureDebut}
          heureFin={heureFin}
        />
      </div>
    </Card>
  );
}

function LigneTroncon({ e }: { e: EntreeCongestion }) {
  return (
    <tr className="border-t app-border">
      <Td>
        <div className="flex flex-col">
          <span className="font-mono font-semibold">{e.sous_troncon_code}</span>
          <span className="text-fluid-xs app-text-muted">{e.sous_troncon_nom}</span>
        </div>
      </Td>
      <Td>
        <span className="text-fluid-xs app-text-muted">{e.troncon_nom}</span>
      </Td>
      <Td className="font-mono">{e.tranche}</Td>
      <Td className="text-right font-semibold">{e.nb_total_semaine}</Td>
      <Td>
        <Regles e={e} />
      </Td>
    </tr>
  );
}

function Regles({ e }: { e: EntreeCongestion }) {
  return (
    <div className="flex flex-col gap-1">
      {e.regle_semaine && (
        <span className="inline-block rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">
          Règle 1 — semaine (≥ 4 ×)
        </span>
      )}
      {e.regle_jour_indicatif && (
        <span className="inline-block rounded bg-statut-congestionne/20 px-2 py-0.5 text-xs text-statut-congestionne">
          Règle 2 — jour indicatif (≥ 3 ×)
        </span>
      )}
    </div>
  );
}

function BoutonExportPdf({
  campagne,
  actif,
  debut,
  fin,
  heureDebut = 0,
  heureFin = 24,
}: {
  campagne: string;
  actif: boolean;
  debut?: string;
  fin?: string;
  heureDebut?: number;
  heureFin?: number;
}) {
  return (
    <div className="mb-3 flex justify-end">
      <button
        type="button"
        disabled={!actif}
        onClick={() => telechargerPdf(campagne, debut, fin, heureDebut, heureFin)}
        className="inline-flex items-center gap-2 rounded-md bg-paa-navy-700 px-3 py-1.5
                   text-fluid-xs font-medium text-white shadow-sm transition-colors
                   hover:bg-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   disabled:cursor-not-allowed disabled:opacity-40"
      >
        <>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
          Exporter PDF
        </>
      </button>
    </div>
  );
}

function BoutonExportCsv({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md border app-border px-3 py-1.5
                 text-fluid-xs font-medium app-text transition-colors
                 hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800
                 focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
      </svg>
      {label}
    </button>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-3 py-2 text-left text-fluid-xs font-medium uppercase tracking-wide ${className ?? ""}`}>
      {children}
    </th>
  );
}

function Td({
  children,
  colSpan,
  className,
}: {
  children: React.ReactNode;
  colSpan?: number;
  className?: string;
}) {
  return (
    <td
      colSpan={colSpan}
      className={`px-3 py-2 align-top text-paa-navy-900 dark:text-paa-blue-100 ${className ?? ""}`}
    >
      {children}
    </td>
  );
}
